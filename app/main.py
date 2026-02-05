from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
import shutil
import asyncio
import json
import gc
import traceback
import cv2
import requests
import librosa
import sys

# --- FFmpeg 路径补构 (Fix for Mac Homebrew) ---
ffmpeg_paths = ["/opt/homebrew/bin", "/usr/local/bin"]
current_path = os.environ.get("PATH", "")
for p in ffmpeg_paths:
    if p not in current_path and os.path.exists(p):
        os.environ["PATH"] = f"{p}:{current_path}"
        current_path = os.environ["PATH"]
# -------------------------------------------

from app.core.config_manager import ConfigManager
from app.core.video_processor import VideoProcessor
from app.core.vector_engine import VectorEngine
from app.core.audio_processor import AudioProcessor
from app.core.editor import Editor
from app.core.llm_engine import LLMEngine
from app.core.image_processor import ImageProcessor

app = FastAPI(title="Sonic-AI")

# Feature flag: Enable LangGraph workflow (v2 API)
USE_LANGGRAPH = os.getenv("USE_LANGGRAPH", "false").lower() == "true"

# Mount v2 API routes if enabled
if USE_LANGGRAPH:
    from app.api.routes import router as v2_router
    app.include_router(v2_router)
    print("✅ LangGraph v2 API enabled at /api/v2")

# Global config
config = ConfigManager()

