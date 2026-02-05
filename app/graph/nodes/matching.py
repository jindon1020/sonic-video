"""
Matching Nodes for LangGraph

These nodes handle AI-powered clip matching, allocation, and fallback generation.
"""

import os
import json
import asyncio
import requests
from typing import Dict, Any, List
from dashscope.aigc.video_synthesis import VideoSynthesis

from app.graph.state import VideoEditState
from app.providers.factory import LLMProviderFactory
from app.providers.qwen import QwenProvider


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


async def match_segments_node(state: VideoEditState) -> Dict[str, Any]:
    """
    Node: Match audio segments with video clips using AI director system.

    This is the most complex node - it performs parallel processing of segments,
    generating visual scripts, searching vectors, enriching semantics, and reranking.

    Input from state:
        - aligned_segments: List of audio segments with text
        - intent: User's creative intent
        - library_context: Visual summary of material library
        - video_description: Optional video description
        - _config: ConfigManager instance
        - _vector_engine: VectorEngine instance
        - _llm_provider: LLMProvider instance
        - _video_processor: VideoProcessor instance

    Output to state:
        - segment_matches: List of matches for each segment
    """
    await log_progress(state, "🧠 [STEP 3/4] ⚡️ 导演系统已升级为【多核并发模式】，正在加速编排分镜...")

    # Get dependencies
    config = state["_config"]
    segments = state["aligned_segments"]
    intent = state["intent"]
    library_context = state.get("library_context")
    video_description = state.get("video_description")
    vector_eng = state["_vector_engine"]
    video_proc = state["_video_processor"]

    # Get or create LLM provider
    llm_provider = state.get("_llm_provider")
    if not llm_provider:
        llm_provider = LLMProviderFactory.from_config(config, task="visual_script")
        state["_llm_provider"] = llm_provider

    # Concurrent processing setup
    concurrent_workers = config.get("advanced", "concurrent_workers", 5)
    sem = asyncio.Semaphore(concurrent_workers)

    async def process_single_segment_task(idx: int, seg: dict):
        """Process a single segment with AI director logic."""
        async with sem:
            lyric_text = seg['text'].strip()
            if not lyric_text:
                return None

            await log_progress(state, f"🧠 [Agent-{idx+1}] 正在构思视觉脚本与检索策略...")

            try:
                # 1. LLM Script Generation (IO Bound)
                if isinstance(llm_provider, QwenProvider):
                    script = await llm_provider.generate_visual_script(
                        lyric_text,
                        intent,
                        library_context=library_context,
                        video_description=video_description
                    )
                else:
                    # Fallback for other providers
                    prompt = f"Convert this lyric into visual search terms: {lyric_text}\nIntent: {intent}"
                    script_text = await llm_provider.generate_text(prompt)
                    script = {"visual_prompt": script_text, "reasoning": "Generated"}

                # 2. Vector Search (Fast)
                search_query = script['visual_prompt']
                search_top_k = config.get("advanced", "vector_search_top_k", 40)
                raw_matches = vector_eng.search(search_query, top_k=search_top_k)

                # 3. Semantic Enrichment (Top-8 only for speed/cost balance)
                candidate_pool = raw_matches[:8]
                enriched_matches = []

                await log_progress(
                    state,
                    f"🧪 [Agent-{idx+1}] 正在对前 {len(candidate_pool)} 个高潜力素材进行深度语义理解..."
                )

                for m in candidate_pool:
                    idx_id = m.get("_id")
                    master_meta = None

                    # Check if metadata already cached
                    try:
                        master_meta = vector_eng.clips_metadata[idx_id].get("metadata")
                    except:
                        pass

                    # Generate metadata if not cached
                    if not master_meta:
                        try:
                            kf_paths = video_proc.extract_keyframes(
                                m['path'],
                                m.get('start', 0),
                                m.get('end', 0),
                                num_frames=1
                            )
                            if kf_paths:
                                # Use provider's scene analysis
                                if isinstance(llm_provider, QwenProvider):
                                    semantic_info = await llm_provider.analyze_scene_semantics(kf_paths[0])
                                else:
                                    # Fallback
                                    semantic_info = {
                                        "action": "Unknown",
                                        "mood": "Neutral",
                                        "objects": [],
                                        "description": "Scene analysis not available"
                                    }

                                master_meta = {
                                    "action": semantic_info.get("action", ""),
                                    "mood": semantic_info.get("mood", ""),
                                    "objects": semantic_info.get("objects", []),
                                    "description": semantic_info.get("description", "")
                                }

                                # Cache metadata
                                vector_eng.clips_metadata[idx_id]["metadata"] = master_meta

                                # Clean up
                                try:
                                    os.remove(kf_paths[0])
                                except:
                                    pass
                        except:
                            pass

                    m["metadata"] = master_meta
                    enriched_matches.append(m)

                # 4. LLM Reranking (IO Bound)
                if isinstance(llm_provider, QwenProvider):
                    matches = await llm_provider.rerank_clips(search_query, enriched_matches)
                else:
                    # Simple fallback - keep original order
                    matches = enriched_matches

                await log_progress(state, f"✅ [Agent-{idx+1}] 逻辑编排完成。")

                return {
                    "idx": idx,
                    "seg": seg,
                    "script": script,
                    "matches": matches,
                    "search_query": search_query
                }

            except Exception as e:
                await log_progress(state, f"❌ [Agent-{idx+1}] 处理失败: {str(e)}")
                return None

    # Launch all concurrent tasks
    tasks = [process_single_segment_task(i, s) for i, s in enumerate(segments)]
    results = await asyncio.gather(*tasks)
    results = [r for r in results if r is not None]

    # Sort to ensure order consistency
    results.sort(key=lambda x: x['idx'])

    await log_progress(state, f"✅ 所有 {len(results)} 个片段的分镜编排已完成")

    return {"segment_matches": results}


