"""
LangGraph State Definition for Sonic-AI

This module defines the shared state structure for the video editing workflow.
"""

from typing import TypedDict, List, Optional, Any, Annotated
from operator import add


class VideoEditState(TypedDict, total=False):
    """
    Shared state for the video editing workflow.

    This TypedDict defines all the data that flows through the LangGraph nodes.
    Fields are organized by lifecycle stage: inputs, processing, results, outputs, and metadata.
    """

    # === INPUT PARAMETERS ===
    audio_path: str
    video_paths: List[Any]  # List[str] or List[dict] for images/live photos
    intent: str
    manual_lyrics: Optional[str]
    video_description: Optional[str]
    allow_ai_gen: bool

    # === PROCESSING INTERMEDIATE STATE ===
    audio_segments: List[dict]          # Whisper transcription results
    aligned_segments: List[dict]        # LLM-aligned lyrics with timestamps
    video_clips: List[dict]             # Scene-split clip metadata
    library_context: Optional[str]      # Visual summary of material library

    # === MATCHING RESULTS ===
    segment_matches: List[dict]         # Match results for each segment
    final_sequence: List[dict]          # Final rendering sequence

    # === OUTPUT ===
    output_path: Optional[str]          # Path to final rendered video

    # === METADATA ===
    errors: Annotated[List[str], add]   # Error log (append-only)
    progress: Annotated[List[str], add] # Progress messages (append-only)

    # === INTERNAL OBJECTS (not serialized) ===
    _config: Optional[Any]              # ConfigManager instance
    _vector_engine: Optional[Any]       # VectorEngine instance
    _llm_provider: Optional[Any]        # LLMProvider instance
    _audio_processor: Optional[Any]     # AudioProcessor instance
    _video_processor: Optional[Any]     # VideoProcessor instance
    _editor: Optional[Any]              # Editor instance
    _image_processor: Optional[Any]     # ImageProcessor instance
    _websocket_manager: Optional[Any]   # WebSocket connection manager
    _clip_usage_count: Optional[dict]   # Clip usage tracking


def create_initial_state(
    audio_path: str,
    video_paths: List[Any],
    intent: str,
    manual_lyrics: Optional[str] = None,
    video_description: Optional[str] = None,
    allow_ai_gen: bool = False,
    config: Optional[Any] = None,
    websocket_manager: Optional[Any] = None
) -> VideoEditState:
    """
    Create an initial state dictionary for the workflow.

    Args:
        audio_path: Path to the audio file
        video_paths: List of video/image paths
        intent: User's creative intent
        manual_lyrics: Optional manual lyrics for alignment
        video_description: Optional video description
        allow_ai_gen: Whether to allow AI video generation
        config: ConfigManager instance
        websocket_manager: WebSocket connection manager

    Returns:
        VideoEditState: Initial state dictionary
    """
    return VideoEditState(
        # Inputs
        audio_path=audio_path,
        video_paths=video_paths,
        intent=intent,
        manual_lyrics=manual_lyrics,
        video_description=video_description,
        allow_ai_gen=allow_ai_gen,

        # Processing state (initialized as empty)
        audio_segments=[],
        aligned_segments=[],
        video_clips=[],
        library_context=None,
        segment_matches=[],
        final_sequence=[],

        # Output
        output_path=None,

        # Metadata
        errors=[],
        progress=[],

        # Internal objects
        _config=config,
        _vector_engine=None,
        _llm_provider=None,
        _audio_processor=None,
        _video_processor=None,
        _editor=None,
        _image_processor=None,
        _websocket_manager=websocket_manager,
        _clip_usage_count={}
    )
