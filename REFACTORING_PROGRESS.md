# SonicVideo LangGraph Refactoring Progress

## ✅ Completed Tasks (9/18)

### Phase 1: Infrastructure ✅
- [x] **Task 1**: Install LangGraph dependencies
  - Updated `requirements.txt` with langgraph, langchain, langchain-openai, langchain-anthropic, langchain-google-genai, dashscope, sse-starlette

- [x] **Task 2**: Create directory structure
  - Created `app/graph/`, `app/graph/nodes/`, `app/providers/`, `app/api/`
  - Created all necessary `__init__.py` files

### Phase 2: Core Abstractions ✅
- [x] **Task 3**: Implement State definition
  - Created `app/graph/state.py` with `VideoEditState` TypedDict
  - Includes all input, processing, output, and metadata fields
  - Helper function `create_initial_state()` for initialization

- [x] **Task 4**: Implement LLMProvider base class
  - Created `app/providers/base.py` with abstract `LLMProvider` interface
  - Methods: `generate_text`, `generate_json`, `analyze_image`, `analyze_multi_images`

### Phase 3: Provider Implementations ✅
- [x] **Task 5**: Implement QwenProvider
  - Created `app/providers/qwen.py`
  - Extracted all logic from `LLMEngine`
  - Methods: `generate_visual_script`, `rerank_clips`, `align_lyrics`, `analyze_scene_semantics`

- [x] **Task 6**: Implement GeminiProvider
  - Created `app/providers/gemini.py`
  - Full support for Google Gemini API with vision capabilities

- [x] **Task 7**: Implement OpenAIProvider
  - Created `app/providers/openai.py`
  - GPT-4 and GPT-4V support with async client

- [x] **Task 8**: Implement AnthropicProvider
  - Created `app/providers/anthropic.py`
  - Claude 3.5 Sonnet/Opus support with vision

- [x] **Task 9**: Implement LLMProviderFactory
  - Created `app/providers/factory.py`
  - Auto-detection based on config with fallback logic
  - Task-based routing support

### Phase 4: Graph Nodes (Partial)
- [x] **Task 10 (Partial)**: Audio processing nodes
  - Created `app/graph/nodes/audio.py`
  - Implemented: `transcribe_audio_node`, `align_lyrics_node`, `merge_segments_node`

## 🚧 Remaining Tasks (8/18)

### Phase 4: Graph Nodes (Continue)
- [ ] **Task 11**: Implement video processing nodes
  - Create `app/graph/nodes/video.py`
  - Nodes: `split_scenes_node`, `build_vector_index_node`, `analyze_library_node`

- [ ] **Task 12**: Implement matching nodes
  - Create `app/graph/nodes/matching.py`
  - Nodes: `match_segments_node`, `allocate_clips_node`, `ai_fallback_node`, `human_review_node`

- [ ] **Task 13**: Implement assembly node
  - Create `app/graph/nodes/assembly.py`
  - Node: `assemble_video_node`

### Phase 5: Graph Construction
- [ ] **Task 14**: Implement conditional edges
  - Create `app/graph/edges.py`
  - Functions: `should_align_lyrics`, `should_generate_ai`, `should_human_review`

- [ ] **Task 15**: Implement Graph builder
  - Create `app/graph/builder.py`
  - Construct StateGraph with all nodes and edges
  - Add checkpoint configuration (MemorySaver for dev)

### Phase 6: Integration
- [ ] **Task 16**: Update ConfigManager
  - Add `llm_routing` to `DEFAULT_CONFIG`
  - Support for task-based routing configuration

- [ ] **Task 17**: Integrate into main.py
  - Add `/api/v2/video/process` endpoint
  - Add `/api/v2/video/status/{session_id}` endpoint
  - Add `/api/v2/video/resume/{session_id}` endpoint
  - Feature flag: `USE_LANGGRAPH` environment variable

- [ ] **Task 18**: Test the system
  - End-to-end workflow test
  - Provider switching test
  - Checkpoint recovery test

## 📁 File Structure Created

```
app/
├── providers/                   ✅ Complete
│   ├── __init__.py
│   ├── base.py                  # Abstract LLMProvider
│   ├── qwen.py                  # Qwen/DashScope provider
│   ├── gemini.py                # Google Gemini provider
│   ├── openai.py                # OpenAI GPT provider
│   ├── anthropic.py             # Anthropic Claude provider
│   └── factory.py               # Provider factory
│
├── graph/                       🚧 Partial
│   ├── __init__.py
│   ├── state.py                 ✅ VideoEditState definition
│   ├── nodes/
│   │   ├── __init__.py
│   │   ├── audio.py             ✅ Audio processing nodes
│   │   ├── video.py             ❌ TODO
│   │   ├── matching.py          ❌ TODO
│   │   └── assembly.py          ❌ TODO
│   ├── edges.py                 ❌ TODO
│   └── builder.py               ❌ TODO
│
└── api/                         ❌ TODO
    ├── __init__.py
    ├── routes.py                # FastAPI routes for v2 API
    └── websocket.py             # WebSocket handlers
```

