"""
LangGraph Workflow Builder

This module constructs the complete video editing workflow graph.
"""

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from app.graph.state import VideoEditState
from app.graph.nodes.audio import (
    transcribe_audio_node,
    align_lyrics_node,
    merge_segments_node
)
from app.graph.nodes.video import (
    split_scenes_node,
    build_vector_index_node,
    analyze_library_node
)
from app.graph.nodes.matching import (
    match_segments_node,
    ai_fallback_node,
    allocate_clips_node,
    human_review_node
)
from app.graph.nodes.assembly import assemble_video_node
from app.graph.edges import (
    should_align_lyrics,
    should_generate_ai,
    check_match_quality
)


def build_video_editing_graph(use_checkpoints: bool = True):
    """
    Build the complete video editing workflow graph.

    The graph implements this flow:

    START
      ↓
    transcribe_audio
      ↓
    [condition: has manual lyrics?]
      ├─ Yes → align_lyrics → merge_segments
      └─ No  → merge_segments
                 ↓
               split_scenes
                 ↓
               build_vector_index
                 ↓
               analyze_library
                 ↓
               match_segments
                 ↓
               [condition: match quality]
                 ├─ needs_ai → ai_fallback → allocate_clips
                 ├─ needs_review → human_review → allocate_clips
                 └─ good → allocate_clips
                           ↓
                         assemble_video
                           ↓
                          END

    Args:
        use_checkpoints: Whether to enable checkpointing for recovery

    Returns:
        Compiled StateGraph ready for execution
    """
    # Create workflow
    workflow = StateGraph(VideoEditState)

    # ===== ADD NODES =====

    # Audio processing nodes
    workflow.add_node("transcribe_audio", transcribe_audio_node)
    workflow.add_node("align_lyrics", align_lyrics_node)
    workflow.add_node("merge_segments", merge_segments_node)

    # Video processing nodes
    workflow.add_node("split_scenes", split_scenes_node)
    workflow.add_node("build_vector_index", build_vector_index_node)
    workflow.add_node("analyze_library", analyze_library_node)

    # Matching nodes
    workflow.add_node("match_segments", match_segments_node)
    workflow.add_node("ai_fallback", ai_fallback_node)
    workflow.add_node("allocate_clips", allocate_clips_node)
    workflow.add_node("human_review", human_review_node)

    # Assembly node
    workflow.add_node("assemble_video", assemble_video_node)

    # ===== ADD EDGES =====

    # Set entry point
    workflow.set_entry_point("transcribe_audio")

    # Audio processing flow
    workflow.add_conditional_edges(
        "transcribe_audio",
        should_align_lyrics,
        {
            "align_lyrics": "align_lyrics",
            "merge_segments": "merge_segments"
        }
    )

    workflow.add_edge("align_lyrics", "merge_segments")

    # Video processing flow (sequential)
    workflow.add_edge("merge_segments", "split_scenes")
    workflow.add_edge("split_scenes", "build_vector_index")
    workflow.add_edge("build_vector_index", "analyze_library")

    # Matching flow
    workflow.add_edge("analyze_library", "match_segments")

    # Quality-based routing after matching
    workflow.add_conditional_edges(
        "match_segments",
        check_match_quality,
        {
            "good": "allocate_clips",
            "needs_ai": "ai_fallback",
            "needs_review": "human_review"
        }
    )

    # Fallback paths converge to allocation
    workflow.add_edge("ai_fallback", "allocate_clips")
    workflow.add_edge("human_review", "allocate_clips")

    # Final assembly
    workflow.add_edge("allocate_clips", "assemble_video")

    # Set finish point
    workflow.add_edge("assemble_video", END)

    # ===== COMPILE GRAPH =====

    # Add checkpoint support for recovery
    if use_checkpoints:
        checkpointer = MemorySaver()
        return workflow.compile(checkpointer=checkpointer)
    else:
        return workflow.compile()


def build_simple_graph():
    """
    Build a simplified graph without conditional logic (for testing).

    This is useful for debugging and testing individual node functionality.

    Returns:
        Compiled StateGraph with linear flow
    """
    workflow = StateGraph(VideoEditState)

    # Add all nodes
    workflow.add_node("transcribe_audio", transcribe_audio_node)
    workflow.add_node("merge_segments", merge_segments_node)
    workflow.add_node("split_scenes", split_scenes_node)
    workflow.add_node("build_vector_index", build_vector_index_node)
    workflow.add_node("analyze_library", analyze_library_node)
    workflow.add_node("match_segments", match_segments_node)
    workflow.add_node("allocate_clips", allocate_clips_node)
    workflow.add_node("assemble_video", assemble_video_node)

    # Simple linear flow
    workflow.set_entry_point("transcribe_audio")
    workflow.add_edge("transcribe_audio", "merge_segments")
    workflow.add_edge("merge_segments", "split_scenes")
    workflow.add_edge("split_scenes", "build_vector_index")
    workflow.add_edge("build_vector_index", "analyze_library")
    workflow.add_edge("analyze_library", "match_segments")
    workflow.add_edge("match_segments", "allocate_clips")
    workflow.add_edge("allocate_clips", "assemble_video")
    workflow.add_edge("assemble_video", END)

    return workflow.compile()


# Export the default graph builder
__all__ = ["build_video_editing_graph", "build_simple_graph"]
