"""
Conditional Edge Functions for LangGraph

These functions determine routing decisions in the workflow graph.
"""

from typing import Literal
from app.graph.state import VideoEditState


def should_align_lyrics(state: VideoEditState) -> Literal["align_lyrics", "merge_segments"]:
    """
    Decide whether to align manual lyrics with Whisper timestamps.

    If manual_lyrics is provided, route to align_lyrics node.
    Otherwise, skip to merge_segments.

    Args:
        state: Current workflow state

    Returns:
        "align_lyrics" if manual lyrics provided, else "merge_segments"
    """
    manual_lyrics = state.get("manual_lyrics")
    if manual_lyrics and manual_lyrics.strip():
        return "align_lyrics"
    return "merge_segments"


def should_generate_ai(state: VideoEditState) -> Literal["ai_fallback", "allocate_clips"]:
    """
    Decide whether to use AI generation fallback.

    If AI generation is enabled and there are segments with low matching scores,
    route to ai_fallback node. Otherwise, proceed to allocate_clips.

    Args:
        state: Current workflow state

    Returns:
        "ai_fallback" if AI generation needed, else "allocate_clips"
    """
    allow_ai_gen = state.get("allow_ai_gen", False)

    if not allow_ai_gen:
        return "allocate_clips"

    # Check if any segment has poor matches
    segment_matches = state.get("segment_matches", [])
    config = state.get("_config")

    if not segment_matches or not config:
        return "allocate_clips"

    # Get fallback threshold from config
    fallback_score = config.get("advanced", "ai_fallback_score", 0.22)

    # Check if any segment needs AI generation
    for match in segment_matches:
        matches = match.get("matches", [])
        if matches and matches[0].get("score", 1.0) < fallback_score:
            return "ai_fallback"

    return "allocate_clips"


def should_human_review(state: VideoEditState) -> Literal["human_review", "allocate_clips"]:
    """
    Decide whether human review is needed.

    This is a placeholder for future human-in-the-loop workflows.
    Currently always returns "allocate_clips" (skip review).

    Args:
        state: Current workflow state

    Returns:
        "human_review" if review needed, else "allocate_clips"
    """
    # Placeholder logic - could check:
    # - Extremely low match scores across all segments
    # - User preference for manual review
    # - Quality thresholds
    #
    # For now, always skip human review
    return "allocate_clips"


def check_match_quality(state: VideoEditState) -> Literal["good", "needs_ai", "needs_review"]:
    """
    Advanced routing: Check overall match quality and route accordingly.

    This function evaluates the quality of all segment matches and determines
    the best next step:
    - "good": All matches are acceptable, proceed to allocation
    - "needs_ai": Some matches are poor but AI gen is enabled
    - "needs_review": Matches are critically poor, needs human intervention

    Args:
        state: Current workflow state

    Returns:
        Quality assessment result
    """
    segment_matches = state.get("segment_matches", [])
    config = state.get("_config")
    allow_ai_gen = state.get("allow_ai_gen", False)

    if not segment_matches or not config:
        return "good"

    # Get thresholds
    fallback_score = config.get("advanced", "ai_fallback_score", 0.22)
    critical_score = 0.10  # Below this, even AI might not help

    # Analyze match quality
    poor_matches = 0
    critical_matches = 0
    total_segments = len(segment_matches)

    for match in segment_matches:
        matches = match.get("matches", [])
        if matches:
            best_score = matches[0].get("score", 1.0)
            if best_score < critical_score:
                critical_matches += 1
            elif best_score < fallback_score:
                poor_matches += 1

    # Decision logic
    if critical_matches > total_segments * 0.3:
        # More than 30% critically poor - needs review
        return "needs_review"
    elif poor_matches > 0 and allow_ai_gen:
        # Some poor matches and AI gen available
        return "needs_ai"
    else:
        # All matches acceptable
        return "good"