## 🎯 Next Steps

### Immediate Actions (Priority Order)

1. **Complete Video Processing Nodes** (`app/graph/nodes/video.py`)
   - Extract logic from `process_video_agent` lines 220-328
   - Implement `split_scenes_node`, `build_vector_index_node`, `analyze_library_node`

2. **Complete Matching Nodes** (`app/graph/nodes/matching.py`)
   - Extract logic from `process_video_agent` lines 355-521
   - Implement parallel processing with `asyncio.Semaphore`
   - Implement `match_segments_node`, `allocate_clips_node`

3. **Complete Assembly Node** (`app/graph/nodes/assembly.py`)
   - Extract logic from `process_video_agent` lines 552-554
   - Simple wrapper around `Editor.assemble()`

4. **Implement Conditional Edges** (`app/graph/edges.py`)
   ```python
   def should_align_lyrics(state):
       return state.get("manual_lyrics") is not None

   def should_generate_ai(state):
       matches = state.get("segment_matches", [])
       return state.get("allow_ai_gen") and matches and matches[0]['score'] < 0.22

   def should_human_review(state):
       # Placeholder for future human-in-the-loop
       return False
   ```

5. **Build the Graph** (`app/graph/builder.py`)
   ```python
   from langgraph.graph import StateGraph
   from langgraph.checkpoint.memory import MemorySaver

   def build_video_editing_graph():
       workflow = StateGraph(VideoEditState)

       # Add nodes
       workflow.add_node("transcribe_audio", transcribe_audio_node)
       workflow.add_node("align_lyrics", align_lyrics_node)
       workflow.add_node("merge_segments", merge_segments_node)
       # ... add all other nodes

       # Add edges
       workflow.set_entry_point("transcribe_audio")
       workflow.add_conditional_edges(
           "transcribe_audio",
           should_align_lyrics,
           {
               True: "align_lyrics",
               False: "merge_segments"
           }
       )
       # ... add all other edges

       workflow.set_finish_point("assemble_video")

       # Compile with checkpointer
       checkpointer = MemorySaver()
       return workflow.compile(checkpointer=checkpointer)
   ```

6. **Update ConfigManager** (add to `DEFAULT_CONFIG`)
   ```python
   "llm_routing": {
       "default": "qwen",
       "tasks": {
           "visual_script": "qwen",
           "scene_analysis": "gemini",
           "lyrics_alignment": "qwen",
           "reranking": "qwen"
       }
   },
   "api_keys": {
       "dashscope_api_key": "",
       "gemini_api_key": "",
       "openai_api_key": "",      # Add
       "anthropic_api_key": ""     # Add
   }
   ```

7. **Create v2 API Endpoints** (`app/api/routes.py`)
   - Implement graph execution with session management
   - Add WebSocket streaming for progress

8. **Integrate into main.py**
   - Add environment flag `USE_LANGGRAPH`
   - Mount v2 API routes
   - Keep old endpoint as fallback

## 🔍 Code Reuse Strategy

Most of the logic already exists in `app/main.py:process_video_agent`. The refactoring mainly involves:

1. **Extracting** code blocks into node functions
2. **Passing** data through `state` instead of local variables
3. **Adding** proper error handling and progress logging
4. **Maintaining** the same business logic

## 🧪 Testing Strategy

After implementation, test:
1. Basic workflow with Qwen provider
2. Provider switching (Qwen → Gemini → OpenAI)
3. Lyrics alignment path
4. AI generation fallback
5. Checkpoint recovery (interrupt and resume)

## 📊 Estimated Completion

- **Remaining work**: ~1,500 lines of code
- **Time estimate**: 4-6 hours for experienced developer
- **Complexity**: Medium (mostly extraction and adaptation)

## 💡 Tips

1. **Start with video.py nodes** - they're straightforward extractions
2. **matching.py is the most complex** - handle async/concurrent logic carefully
3. **Test incrementally** - after each node, run a simple test
4. **Use the existing `progress_logs`** - integrate with state["progress"]
5. **Keep error handling robust** - wrap nodes in try/except blocks