async def ai_fallback_node(state: VideoEditState) -> Dict[str, Any]:
    """
    Node: Generate AI video for segments with poor matches.

    Input from state:
        - segment_matches: Results from matching
        - allow_ai_gen: Whether AI generation is enabled
        - _config: ConfigManager instance

    Output to state:
        - segment_matches: Updated with AI-generated videos
    """
    await log_progress(state, "🎨 正在检查是否需要 AI 生成兜底...")

    config = state["_config"]
    segment_matches = state.get("segment_matches", [])
    fallback_score = config.get("advanced", "ai_fallback_score", 0.22)

    # Candidate models for video generation
    candidate_models = [
        "wan2.1-t2v-14b",
        "wan2.1-t2v-1.3b",
        "wanx2.1-t2v-plus",
        "wanx2.1-t2v-turbo",
        "wanx-v1",
        "video-generation"
    ]

    async def generate_ai_video(prompt: str, duration_sec: float = 5.0) -> str:
        """Generate AI video using DashScope."""
        for model_name in candidate_models:
            try:
                await log_progress(state, f"🎨 正在尝试调用模型 [{model_name}] 生成视频...")

                rsp = VideoSynthesis.call(
                    model=model_name,
                    prompt=prompt,
                    size="1280*720"
                )

                if rsp.status_code == 200:
                    task_id = rsp.output.task_id
                    await log_progress(state, f"⏳ [{model_name}] 任务提交成功 (Task: {task_id})，等待渲染...")

                    # Wait for completion
                    status = VideoSynthesis.wait(rsp)
                    if status.status_code == 200:
                        video_url = status.output.video_url
                        await log_progress(state, "✨ AI 视频生成成功，正在下载...")

                        # Download video
                        r = requests.get(video_url)
                        file_name = f"ai_gen_{task_id}.mp4"
                        save_path = os.path.join("uploads", file_name)
                        with open(save_path, 'wb') as f:
                            f.write(r.content)

                        return save_path
                    else:
                        await log_progress(state, f"❌ [{model_name}] 渲染失败: {status.message}")
                else:
                    if "Model not exist" in rsp.message:
                        continue  # Try next model
                    await log_progress(state, f"❌ [{model_name}] 调用报错: {rsp.message}")

            except Exception as e:
                await log_progress(state, f"❌ [{model_name}] 异常: {str(e)}")

        await log_progress(state, "❌ 所有 AI 模型均尝试失败，无法生成视频。")
        return None

    # Check each segment match
    for match in segment_matches:
        matches = match.get("matches", [])
        if matches and matches[0].get('score', 0) < fallback_score:
            search_query = match.get("search_query", "")
            seg = match.get("seg", {})

            await log_progress(
                state,
                f"⚠️ 片段匹配度低 ({matches[0].get('score', 0):.2f})，正在执行 AI 生成..."
            )

            ai_video_path = await generate_ai_video(search_query)
            if ai_video_path:
                # Replace matches with AI-generated video
                target_duration = seg['end'] - seg['start']
                match["matches"] = [{
                    "path": ai_video_path,
                    "type": "ai_generated",
                    "score": 0.99,
                    "duration": target_duration,
                    "target_duration": target_duration,
                    "text": seg['text']
                }]
                await log_progress(state, "✅ AI 生成成功，已替换原匹配结果")

    return {"segment_matches": segment_matches}


