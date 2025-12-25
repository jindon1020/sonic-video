from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
import shutil
import asyncio

from app.core.video_processor import VideoProcessor
from app.core.vector_engine import VectorEngine
from app.core.audio_processor import AudioProcessor
from app.core.editor import Editor
from app.core.llm_engine import LLMEngine
from app.core.image_processor import ImageProcessor

app = FastAPI(title="Director AI Agent")

# Static files & Folders
UPLOADS_DIR = "uploads"
PROCESSED_DIR = "app/static/processed"
THUMBNAILS_DIR = "app/static/processed/thumbnails"
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)
os.makedirs(THUMBNAILS_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Initialize engines
video_proc = VideoProcessor()
vector_eng = VectorEngine()
audio_proc = AudioProcessor()
editor = Editor()
llm_eng = LLMEngine() # Initialize Gemini
image_proc = ImageProcessor()  # Image and Live Photo processor

# WebSocket Connection Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                continue

manager = ConnectionManager()
progress_logs = []

async def log_progress(msg):
    global progress_logs
    progress_logs.append(msg)
    print(f" LOG: {msg}")
    await manager.broadcast(msg)

async def generate_ai_video(prompt, duration_sec=5):
    from dashscope.aigc.video_synthesis import VideoSynthesis
    
    # 候选模型列表 (优先级从高到低)
    candidate_models = [
        "wan2.1-t2v-14b",
        "wan2.1-t2v-1.3b",
        "wanx2.1-t2v-plus", 
        "wanx2.1-t2v-turbo",
        "wanx-v1",
        "video-generation"
    ]

    for model_name in candidate_models:
        try:
            await log_progress(f"🎨 正在尝试调用模型 [{model_name}] 生成视频...")
            
            rsp = VideoSynthesis.call(model=model_name, 
                                     prompt=prompt,
                                     size="1280*720")
            
            if rsp.status_code == 200:
                task_id = rsp.output.task_id
                await log_progress(f"⏳ [{model_name}] 任务提交成功 (Task: {task_id})，等待渲染...")
                
                # Wait for completion
                status = VideoSynthesis.wait(rsp)
                if status.status_code == 200:
                    video_url = status.output.video_url
                    await log_progress("✨ AI 视频生成成功，正在下载...")
                    
                    # Download video
                    import requests
                    r = requests.get(video_url)
                    file_name = f"ai_gen_{task_id}.mp4"
                    save_path = os.path.join(UPLOADS_DIR, file_name)
                    with open(save_path, 'wb') as f:
                        f.write(r.content)
                    
                    return save_path
                else:
                    await log_progress(f"❌ [{model_name}] 渲染失败: {status.message}")
            else:
                if "Model not exist" in rsp.message:
                    continue # Try next model
                await log_progress(f"❌ [{model_name}] 调用报错: {rsp.message}")
                
        except Exception as e:
            await log_progress(f"❌ [{model_name}] 异常: {str(e)}")
            
    await log_progress("❌ 所有 AI 模型均尝试失败，无法生成视频。")
    return None

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Send history on connect
        for log in progress_logs:
            await websocket.send_text(log)
        while True:
            await websocket.receive_text() # Keep connection alive
    except WebSocketDisconnect:
        manager.disconnect(websocket)

async def process_video_agent(audio_path, video_paths, intent, manual_lyrics=None, allow_ai_gen=False):
    global progress_logs
    progress_logs = []
    
    try:
        # 1. Analyze Audio
        await log_progress("🎵 [STEP 1/4] 音频深度解析开始...")
        if manual_lyrics:
            await log_progress("📝 检测到用户手动输入歌词，正在开启【参考对齐】模式以提升识别精度...")
        
        await log_progress("📡 正在调用 Whisper 进行语义对齐，提取歌词时间戳...")
        raw_segments = audio_proc.transcribe_with_timestamps(audio_path, manual_lyrics)
        
        # 核心逻辑优化：镜头不要太碎，合并到 10-15s
        await log_progress("🧬 正在进行【长镜头策略】分析：正在将短句合并为 10-15s 的完整视觉单元...")
        segments = []
        curr = None
        for s in raw_segments:
            if curr is None:
                curr = s.copy()
            else:
                curr['text'] += " " + s['text']
                curr['end'] = s['end']
            
            if (curr['end'] - curr['start']) >= 10.0:
                segments.append(curr)
                curr = None
        if curr: segments.append(curr)

        await log_progress("💓 正在分析音频节拍与节奏特征...")
        beats = audio_proc.analyze_beats(audio_path)
        await log_progress(f"📊 音频分析完成: 已将片段聚类为 {len(segments)} 个【长视觉单元】，BPM: {beats['tempo']:.1f}")
        
        # 2. Process Videos & Images
        await log_progress("🎬 [STEP 2/4] 素材库特征工程启动...")
        all_clips = []
        for v_item in video_paths:
            # Handle different media types
            if isinstance(v_item, dict):
                if v_item['type'] == 'image':
                    # Static image - convert to video with Ken Burns effect
                    img_path = v_item['path']
                    img_name = os.path.basename(img_path)
                    await log_progress(f"🖼️ 正在将图片 {img_name} 转换为动态视频...")
                    
                    try:
                        video_path = image_proc.create_video_from_image(
                            img_path, 
                            duration=5.0,  # 5 seconds default
                            add_motion=True  # Ken Burns effect
                        )
                        clip = {
                            "path": video_path,
                            "start": 0,
                            "end": 5.0,
                            "duration": 5.0,
                            "type": "image"
                        }
                        # Use the image directly for embedding
                        vec = vector_eng.encode_image(img_path)
                        vector_eng.add_to_index(vec, clip)
                        all_clips.append(clip)
                        await log_progress(f"✅ 图片 {img_name} 已转换为动态视频片段")
                    except Exception as e:
                        await log_progress(f"⚠️ 图片处理失败: {str(e)}")
                        
                elif v_item['type'] == 'live_photo':
                    # Apple Live Photo - extract the motion video
                    img_path = v_item['image']
                    mov_path = v_item['video']
                    base_name = os.path.basename(img_path).split('.')[0]
                    await log_progress(f"📱 检测到 Live Photo: {base_name}，正在提取动态内容...")
                    
                    try:
                        video_path = image_proc.process_live_photo(img_path, mov_path)
                        # Get duration from the MOV file
                        import cv2
                        cap = cv2.VideoCapture(video_path)
                        fps = cap.get(cv2.CAP_PROP_FPS)
                        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                        duration = frame_count / fps if fps > 0 else 3.0
                        cap.release()
                        
                        clip = {
                            "path": video_path,
                            "start": 0,
                            "end": duration,
                            "duration": duration,
                            "type": "live_photo"
                        }
                        # Use the still image for embedding (better quality)
                        if img_path.lower().endswith(('.heic', '.heif')):
                            img_path = image_proc.convert_heic_to_jpg(img_path)
                        vec = vector_eng.encode_image(img_path)
                        vector_eng.add_to_index(vec, clip)
                        all_clips.append(clip)
                        await log_progress(f"✅ Live Photo {base_name} 已处理完成 (时长: {duration:.1f}s)")
                    except Exception as e:
                        await log_progress(f"⚠️ Live Photo 处理失败: {str(e)}")
            else:
                # Regular video file
                v_path = v_item
                v_name = os.path.basename(v_path)
                
                # Get video info for memory estimation
                v_info = video_proc.get_video_info(v_path)
                await log_progress(f"🎞️ 正在对视频 {v_name} 进行镜头切分 (大小: {v_info['size_mb']:.1f}MB, 时长: {v_info['duration']:.1f}s)...")
                
                clips = video_proc.split_scenes(v_path)
                
                # Batch processing for feature extraction
                FEATURE_BATCH_SIZE = 10
                total_clips = len(clips)
                await log_progress(f"🧊 正在分批提取 {total_clips} 个镜头的视觉特征向量 (每批 {FEATURE_BATCH_SIZE} 个)...")
                
                for i, clip in enumerate(clips):
                    kf_path = video_proc.extract_keyframe(clip["path"])
                    if kf_path:
                        vec = vector_eng.encode_image(kf_path)
                        vector_eng.add_to_index(vec, clip)
                        
                        # Clean up keyframe file to save disk space
                        try:
                            os.remove(kf_path)
                        except:
                            pass
                    
                    # Progress and memory cleanup
                    if (i + 1) % FEATURE_BATCH_SIZE == 0:
                        await log_progress(f"   - 已处理 {i+1}/{total_clips} 个镜头，正在清理缓存...")
                        import gc
                        gc.collect()
                        
                all_clips.extend(clips)
                
        # Final memory stats
        stats = vector_eng.get_memory_stats()
        await log_progress(f"✅ 素材库构建完成，当前索引容量: {stats['vectors_count']} 个语义片段")
        
        # 3. Creative Matching (Qwen Powered)
        await log_progress("🧠 [STEP 3/4] 阿里云 Qwen 导演系统启动，正在编排分镜...")
        final_sequence = []
        used_clip_paths = set()
        
        for idx, seg in enumerate(segments):
            lyric_text = seg['text'].strip()
            if not lyric_text: continue
            
            await log_progress(f"✍️ 正在构思第 {idx+1} 个长镜头 (歌词: \"{lyric_text[:30]}...\")")
            
            script = await llm_eng.generate_visual_script(lyric_text, intent)
            semantic_translation = script['reasoning']
            search_query = script['visual_prompt']
            
            # 使用较多候选进行去重
            matches = vector_eng.search(search_query, top_k=20)
            
            best_match = None
            if matches:
                for m in matches:
                    if m['path'] not in used_clip_paths:
                        best_match = m
                        break
                if not best_match: best_match = matches[0]
            
                if best_match['score'] < 0.22 and allow_ai_gen:
                    await log_progress(f"⚠️ 最佳素材相关度仅为 {best_match['score']:.2f} (低于阈值 0.22)，尝试启动 AI 生成...")
                    ai_video_path = await generate_ai_video(search_query)
                    
                    if ai_video_path:
                        match = {
                            "path": ai_video_path,
                            "type": "video",
                            "score": 0.99, # Artificial score for generated content
                            "target_duration": seg['end'] - seg['start'] 
                        }
                        final_sequence.append(match)
                        await log_progress(f"🎨 AI 生成视频已采纳 -> [{os.path.basename(ai_video_path)}]")
                    else:
                        # Fallback to best match if AI fails
                        match = best_match.copy()
                        match['target_duration'] = seg['end'] - seg['start']
                        final_sequence.append(match)
                        used_clip_paths.add(match['path'])
                        await log_progress(f"🎯 匹配成功 (AI 生成失败，回退): \"{semantic_translation}\" -> 选中 [{os.path.basename(match['path'])}] (相关度: {match['score']:.2f})")
                
                else:
                    match = best_match.copy()
                    match['target_duration'] = seg['end'] - seg['start']
                    final_sequence.append(match)
                    used_clip_paths.add(match['path'])
                    
                    await log_progress(f"🎯 匹配成功: \"{semantic_translation}\" -> 选中 [{os.path.basename(match['path'])}] (相关度: {match['score']:.2f})")
            
        # 4. Assembly
        await log_progress("🎞️ [STEP 4/4] 进入后期合成阶段...")
        await log_progress("⚙️ 正在执行 MoviePy 视频流混放、音轨对齐与高性能渲染并行导出...")
        final_video_path = editor.assemble(final_sequence, audio_path)
        
        await log_progress("✨ 制作任务圆满完成！最终成片已生成。")
        
    except Exception as e:
        error_msg = f"❌ 任务中断: 系统遇到不可恢复的错误 -> {str(e)}"
        await log_progress(error_msg)
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup: Reset vector engine and free memory
        await log_progress("🧹 正在释放内存资源...")
        vector_eng.reset()
        import gc
        gc.collect()
        await log_progress("♻️ 资源清理完毕，系统就绪")

@app.get("/", response_class=HTMLResponse)
async def get_index():
    with open("app/static/index.html", "r") as f:
        return f.read()

@app.post("/upload")
async def upload_files(
    background_tasks: BackgroundTasks,
    audio: UploadFile = File(None),
    media: list[UploadFile] = File(...),  # Changed from 'videos' to 'media' (images + videos)
    intent: str = Form(...),
    lyrics: str = Form(None),
    allow_ai_generation: str = Form("false")  # Receive as string from FormData
):
    # Check boolean
    allow_ai_gen = (allow_ai_generation.lower() == 'true')

    # Save audio
    audio_path = None
    if audio:
        audio_path = os.path.join(UPLOADS_DIR, audio.filename)
        with open(audio_path, "wb") as buffer:
            shutil.copyfileobj(audio.file, buffer)
    
    # Save all media files and categorize
    saved_files = []
    for file in media:
        file_path = os.path.join(UPLOADS_DIR, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        saved_files.append(file_path)
    
    # Use ImageProcessor to detect Live Photos and categorize files
    detected_media = image_proc.auto_detect_live_photo_pair(saved_files)
    
    video_paths = []
    for item in detected_media:
        if item['type'] == 'video':
            # Regular video file
            video_paths.append(item['video'])
        elif item['type'] == 'image':
            # Static image - keep original path, will convert in processor
            video_paths.append({'type': 'image', 'path': item['image']})
        elif item['type'] == 'live_photo':
            # Live Photo pair
            video_paths.append({
                'type': 'live_photo',
                'image': item['image'],
                'video': item['video']
            })
    
    # Start agent in background
    background_tasks.add_task(process_video_agent, audio_path, video_paths, intent, lyrics, allow_ai_gen)
    return {"status": "processing"}

@app.post("/thumbnail")
async def get_video_thumbnail(video: UploadFile = File(...)):
    temp_path = os.path.join(UPLOADS_DIR, f"temp_{video.filename}")
    with open(temp_path, "wb") as f:
        shutil.copyfileobj(video.file, f)
    
    thumb_name = f"{video.filename}.jpg"
    thumb_path = os.path.join(THUMBNAILS_DIR, thumb_name)
    
    success = video_proc.extract_thumbnail(temp_path, thumb_path)
    os.remove(temp_path)
    
    if success:
        return {"thumbnail_url": f"/static/processed/thumbnails/{thumb_name}"}
    else:
        return JSONResponse(status_code=500, content={"message": "Failed to extract thumbnail"})

@app.get("/progress")
async def get_progress():
    return {"logs": progress_logs}

@app.post("/image-thumbnail")
async def get_image_thumbnail(image: UploadFile = File(...)):
    """Generate thumbnail for image files, especially HEIC format."""
    temp_path = os.path.join(UPLOADS_DIR, f"temp_{image.filename}")
    with open(temp_path, "wb") as f:
        shutil.copyfileobj(image.file, f)
    
    thumb_name = f"{image.filename}.jpg"
    thumb_path = os.path.join(THUMBNAILS_DIR, thumb_name)
    
    success = image_proc.extract_thumbnail(temp_path, thumb_path)
    os.remove(temp_path)
    
    if success:
        return {"thumbnail_url": f"/static/processed/thumbnails/{thumb_name}"}
    else:
        return JSONResponse(status_code=500, content={"message": "Failed to extract image thumbnail"})

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