# Static files & Folders
UPLOADS_DIR = "uploads"
PROCESSED_DIR = "app/static/processed"
THUMBNAILS_DIR = "app/static/processed/thumbnails"
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)
os.makedirs(THUMBNAILS_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Initialize engines with config
video_proc = VideoProcessor(config=config)
vector_eng = VectorEngine(config=config)
audio_proc = AudioProcessor()
editor = Editor(config=config)
llm_eng = LLMEngine(config=config)
image_proc = ImageProcessor()


def reload_engines():
    """Re-initialize engines after settings change."""
    global video_proc, vector_eng, editor, llm_eng, config
    config.load()
    video_proc = VideoProcessor(config=config)
    vector_eng = VectorEngine(config=config)
    editor = Editor(config=config)
    llm_eng = LLMEngine(config=config)

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

async def process_video_agent(audio_path, video_paths, intent, manual_lyrics=None, allow_ai_gen=False, video_description=None):
    global progress_logs
    progress_logs = []
    
    try:
        # 1. Analyze Audio
        await log_progress("🎵 [STEP 1/4] 音频深度解析开始...")
        if manual_lyrics:
            await log_progress("📝 检测到用户手动输入歌词，正在开启【参考对齐】模式以提升识别精度...")
        
        await log_progress("📡 正在调用 Whisper 进行语义识别...")
        raw_segments = audio_proc.transcribe_with_timestamps(audio_path)
        
        # 优化点 1：如果用户提供了手动歌词，利用 Qwen 进行精准校准对齐
        if manual_lyrics:
            await log_progress("🧩 正在利用 LLM 将【精准歌词】与时间戳进行对齐校准...")
            try:
                raw_segments = await llm_eng.align_lyrics(raw_segments, manual_lyrics)
                await log_progress("✅ 歌词校准完成，准确度极大提升。")
            except Exception as e:
                await log_progress(f"⚠️ 歌词校准失败，回退到原始识别结果: {e}")
        
        # 优化点 2：核心逻辑优化：镜头不要太碎，且必须填满时间轴
        await log_progress("🧬 正在进行【长镜头策略】分析：正在将短句合并为理想的视觉单元...")
        
        # 稳健性处理：确保 raw_segments 是列表格式
        if isinstance(raw_segments, dict):
            # 兼容模型返回 {"0": ..., "1": ...} 的情况
            try:
                raw_segments = [v for k, v in sorted(raw_segments.items(), key=lambda x: int(x[0]) if str(x[0]).isdigit() else 0)]
            except:
                raw_segments = list(raw_segments.values())

        segments = []
        if raw_segments and len(raw_segments) > 0:
            curr = raw_segments[0].copy()
            for i in range(1, len(raw_segments)):
                s = raw_segments[i]
                # 检查两个分段之间是否有巨大空隙，如果有，把空隙合并到前一段或后一段
                # 确保时间轴是连续的
                if s['start'] > curr['end']:
                    curr['end'] = s['start'] 
                
                curr['text'] += " " + s['text']
                curr['end'] = s['end']
                
                # 合并到 10s 以上或者已经是最后一个
                if (curr['end'] - curr['start']) >= 10.0:
                    segments.append(curr)
                    curr = s.copy() if i < len(raw_segments) - 1 else None
            
            if curr:
                # 补全最后一段到音频结尾
                audio_len = librosa.get_duration(path=audio_path)
                curr['end'] = max(curr['end'], audio_len)
                segments.append(curr)

        await log_progress(f"📊 音频分析完成: 已生成 {len(segments)} 个视觉序列，准备匹配素材。")
        
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
                    kf_paths = video_proc.extract_keyframes(
                        clip["path"], 
                        clip.get("start", 0), 
                        clip.get("end", 9999), 
                        num_frames=3
                    )
                    
                    if kf_paths:
                        # [Coarse Phase] 仅计算 CLIP 向量，成本为 0
                        avg_vec = vector_eng.encode_images_and_average(kf_paths)
                        if avg_vec is not None:
                            vector_eng.add_to_index(avg_vec, clip)
                        
                        # 清理采样帧
                        for kp in kf_paths:
                            try: os.remove(kp)
                            except: pass
                    
                    if (i + 1) % FEATURE_BATCH_SIZE == 0:
                        await log_progress(f"   - 已处理 {i+1}/{total_clips} 个镜头 (CLIP 快速索引)...")
                        gc.collect()
                        
                all_clips.extend(clips)
                
        # Final memory stats
        stats = vector_eng.get_memory_stats()
        await log_progress(f"✅ 素材库构建完成，当前索引容量: {stats['vectors_count']} 个语义片段")
        
        # 3. Creative Matching (Qwen Powered)
        if video_description:
            await log_progress(f"📖 已注入剧本背景知识: {video_description[:100]}...")
            
        await log_progress("🔎 正在扫描素材库全局调性，为 AI 导演提供构思参考...")
        library_context = None
        representative_frames = []
        
        # 优化采样：从所有视频中均匀各取 3 帧，直到满 15 帧
        for v_item in video_paths:
            if isinstance(v_item, str) and v_item.lower().endswith(('.mp4', '.mov', '.avi')):
                v_info = video_proc.get_video_info(v_item)
                # 避开片头片尾，在中间 10%-90% 区域采样
                frames = video_proc.extract_keyframes(v_item, v_info['duration']*0.1, v_info['duration']*0.9, num_frames=3)
                representative_frames.extend(frames)
            if len(representative_frames) >= 15: break
            
        if representative_frames:
            library_context = await llm_eng.analyze_video_library(representative_frames)
            await log_progress(f"📋 素材库视觉风格: {library_context}")
            # 清理采样帧
            for f in representative_frames:
                try: os.remove(f)
                except: pass

        await log_progress("🧠 [STEP 3/4] 阿里云 Qwen 导演系统启动，正在编排分镜...")
        final_sequence = []
        used_clip_paths = set()
        clip_usage_count = {} # 新增：全局片段使用计数器，用于最大化素材多样性
        
        
        # 3. Creative Matching (Qwen Powered)
        if video_description:
            await log_progress(f"📖 已注入剧本背景知识: {video_description[:100]}...")
            
        await log_progress("🔎 正在扫描素材库全局调性，为 AI 导演提供构思参考...")
        representative_frames = []
        for v_item in video_paths:
            if isinstance(v_item, str) and v_item.lower().endswith(('.mp4', '.mov', '.avi')):
                v_info = video_proc.get_video_info(v_item)
                frames = video_proc.extract_keyframes(v_item, v_info['duration']*0.1, v_info['duration']*0.9, num_frames=3)
                representative_frames.extend(frames)
            if len(representative_frames) >= 15: break
            
        library_context = None
        if representative_frames:
            library_context = await llm_eng.analyze_video_library(representative_frames)
            await log_progress(f"📋 素材库视觉风格: {library_context}")
            for f in representative_frames:
                try: os.remove(f)
                except: pass

        await log_progress("🧠 [STEP 3/4] ⚡️ 导演系统已升级为【多核并发模式】，正在加速编排分镜...")
        
        # --- 并发任务定义 ---
        concurrent_workers = config.get("advanced", "concurrent_workers", 5)
        sem = asyncio.Semaphore(concurrent_workers)
        
        async def process_single_segment_task(idx, seg):
            async with sem:
                lyric_text = seg['text'].strip()
                if not lyric_text: return None
                
                # 实时进度反馈
                await log_progress(f"🧠 [Agent-{idx+1}] 正在构思视觉脚本与检索策略...")
                
                # 1. LLM 脚本生成 (IO Bound)
                script = await llm_eng.generate_visual_script(
                    lyric_text, intent, library_context=library_context, video_description=video_description
                )
                
                # 2. 向量粗筛 (Fast)
                search_query = script['visual_prompt']
                search_top_k = config.get("advanced", "vector_search_top_k", 40)
                raw_matches = vector_eng.search(search_query, top_k=search_top_k)
                
                # 3. 延迟语义富化 -【优化：仅对 Top-8 进行深度分析，平衡效果与速度】
                candidate_pool = raw_matches[:8]
                enriched_matches = []
                
                await log_progress(f"🧪 [Agent-{idx+1}] 正在对前 {len(candidate_pool)} 个高潜力素材进行深度语义理解...")
                
                for m in candidate_pool:
                    idx_id = m.get("_id")
                    master_meta = None
                    try:
                        master_meta = vector_eng.clips_metadata[idx_id].get("metadata")
                    except: pass

                    if not master_meta:
                        try:
                            kf_paths = video_proc.extract_keyframes(m['path'], m.get('start', 0), m.get('end', 0), num_frames=1)
                            if kf_paths:
                                semantic_info = await llm_eng.analyze_scene_semantics(kf_paths[0])
                                master_meta = {
                                    "action": semantic_info.get("action", ""),
                                    "mood": semantic_info.get("mood", ""),
                                    "objects": semantic_info.get("objects", []),
                                    "description": semantic_info.get("description", "")
                                }
                                vector_eng.clips_metadata[idx_id]["metadata"] = master_meta
                                try: os.remove(kf_paths[0])
                                except: pass
                        except: pass
                    m["metadata"] = master_meta
                    enriched_matches.append(m)

                # 4. LLM 重排打分 (IO Bound)
                matches = await llm_eng.rerank_clips(search_query, enriched_matches)
                await log_progress(f"✅ [Agent-{idx+1}] 逻辑编排完成。")
                
                return {
                    "idx": idx,
                    "seg": seg,
                    "script": script,
                    "matches": matches,
                    "search_query": search_query
                }

        # 启动所有并发任务
        tasks = [process_single_segment_task(i, s) for i, s in enumerate(segments)]
        results = await asyncio.gather(*tasks)
        results = [r for r in results if r is not None]
        # 排序保证顺序一致性
        results.sort(key=lambda x: x['idx'])

        # --- 汇总结果与素材分配 (串行) ---
        final_sequence = []
        clip_usage_count = {}

        for res in results:
            idx = res['idx']
            seg = res['seg']
            script = res['script']
            matches = res['matches']
            search_query = res['search_query']
            lyric_text = seg['text']
            
            await log_progress(f"🎬 已完成第 {idx+1} 段的分镜逻辑构思...")

            if matches:
                target_duration = seg['end'] - seg['start']
                remaining_duration = target_duration
                
                # 策略：AI 生成兜底
                fallback_score = config.get("advanced", "ai_fallback_score", 0.22)
                if matches[0]['score'] < fallback_score and allow_ai_gen:
                    await log_progress(f"⚠️ 匹配度低 ({matches[0]['score']:.2f})，正在并发执行 AI 生成...")
                    ai_video_path = await generate_ai_video(search_query)
                    if ai_video_path:
                        final_sequence.append({
                            "path": ai_video_path,
                            "type": "video",
                            "score": 0.99,
                            "target_duration": target_duration,
                            "text": lyric_text
                        })
                        continue

                # 分配素材：优先选使用次数少的
                def get_usage(m):
                    return clip_usage_count.get((m['path'], m.get('start', 0)), 0)
                
                available_matches = sorted(matches, key=lambda x: (get_usage(x)))
                
                match_idx = 0
                while remaining_duration > 0.1 and match_idx < len(available_matches):
                    m = available_matches[match_idx].copy()
                    clip_dur = m['duration']
                    use_dur = min(clip_dur, remaining_duration)
                    
                    m['target_duration'] = use_dur
                    m['text'] = lyric_text if remaining_duration >= target_duration else ""
                    
                    final_sequence.append(m)
                    
                    cid = (m['path'], m.get('start', 0))
                    clip_usage_count[cid] = clip_usage_count.get(cid, 0) + 1
                    remaining_duration -= use_dur
                    match_idx += 1
                
                # 结构化同步
                segment_payload = {
                    "type": "segment_data",
                    "id": idx + 1,
                    "text": lyric_text,
                    "start": seg['start'],
                    "end": seg['end'],
                    "duration": f"{target_duration:.1f}s"
                }
                await manager.broadcast(f"JSON:{json.dumps(segment_payload)}")
            
        # [Strategy 2 Optimization] 优化：将深度语义描述和匹配理由渲染到画面，用于效果评估
        for m in final_sequence:
            meta = m.get("metadata", {})
            tag_text = ""
            
            if isinstance(meta, dict):
                # 调优标签显示内容
                # 1. 匹配理由 (最重要，告诉用户 AI 为什么选它)
                reason = m.get("rank_reason", "Common Match")
                score = m.get("score", 0)
                
                # 2. 素材本身的英文语义 (验证召回效果)
                desc = meta.get("description", "No description")
                
                # 3. 核心标签
                action = meta.get("action", "")
                mood = meta.get("mood", "")
                
                tag_text = f"🎯 Reason: {reason}\n"
                tag_text += f"📊 Score: {score:.2f} | Action: {action} | Mood: {mood}\n"
                tag_text += f"📷 Meta: {desc[:60]}..."
            
            if not tag_text.strip():
                tag_text = f"File: {os.path.basename(m.get('path', 'unknown'))}"
                
            m['visual_description'] = tag_text
            # 记录日志
            await log_progress(f"🏷️ Rendering tag for clip: {os.path.basename(m.get('path', ''))}")

        # 4. Assembly
        await log_progress("🎞️ [STEP 4/4] 进入后期合成阶段...")
        await log_progress("⚙️ 正在执行 MoviePy 视频流混放、音轨对齐与高性能渲染并行导出...")
        final_video_path = editor.assemble(final_sequence, audio_path)
        
        await log_progress("✨ 制作任务圆满完成！最终成片已生成。")
        
    except Exception as e:
        error_msg = f"❌ 任务中断: 系统遇到不可恢复的错误 -> {str(e)}"
        await log_progress(error_msg)
        traceback.print_exc()
    finally:
        # Cleanup: Reset vector engine and free memory
        await log_progress("🧹 正在释放内存资源...")
        vector_eng.reset()
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
    video_description: str = Form(None),
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
    background_tasks.add_task(process_video_agent, audio_path, video_paths, intent, lyrics, allow_ai_gen, video_description)
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

@app.post("/debug/run_test")
async def run_test_endpoint(
    background_tasks: BackgroundTasks,
    data: dict
):
    """
    Debug endpoint to run the agent with local absolute paths.
    Expected data: {
        "audio_path": "...",
        "video_paths": ["...", "..."],
        "intent": "...",
        "lyrics": "...",
        "video_description": "...",
        "allow_ai_gen": false
    }
    """
    audio_path = data.get("audio_path")
    video_paths = data.get("video_paths", [])
    intent = data.get("intent", "默认剪辑意图")
    lyrics = data.get("lyrics")
    video_description = data.get("video_description")
    allow_ai_gen = data.get("allow_ai_gen", False)

    # Validate paths if provided
    if audio_path and not os.path.exists(audio_path):
        return JSONResponse(status_code=400, content={"message": f"Audio path not found: {audio_path}"})
    
    for vp in video_paths:
        if isinstance(vp, str) and not os.path.exists(vp):
            return JSONResponse(status_code=400, content={"message": f"Video path not found: {vp}"})

    background_tasks.add_task(
        process_video_agent, 
        audio_path, 
        video_paths, 
        intent, 
        lyrics, 
        allow_ai_gen, 
        video_description
    )
    return {"status": "debug_processing", "message": "Test task started with local paths"}

@app.get("/api/settings")
async def get_settings():
    """Return current settings with API keys masked."""
    return config.to_safe_dict()


@app.post("/api/settings")
async def save_settings(data: dict):
    """Save settings and reload engines."""
    for section in ("api_keys", "models", "advanced"):
        if section in data:
            config.update_section(section, data[section])
    reload_engines()
    return {"status": "ok", "config": config.to_safe_dict()}


@app.get("/settings", response_class=HTMLResponse)
async def settings_page():
    """Redirect to main page (settings is a modal)."""
    with open("app/static/index.html", "r") as f:
        return f.read()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