async def allocate_clips_node(state: VideoEditState) -> Dict[str, Any]:
    """
    Node: Allocate clips to segments, prioritizing diversity.

    Input from state:
        - segment_matches: Matches for each segment
        - _clip_usage_count: Clip usage tracking

    Output to state:
        - final_sequence: Final rendering sequence
    """
    await log_progress(state, "📋 正在进行素材分配，优化片段多样性...")

    segment_matches = state.get("segment_matches", [])
    clip_usage_count = state.get("_clip_usage_count", {})

    final_sequence = []

    for res in segment_matches:
        idx = res['idx']
        seg = res['seg']
        script = res.get('script', {})
        matches = res.get('matches', [])
        lyric_text = seg['text']

        await log_progress(state, f"🎬 正在分配第 {idx+1} 段的素材...")

        if matches:
            target_duration = seg['end'] - seg['start']
            remaining_duration = target_duration

            # Sort by usage count (prefer less-used clips)
            def get_usage(m):
                return clip_usage_count.get((m['path'], m.get('start', 0)), 0)

            available_matches = sorted(matches, key=lambda x: get_usage(x))

            match_idx = 0
            while remaining_duration > 0.1 and match_idx < len(available_matches):
                m = available_matches[match_idx].copy()
                clip_dur = m.get('duration', m.get('end', 0) - m.get('start', 0))
                use_dur = min(clip_dur, remaining_duration)

                m['target_duration'] = use_dur
                m['text'] = lyric_text if remaining_duration >= target_duration else ""

                final_sequence.append(m)

                # Update usage count
                cid = (m['path'], m.get('start', 0))
                clip_usage_count[cid] = clip_usage_count.get(cid, 0) + 1
                remaining_duration -= use_dur
                match_idx += 1

            # Send structured data to WebSocket
            segment_payload = {
                "type": "segment_data",
                "id": idx + 1,
                "text": lyric_text,
                "start": seg['start'],
                "end": seg['end'],
                "duration": f"{target_duration:.1f}s"
            }

            manager = state.get("_websocket_manager")
            if manager:
                try:
                    await manager.broadcast(f"JSON:{json.dumps(segment_payload)}")
                except:
                    pass

    # Add visual descriptions for debugging/evaluation
    for m in final_sequence:
        meta = m.get("metadata", {})
        tag_text = ""

        if isinstance(meta, dict):
            reason = m.get("rank_reason", "Common Match")
            score = m.get("score", 0)
            desc = meta.get("description", "No description")
            action = meta.get("action", "")
            mood = meta.get("mood", "")

            tag_text = f"🎯 Reason: {reason}\n"
            tag_text += f"📊 Score: {score:.2f} | Action: {action} | Mood: {mood}\n"
            tag_text += f"📷 Meta: {desc[:60]}..."

        if not tag_text.strip():
            tag_text = f"File: {os.path.basename(m.get('path', 'unknown'))}"

        m['visual_description'] = tag_text

    await log_progress(state, f"✅ 素材分配完成，共 {len(final_sequence)} 个片段待渲染")

    return {
        "final_sequence": final_sequence,
        "_clip_usage_count": clip_usage_count
    }


async def human_review_node(state: VideoEditState) -> Dict[str, Any]:
    """
    Node: Placeholder for human review (future feature).

    This node would trigger a NodeInterrupt for human-in-the-loop workflows.
    For now, it's a pass-through node.
    """
    await log_progress(state, "👤 人工审核节点（当前跳过）")
    return {}
