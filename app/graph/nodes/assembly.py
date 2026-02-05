"""
Assembly Node for LangGraph

This node handles final video assembly and rendering.
"""

import gc
from typing import Dict, Any

from app.graph.state import VideoEditState
from app.core.editor import Editor


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


async def assemble_video_node(state: VideoEditState) -> Dict[str, Any]:
    """
    Node: Assemble final video from sequence.

    Input from state:
        - final_sequence: List of clips to assemble
        - audio_path: Audio file path
        - _config: ConfigManager instance
        - _editor: Editor instance (or create)
        - _vector_engine: VectorEngine instance (for cleanup)

    Output to state:
        - output_path: Path to final rendered video
    """
    await log_progress(state, "🎞️ [STEP 4/4] 进入后期合成阶段...")
    await log_progress(state, "⚙️ 正在执行 MoviePy 视频流混放、音轨对齐与高性能渲染并行导出...")

    # Get or create editor
    config = state["_config"]
    editor = state.get("_editor")
    if not editor:
        editor = Editor(config=config)
        state["_editor"] = editor

    # Assemble video
    final_sequence = state["final_sequence"]
    audio_path = state["audio_path"]

    try:
        final_video_path = editor.assemble(final_sequence, audio_path)

        await log_progress(state, "✨ 制作任务圆满完成！最终成片已生成。")

        return {"output_path": final_video_path}

    except Exception as e:
        error_msg = f"❌ 视频合成失败: {str(e)}"
        await log_progress(state, error_msg)
        state["errors"].append(error_msg)
        raise

    finally:
        # Cleanup: Reset vector engine and free memory
        await log_progress(state, "🧹 正在释放内存资源...")
        vector_eng = state.get("_vector_engine")
        if vector_eng:
            vector_eng.reset()
        gc.collect()
        await log_progress(state, "♻️ 资源清理完毕，系统就绪")
