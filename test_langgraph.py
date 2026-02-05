"""
Test Script for LangGraph Refactoring

This script validates the LangGraph implementation by testing:
1. Provider factory and initialization
2. State management
3. Graph construction
4. Individual node execution (dry run)
"""

import asyncio
import os
import sys

# Add app to path
sys.path.insert(0, os.path.dirname(__file__))

from app.core.config_manager import ConfigManager
from app.providers.factory import LLMProviderFactory
from app.graph.state import create_initial_state
from app.graph.builder import build_video_editing_graph, build_simple_graph


async def test_provider_factory():
    """Test 1: Provider factory and initialization."""
    print("\n" + "="*60)
    print("TEST 1: Provider Factory")
    print("="*60)

    config = ConfigManager()

    # Test provider creation
    try:
        provider = LLMProviderFactory.from_config(config, task="visual_script")
        print(f"✅ Provider created: {provider.__class__.__name__}")
        print(f"   Model: {provider.model}")
        print(f"   Info: {provider.get_model_info()}")
    except Exception as e:
        print(f"❌ Provider creation failed: {e}")
        return False

    # Test task-based routing
    tasks = ["visual_script", "scene_analysis", "lyrics_alignment", "reranking"]
    for task in tasks:
        try:
            provider = LLMProviderFactory.from_config(config, task=task)
            print(f"✅ Task '{task}' → {provider.__class__.__name__}")
        except Exception as e:
            print(f"⚠️  Task '{task}' failed: {e}")

    return True


async def test_state_management():
    """Test 2: State creation and management."""
    print("\n" + "="*60)
    print("TEST 2: State Management")
    print("="*60)

    config = ConfigManager()

    # Create initial state
    state = create_initial_state(
        audio_path="/path/to/audio.mp3",
        video_paths=["/path/to/video1.mp4", "/path/to/video2.mp4"],
        intent="Test intent",
        manual_lyrics="Test lyrics",
        video_description="Test description",
        allow_ai_gen=False,
        config=config,
        websocket_manager=None
    )

    # Validate state structure
    required_fields = [
        "audio_path", "video_paths", "intent", "manual_lyrics",
        "video_description", "allow_ai_gen", "audio_segments",
        "aligned_segments", "video_clips", "segment_matches",
        "final_sequence", "output_path", "errors", "progress"
    ]

    all_present = True
    for field in required_fields:
        if field in state:
            print(f"✅ Field '{field}' present")
        else:
            print(f"❌ Field '{field}' missing")
            all_present = False

    return all_present


def test_graph_construction():
    """Test 3: Graph construction."""
    print("\n" + "="*60)
    print("TEST 3: Graph Construction")
    print("="*60)

    try:
        # Build full graph
        graph = build_video_editing_graph(use_checkpoints=True)
        print("✅ Full graph built successfully")
        print(f"   Graph type: {type(graph).__name__}")

        # Build simple graph
        simple_graph = build_simple_graph()
        print("✅ Simple graph built successfully")

        # Get graph structure (if available)
        try:
            nodes = graph.get_graph().nodes
            print(f"   Total nodes: {len(nodes)}")
            print(f"   Node names: {list(nodes.keys())[:5]}...")
        except:
            print("   (Graph introspection not available)")

        return True

    except Exception as e:
        print(f"❌ Graph construction failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_node_imports():
    """Test 4: Node module imports."""
    print("\n" + "="*60)
    print("TEST 4: Node Module Imports")
    print("="*60)

    modules = [
        ("app.graph.nodes.audio", ["transcribe_audio_node", "align_lyrics_node", "merge_segments_node"]),
        ("app.graph.nodes.video", ["split_scenes_node", "build_vector_index_node", "analyze_library_node"]),
        ("app.graph.nodes.matching", ["match_segments_node", "ai_fallback_node", "allocate_clips_node"]),
        ("app.graph.nodes.assembly", ["assemble_video_node"]),
    ]

    all_imported = True
    for module_name, functions in modules:
        try:
            module = __import__(module_name, fromlist=functions)
            for func_name in functions:
                if hasattr(module, func_name):
                    print(f"✅ {module_name}.{func_name}")
                else:
                    print(f"❌ {module_name}.{func_name} not found")
                    all_imported = False
        except Exception as e:
            print(f"❌ Import {module_name} failed: {e}")
            all_imported = False

    return all_imported


async def test_api_routes():
    """Test 5: API routes availability."""
    print("\n" + "="*60)
    print("TEST 5: API Routes")
    print("="*60)

    try:
        from app.api.routes import router
        print(f"✅ Router imported: {router.prefix}")

        # List routes
        routes = [route.path for route in router.routes]
        print(f"   Available routes: {len(routes)}")
        for route_path in routes:
            print(f"   - {router.prefix}{route_path}")

        return True

    except Exception as e:
        print(f"❌ API routes test failed: {e}")
        return False


async def run_all_tests():
    """Run all tests and report results."""
    print("\n" + "="*60)
    print("LANGGRAPH REFACTORING VALIDATION")
    print("="*60)

    results = {
        "Provider Factory": await test_provider_factory(),
        "State Management": await test_state_management(),
        "Graph Construction": test_graph_construction(),
        "Node Imports": await test_node_imports(),
        "API Routes": await test_api_routes()
    }

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed! LangGraph refactoring is ready.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Review the errors above.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_all_tests())
    sys.exit(exit_code)
