"""
API Routes for LangGraph Workflow (v2 API)

This module provides the new v2 API endpoints that use LangGraph workflow.
"""

import os
import uuid
from typing import Dict, Any, Optional
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from app.graph.builder import build_video_editing_graph
from app.graph.state import create_initial_state
from app.core.config_manager import ConfigManager
from app.core.video_processor import VideoProcessor
from app.core.audio_processor import AudioProcessor
from app.core.editor import Editor
from app.core.image_processor import ImageProcessor


# Create router
router = APIRouter(prefix="/api/v2", tags=["v2"])

# Session storage (in-memory for now, use Redis in production)
active_sessions: Dict[str, Dict[str, Any]] = {}


class ProcessVideoRequest(BaseModel):
    """Request model for video processing."""
    audio_path: str
    video_paths: list
    intent: str
    manual_lyrics: Optional[str] = None
    video_description: Optional[str] = None
    allow_ai_gen: bool = False


class ProcessVideoResponse(BaseModel):
    """Response model for video processing."""
    session_id: str
    status: str
    message: str


class SessionStatusResponse(BaseModel):
    """Response model for session status."""
    session_id: str
    status: str
    progress: list
    errors: list
    output_path: Optional[str] = None


async def run_graph_workflow(
    session_id: str,
    request: ProcessVideoRequest,
    config: ConfigManager,
    websocket_manager: Any = None
):
    """
    Execute the LangGraph workflow in background.

    Args:
        session_id: Unique session identifier
        request: Processing request parameters
        config: ConfigManager instance
        websocket_manager: WebSocket connection manager
    """
    try:
        # Update session status
        active_sessions[session_id]["status"] = "running"

        # Create initial state
        initial_state = create_initial_state(
            audio_path=request.audio_path,
            video_paths=request.video_paths,
            intent=request.intent,
            manual_lyrics=request.manual_lyrics,
            video_description=request.video_description,
            allow_ai_gen=request.allow_ai_gen,
            config=config,
            websocket_manager=websocket_manager
        )

        # Initialize processors in state
        initial_state["_audio_processor"] = AudioProcessor()
        initial_state["_video_processor"] = VideoProcessor(config=config)
        initial_state["_editor"] = Editor(config=config)
        initial_state["_image_processor"] = ImageProcessor()

        # Build and execute graph
        graph = build_video_editing_graph(use_checkpoints=True)

        # Execute with streaming (for progress updates)
        final_state = None
        async for event in graph.astream(initial_state, {"recursion_limit": 100}):
            # Track progress through events
            if isinstance(event, dict):
                # Store latest state
                for node_name, node_state in event.items():
                    if isinstance(node_state, dict):
                        final_state = node_state

        # Update session with results
        if final_state:
            active_sessions[session_id].update({
                "status": "completed",
                "output_path": final_state.get("output_path"),
                "progress": final_state.get("progress", []),
                "errors": final_state.get("errors", []),
                "final_state": final_state
            })
        else:
            active_sessions[session_id].update({
                "status": "failed",
                "errors": ["Workflow execution failed - no final state"]
            })

    except Exception as e:
        # Update session with error
        active_sessions[session_id].update({
            "status": "failed",
            "errors": [str(e)]
        })
        print(f"Workflow error for session {session_id}: {e}")
        import traceback
        traceback.print_exc()


@router.post("/video/process", response_model=ProcessVideoResponse)
async def process_video(
    request: ProcessVideoRequest,
    background_tasks: BackgroundTasks
):
    """
    Start video processing with LangGraph workflow.

    This endpoint initiates the workflow and returns immediately with a session ID.
    Use the session ID to check status and retrieve results.

    Args:
        request: Video processing parameters
        background_tasks: FastAPI background tasks

    Returns:
        ProcessVideoResponse with session_id
    """
    # Generate session ID
    session_id = str(uuid.uuid4())

    # Validate inputs
    if not os.path.exists(request.audio_path):
        raise HTTPException(status_code=400, detail=f"Audio file not found: {request.audio_path}")

    for vp in request.video_paths:
        if isinstance(vp, str) and not os.path.exists(vp):
            raise HTTPException(status_code=400, detail=f"Video file not found: {vp}")

    # Initialize session
    active_sessions[session_id] = {
        "status": "pending",
        "progress": [],
        "errors": [],
        "output_path": None,
        "request": request.dict()
    }

    # Get config
    config = ConfigManager()

    # Start workflow in background
    background_tasks.add_task(
        run_graph_workflow,
        session_id,
        request,
        config,
        None  # WebSocket manager (can be passed if available)
    )

    return ProcessVideoResponse(
        session_id=session_id,
        status="started",
        message="Video processing started. Use session_id to check status."
    )


@router.get("/video/status/{session_id}", response_model=SessionStatusResponse)
async def get_status(session_id: str):
    """
    Get the status of a processing session.

    Args:
        session_id: Session identifier

    Returns:
        SessionStatusResponse with current status and progress
    """
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    session = active_sessions[session_id]

    return SessionStatusResponse(
        session_id=session_id,
        status=session["status"],
        progress=session.get("progress", []),
        errors=session.get("errors", []),
        output_path=session.get("output_path")
    )


@router.post("/video/resume/{session_id}")
async def resume_session(
    session_id: str,
    background_tasks: BackgroundTasks
):
    """
    Resume a failed or interrupted session.

    This uses LangGraph's checkpoint feature to continue from the last state.

    Args:
        session_id: Session identifier
        background_tasks: FastAPI background tasks

    Returns:
        Status message
    """
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    session = active_sessions[session_id]

    if session["status"] not in ["failed", "interrupted"]:
        raise HTTPException(
            status_code=400,
            detail=f"Session cannot be resumed (status: {session['status']})"
        )

    # Get original request
    original_request = ProcessVideoRequest(**session["request"])
    config = ConfigManager()

    # Restart workflow (checkpoint will restore state)
    background_tasks.add_task(
        run_graph_workflow,
        session_id,
        original_request,
        config,
        None
    )

    return {
        "session_id": session_id,
        "status": "resumed",
        "message": "Session resumed from checkpoint"
    }


@router.delete("/video/session/{session_id}")
async def delete_session(session_id: str):
    """
    Delete a session and clean up resources.

    Args:
        session_id: Session identifier

    Returns:
        Status message
    """
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    del active_sessions[session_id]

    return {
        "session_id": session_id,
        "status": "deleted",
        "message": "Session deleted successfully"
    }


@router.get("/sessions")
async def list_sessions():
    """
    List all active sessions.

    Returns:
        List of session summaries
    """
    return {
        "sessions": [
            {
                "session_id": sid,
                "status": session["status"],
                "has_output": session.get("output_path") is not None
            }
            for sid, session in active_sessions.items()
        ]
    }
