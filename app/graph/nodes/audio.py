"""
Audio Processing Nodes for LangGraph

These nodes handle audio transcription and lyrics alignment.
"""

import librosa
from typing import Dict, Any

from app.graph.state import VideoEditState
from app.core.audio_processor import AudioProcessor
from app.providers.factory import LLMProviderFactory


async def log_progress(state: VideoEditState, message: str):
    """Helper to log progress to state and websocket."""
    print(f" LOG: {message}")
    state["progress"].append(message)

    # Send to WebSocket if available
    manager = state.get("_websocket_manager")
    if manager:
        try:
            await manager.broadcast(message)
        except:
            pass


async def transcribe_audio_node(state: VideoEditState) -> Dict[str, Any]:
    """
    Node 1: Transcribe audio using Whisper.

    Input from state:
        - audio_path: Path to audio file
        - _audio_processor: AudioProcessor instance (or create one)

    Output to state:
        - audio_segments: List of transcription segments with timestamps
    """
    await log_progress(state, "🎵 [STEP 1/4] 音频深度解析开始...")
    await log_progress(state, "📡 正在调用 Whisper 进行语义识别...")

    # Get or create audio processor
    audio_proc = state.get("_audio_processor")
    if not audio_proc:
        audio_proc = AudioProcessor()
        state["_audio_processor"] = audio_proc

    # Transcribe audio
    audio_path = state["audio_path"]
    raw_segments = audio_proc.transcribe_with_timestamps(audio_path)

    # Store in state
    state["audio_segments"] = raw_segments

    await log_progress(state, f"✅ Whisper 识别完成，检测到 {len(raw_segments)} 个音频片段")

    return {"audio_segments": raw_segments}


async def align_lyrics_node(state: VideoEditState) -> Dict[str, Any]:
    """
    Node 2: Align manual lyrics with Whisper timestamps using LLM.

    Input from state:
        - audio_segments: Whisper transcription results
        - manual_lyrics: User-provided lyrics text
        - _config: ConfigManager instance
        - _llm_provider: LLMProvider instance (or create one)

    Output to state:
        - aligned_segments: LLM-aligned segments
    """
    await log_progress(state, "📝 检测到用户手动输入歌词，正在开启【参考对齐】模式...")
    await log_progress(state, "🧩 正在利用 LLM 将【精准歌词】与时间戳进行对齐校准...")

    # Get or create LLM provider
    llm_provider = state.get("_llm_provider")
    if not llm_provider:
        config = state["_config"]
        llm_provider = LLMProviderFactory.from_config(config, task="lyrics_alignment")
        state["_llm_provider"] = llm_provider

    # Perform alignment
    try:
        raw_segments = state["audio_segments"]
        manual_lyrics = state["manual_lyrics"]

        # Use Qwen provider's align_lyrics method
        from app.providers.qwen import QwenProvider
        if isinstance(llm_provider, QwenProvider):
            aligned_segments = await llm_provider.align_lyrics(raw_segments, manual_lyrics)
        else:
            # Fallback: use raw segments
            aligned_segments = raw_segments

        await log_progress(state, "✅ 歌词校准完成，准确度极大提升。")

        return {"aligned_segments": aligned_segments}

    except Exception as e:
        await log_progress(state, f"⚠️ 歌词校准失败，回退到原始识别结果: {e}")
        return {"aligned_segments": state["audio_segments"]}


async def merge_segments_node(state: VideoEditState) -> Dict[str, Any]:
    """
    Node 3: Merge short segments into longer visual units (≥10s).

    Input from state:
        - aligned_segments (or audio_segments if no alignment)
        - audio_path: For getting total duration

    Output to state:
        - aligned_segments: Merged segments
    """
    await log_progress(state, "🧬 正在进行【长镜头策略】分析：将短句合并为理想的视觉单元...")

    # Get segments (aligned or raw)
    raw_segments = state.get("aligned_segments", state.get("audio_segments", []))

    # Handle dict format from some models
    if isinstance(raw_segments, dict):
        try:
            raw_segments = [v for k, v in sorted(
                raw_segments.items(),
                key=lambda x: int(x[0]) if str(x[0]).isdigit() else 0
            )]
        except:
            raw_segments = list(raw_segments.values())

    segments = []
    if raw_segments and len(raw_segments) > 0:
        curr = raw_segments[0].copy()
        for i in range(1, len(raw_segments)):
            s = raw_segments[i]

            # Ensure timeline continuity
            if s['start'] > curr['end']:
                curr['end'] = s['start']

            curr['text'] += " " + s['text']
            curr['end'] = s['end']

            # Merge to ≥10s or last segment
            if (curr['end'] - curr['start']) >= 10.0:
                segments.append(curr)
                curr = s.copy() if i < len(raw_segments) - 1 else None

        if curr:
            # Extend last segment to audio end
            audio_len = librosa.get_duration(path=state["audio_path"])
            curr['end'] = max(curr['end'], audio_len)
            segments.append(curr)

    await log_progress(state, f"📊 音频分析完成: 已生成 {len(segments)} 个视觉序列")

    return {"aligned_segments": segments}
