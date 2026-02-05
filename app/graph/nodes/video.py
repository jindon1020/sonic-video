"""
Video Processing Nodes for LangGraph

These nodes handle video scene detection, feature extraction, and indexing.
"""

import os
import gc
import cv2
from typing import Dict, Any

from app.graph.state import VideoEditState
from app.core.video_processor import VideoProcessor
from app.core.image_processor import ImageProcessor
from app.core.vector_engine import VectorEngine
from app.providers.factory import LLMProviderFactory


async def log_progress(state: VideoEditState, message: str):
    """Helper to log progress to state and websocket."""
    print(f" LOG: {message}")
    state["progress"].append(message)

    manager = state.get("_websocket_manager")
    if manager:
        try:
            await manager.broadcast(message)
        except:
            pass


async def split_scenes_node(state: VideoEditState) -> Dict[str, Any]:
    """
    Node: Split videos into scenes and process images/live photos.

    Input from state:
        - video_paths: List of video/image/live photo paths
        - _config: ConfigManager instance
        - _video_processor: VideoProcessor instance (or create)
        - _image_processor: ImageProcessor instance (or create)

    Output to state:
        - video_clips: List of clip metadata
    """
    await log_progress(state, "🎬 [STEP 2/4] 素材库特征工程启动...")

    # Get or create processors
    config = state["_config"]
    video_proc = state.get("_video_processor")
    if not video_proc:
        video_proc = VideoProcessor(config=config)
        state["_video_processor"] = video_proc

    image_proc = state.get("_image_processor")
    if not image_proc:
        image_proc = ImageProcessor()
        state["_image_processor"] = image_proc

    all_clips = []
    video_paths = state["video_paths"]

    for v_item in video_paths:
        # Handle different media types
        if isinstance(v_item, dict):
            if v_item['type'] == 'image':
                # Static image - convert to video with Ken Burns effect
                img_path = v_item['path']
                img_name = os.path.basename(img_path)
                await log_progress(state, f"🖼️ 正在将图片 {img_name} 转换为动态视频...")

                try:
                    video_path = image_proc.create_video_from_image(
                        img_path,
                        duration=5.0,
                        add_motion=True
                    )
                    clip = {
                        "path": video_path,
                        "start": 0,
                        "end": 5.0,
                        "duration": 5.0,
                        "type": "image",
                        "_image_path": img_path  # Store for embedding later
                    }
                    all_clips.append(clip)
                    await log_progress(state, f"✅ 图片 {img_name} 已转换为动态视频片段")
                except Exception as e:
                    await log_progress(state, f"⚠️ 图片处理失败: {str(e)}")

            elif v_item['type'] == 'live_photo':
                # Apple Live Photo - extract motion video
                img_path = v_item['image']
                mov_path = v_item['video']
                base_name = os.path.basename(img_path).split('.')[0]
                await log_progress(state, f"📱 检测到 Live Photo: {base_name}，正在提取动态内容...")

                try:
                    video_path = image_proc.process_live_photo(img_path, mov_path)
                    # Get duration
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
                        "type": "live_photo",
                        "_image_path": img_path  # Store for embedding later
                    }
                    all_clips.append(clip)
                    await log_progress(state, f"✅ Live Photo {base_name} 已处理完成 (时长: {duration:.1f}s)")
                except Exception as e:
                    await log_progress(state, f"⚠️ Live Photo 处理失败: {str(e)}")
        else:
            # Regular video file
            v_path = v_item
            v_name = os.path.basename(v_path)

            # Get video info
            v_info = video_proc.get_video_info(v_path)
            await log_progress(
                state,
                f"🎞️ 正在对视频 {v_name} 进行镜头切分 "
                f"(大小: {v_info['size_mb']:.1f}MB, 时长: {v_info['duration']:.1f}s)..."
            )

            clips = video_proc.split_scenes(v_path)
            all_clips.extend(clips)

            await log_progress(state, f"✅ {v_name} 已完成场景切分，生成 {len(clips)} 个片段")

    await log_progress(state, f"📊 场景切分完成，共生成 {len(all_clips)} 个视频片段")

    return {"video_clips": all_clips}


