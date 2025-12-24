from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks
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

app = FastAPI(title="Director AI Agent")

# Static files & Folders
UPLOADS_DIR = "uploads"
PROCESSED_DIR = "app/static/processed"
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Initialize engines
video_proc = VideoProcessor()
vector_eng = VectorEngine()
audio_proc = AudioProcessor()
editor = Editor()

progress_logs = []

async def process_video_agent(audio_path, video_paths, intent):
    global progress_logs
    progress_logs = []
    
    try:
        # 1. Analyze Audio
        progress_logs.append("🔍 正在解析音频与歌词...")
        segments = audio_proc.transcribe_with_timestamps(audio_path)
        beats = audio_proc.analyze_beats(audio_path)
        progress_logs.append(f"📊 识别到 {len(segments)} 段歌词，BPM: {beats['tempo']:.1f}")
        
        # 2. Process Videos (Shot detection & Embedding)
        progress_logs.append("🎥 正在拉片并分析视频素材...")
        all_clips = []
        for v_path in video_paths:
            clips = video_proc.split_scenes(v_path)
            for clip in clips:
                kf_path = video_proc.extract_keyframe(clip["path"])
                if kf_path:
                    vec = vector_eng.encode_image(kf_path)
                    vector_eng.add_to_index(vec, clip)
            all_clips.extend(clips)
        progress_logs.append(f"✅ 素材理解完成，共入库 {len(vector_eng.vectors)} 个片段")
        
        # 3. Creative Matching
        progress_logs.append("🤖 LLM 正在编排分镜脚本...")
        final_sequence = []
        for seg in segments:
            lyric_text = seg['text']
            # Intent mapping: 模拟 LLM 将感性歌词转化为视觉描述词
            # 这里的 logic 会展示在前端
            semantic_translation = f"映射意境: 在'{intent}'主题下，将'{lyric_text}'转化为视觉特征..."
            
            search_query = f"{lyric_text} {intent}"
            matches = vector_eng.search(search_query, top_k=1)
            
            if matches:
                match = matches[0]
                # 记录该片段应有的时长（歌词段长度）
                match['target_duration'] = seg['end'] - seg['start']
                final_sequence.append(match)
                # 重点：展示匹配逻辑
                detail_log = {
                    "type": "match",
                    "lyric": lyric_text,
                    "reasoning": semantic_translation,
                    "clip": os.path.basename(match['path']),
                    "score": round(match['score'], 2)
                }
                progress_logs.append(f"🔍 匹配逻辑: 歌词[{lyric_text}] -> {semantic_translation} -> 命中[{detail_log['clip']}] (置信度: {detail_log['score']})")
            
        # 4. Assembly
        progress_logs.append("🎞️ 正在合成最终成片...")
        final_video_path = editor.assemble(final_sequence, audio_path)
        
        progress_logs.append("✨ 制作完成！")
        
    except Exception as e:
        progress_logs.append(f"❌ 运行失败: {str(e)}")

@app.get("/", response_class=HTMLResponse)
async def get_index():
    with open("app/static/index.html", "r") as f:
        return f.read()

@app.post("/upload")
async def upload_files(
    background_tasks: BackgroundTasks,
    audio: UploadFile = File(...),
    videos: list[UploadFile] = File(...),
    intent: str = Form(...)
):
    audio_path = os.path.join(UPLOADS_DIR, audio.filename)
    with open(audio_path, "wb") as f:
        shutil.copyfileobj(audio.file, f)
    
    video_paths = []
    for video in videos:
        v_path = os.path.join(UPLOADS_DIR, video.filename)
        with open(v_path, "wb") as f:
            shutil.copyfileobj(video.file, f)
        video_paths.append(v_path)
    
    background_tasks.add_task(process_video_agent, audio_path, video_paths, intent)
    
    return {"message": "Processing started", "task_id": "123"}

@app.get("/progress")
async def get_progress():
    return {"logs": progress_logs}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