async def build_vector_index_node(state: VideoEditState) -> Dict[str, Any]:
    """
    Node: Build CLIP vector index for all clips.

    Input from state:
        - video_clips: List of clip metadata
        - _config: ConfigManager instance
        - _video_processor: VideoProcessor instance
        - _vector_engine: VectorEngine instance (or create)

    Output to state:
        - _vector_engine: Populated vector engine
    """
    await log_progress(state, "🧊 正在构建 CLIP 向量索引...")

    # Get or create vector engine
    config = state["_config"]
    vector_eng = state.get("_vector_engine")
    if not vector_eng:
        vector_eng = VectorEngine(config=config)
        state["_vector_engine"] = vector_eng

    video_proc = state["_video_processor"]
    video_clips = state["video_clips"]

    FEATURE_BATCH_SIZE = 10
    total_clips = len(video_clips)

    for i, clip in enumerate(video_clips):
        # Check if this is an image/live photo with stored image path
        if "_image_path" in clip:
            # Use the image directly for better quality
            img_path = clip["_image_path"]
            if img_path.lower().endswith(('.heic', '.heif')):
                image_proc = state["_image_processor"]
                img_path = image_proc.convert_heic_to_jpg(img_path)

            vec = vector_eng.encode_image(img_path)
            if vec is not None:
                vector_eng.add_to_index(vec, clip)
        else:
            # Regular video clip - extract keyframes
            kf_paths = video_proc.extract_keyframes(
                clip["path"],
                clip.get("start", 0),
                clip.get("end", 9999),
                num_frames=3
            )

            if kf_paths:
                # Calculate CLIP embedding
                avg_vec = vector_eng.encode_images_and_average(kf_paths)
                if avg_vec is not None:
                    vector_eng.add_to_index(avg_vec, clip)

                # Clean up keyframes
                for kp in kf_paths:
                    try:
                        os.remove(kp)
                    except:
                        pass

        if (i + 1) % FEATURE_BATCH_SIZE == 0:
            await log_progress(state, f"   - 已处理 {i+1}/{total_clips} 个镜头 (CLIP 快速索引)...")
            gc.collect()

    stats = vector_eng.get_memory_stats()
    await log_progress(state, f"✅ 向量索引构建完成，索引容量: {stats['vectors_count']} 个语义片段")

    return {"_vector_engine": vector_eng}


async def analyze_library_node(state: VideoEditState) -> Dict[str, Any]:
    """
    Node: Analyze material library to generate global visual context.

    Input from state:
        - video_paths: Original video paths
        - video_description: Optional user description
        - _config: ConfigManager instance
        - _video_processor: VideoProcessor instance
        - _llm_provider: LLMProvider instance (or create)

    Output to state:
        - library_context: Visual summary of the material library
    """
    video_description = state.get("video_description")
    if video_description:
        await log_progress(state, f"📖 已注入剧本背景知识: {video_description[:100]}...")

    await log_progress(state, "🔎 正在扫描素材库全局调性，为 AI 导演提供构思参考...")

    # Get or create LLM provider
    llm_provider = state.get("_llm_provider")
    if not llm_provider:
        config = state["_config"]
        llm_provider = LLMProviderFactory.from_config(config, task="library_analysis")
        state["_llm_provider"] = llm_provider

    video_proc = state["_video_processor"]
    representative_frames = []

    # Sample frames from videos (uniform sampling, max 15 frames)
    video_paths = state["video_paths"]
    for v_item in video_paths:
        if isinstance(v_item, str) and v_item.lower().endswith(('.mp4', '.mov', '.avi')):
            v_info = video_proc.get_video_info(v_item)
            # Sample from middle 10%-90% region
            frames = video_proc.extract_keyframes(
                v_item,
                v_info['duration'] * 0.1,
                v_info['duration'] * 0.9,
                num_frames=3
            )
            representative_frames.extend(frames)
        if len(representative_frames) >= 15:
            break

    library_context = None
    if representative_frames:
        try:
            # Use LLM provider's multi-image analysis
            prompt = (
                "你是一个资深的素材库分析师。请分析以下这组来自同一视频（或素材库）的关键采样帧，"
                "并总结出该素材库的【核心视觉元素】、【主要场景类型】、【画面主色调】以及【动作风格】。"
                "这将作为后续 AI 剪辑导演的参考。请用一两句话简练概括。"
            )
            library_context = await llm_provider.analyze_multi_images(representative_frames, prompt)
            await log_progress(state, f"📋 素材库视觉风格: {library_context}")
        except Exception as e:
            await log_progress(state, f"⚠️ 素材库分析失败: {e}")
            library_context = "Analysis failed, please use general cinematic style."

        # Clean up frames
        for f in representative_frames:
            try:
                os.remove(f)
            except:
                pass

    return {"library_context": library_context}
