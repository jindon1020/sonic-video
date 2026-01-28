from openai import OpenAI
import os
import json
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

class LLMEngine:
    def __init__(self, config=None):
        if config:
            self.api_key = config.get("api_keys", "dashscope_api_key") or os.getenv("DASHSCOPE_API_KEY")
            self.gemini_key = config.get("api_keys", "gemini_api_key") or os.getenv("GEMINI_API_KEY")
            self.model_name = config.get("models", "llm_model", "qwen-plus")
            self.vision_model_name = config.get("models", "vision_model", "qwen-vl-plus")
            self.gemini_model_name = config.get("models", "gemini_model", "gemini-1.5-flash")
        else:
            self.api_key = os.getenv("DASHSCOPE_API_KEY")
            self.gemini_key = os.getenv("GEMINI_API_KEY")
            self.model_name = "qwen-plus"
            self.vision_model_name = "qwen-vl-plus"
            self.gemini_model_name = "gemini-1.5-flash"

        if not self.api_key:
            print("Warning: DASHSCOPE_API_KEY not found. Some features may fail.")

        if self.api_key:
            self.client = OpenAI(
                api_key=self.api_key,
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            )

        if self.gemini_key:
            genai.configure(api_key=self.gemini_key)
            self.gemini_model = genai.GenerativeModel(self.gemini_model_name)

    async def tag_clip_visuals(self, image_path):
        """
        [Migrated to Qwen-VL] Visual tagging in English for better CLIP recall.
        """
        if not self.api_key:
            return "(Analysis Failed)"

        import base64
        def encode_image(path):
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode('utf-8')

        try:
            base64_image = encode_image(image_path)
            response = self.client.chat.completions.create(
                model=self.vision_model_name,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Describe the core visual content of this image in a very short English phrase (max 6 words)."},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                    ],
                }]
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"Warning: Qwen-VL labeling failed: {e}")
            return "(Analyzing...)"

    async def analyze_scene_semantics(self, image_path: str) -> dict:
        """
        [Migrated to Qwen-VL] Deep semantic analysis (English Optimized)
        """
        if not self.api_key:
            return {"error": "Missing API Key"}

        import base64
        def encode_image(path):
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode('utf-8')

        try:
            base64_image = encode_image(image_path)
            prompt = """
            You are a professional video content analyst. Please extract structured information in English:
            {
                "action": "Description of the main action (e.g., person turning back)",
                "mood": "Emotional tone (e.g., mysterious, epic, peaceful)",
                "objects": ["object1", "object2"],
                "description": "Detailed visual semantic description in English"
            }
            """

            response = self.client.chat.completions.create(
                model=self.vision_model_name,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                    ],
                }],
                response_format={ "type": "json_object" }
            )
            return json.loads(response.choices[0].message.content.strip())
        except Exception as e:
            print(f"Warning: Qwen-VL Semantic analysis failed: {e}")
            return {"action": "Processing error", "mood": "Unknown", "objects": [], "description": "Unable to analyze visual content"}

    async def rerank_clips(self, query: str, candidates: list[dict]) -> list[dict]:
        """
        [Strategy 1] Router-Ranker cascade filtering - Ranker stage.
        Uses LLM to verify intent and rerank candidates from the Router (coarse) stage.
        """
        if not candidates:
            return []

        candidates_context = []
        for idx, item in enumerate(candidates):
            meta = item.get("metadata", {})
            if isinstance(meta, str):
                desc = meta
                mood = "Unknown"
                action = ""
            else:
                desc = meta.get("description", item.get("raw_text", "No description"))
                mood = meta.get("mood", "Neutral")
                action = meta.get("action", "")

            candidates_context.append({
                "id": idx,
                "content": f"[Clip {idx}] Description: {desc} | Action: {action} | Mood: {mood}"
            })

        prompt = f"""
        You are a video retrieval expert (Ranker).
        Your task is to match the target Intent with the candidate clips based on semantic English descriptions.

        【Query Intent】: "{query}" (English)

        【Candidates (Router Results)】:
        {json.dumps(candidates_context, indent=2)}

        【Instructions】:
        1. Compare the core visual elements and emotional tone between the query and candidates.
        2. Assign a score (1-10) for each clip.
        3. Provide the 'reason' in CHINESE to help the user understand your decision.
        4. Focus on visual consistency (e.g., lighting, objects, movement).

        【Output Format (JSON)】:
        {{
            "ranked_results": [
                {{ "id": original_id, "score": 10.0, "reason": "Chinese matching reason" }},
                ...
            ]
        }}
        """

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are a precise search ranking algorithm. Output JSON directly."},
                    {"role": "user", "content": prompt}
                ],
                response_format={ "type": "json_object" }
            )

            result_json = json.loads(response.choices[0].message.content.strip())
            ranked_indices = result_json.get("ranked_results", [])

            final_results = []
            seen_ids = set()
            for rank_item in ranked_indices:
                original_idx = rank_item.get("id")
                if 0 <= original_idx < len(candidates) and original_idx not in seen_ids:
                    clip_data = candidates[original_idx].copy()
                    clip_data["rank_score"] = rank_item.get("score")
                    clip_data["rank_reason"] = rank_item.get("reason")
                    final_results.append(clip_data)
                    seen_ids.add(original_idx)

            for idx, cand in enumerate(candidates):
                if idx not in seen_ids:
                    final_results.append(cand)

            return final_results

        except Exception as e:
            print(f"Warning: Ranker reranking failed: {e}")
            return candidates

    async def generate_visual_script(self, lyric, intent, library_context=None, video_description=None):
        """
        Convert lyrics and intent into concrete visual search terms.
        """
        library_info = f"\n素材库视觉摘要: {library_context}\n" if library_context else ""
        theme_info = f"\n视频素材背景知识: {video_description}\n" if video_description else ""

        prompt = f"""
        你是一位顶级视频剪辑导演。当前你正在处理一个重要的剪辑任务，请结合【剧本核心背景】和【当前素材库视觉概况】来构思镜头。

        【极其重要 - 剧本核心背景】：{video_description if video_description else "未提供，请根据素材内容自行推断"}

        【当前素材库视觉概况】：{library_context if library_context else "正在识别中"}

        【歌词内容】：{lyric}
        【剪辑意图】：{intent}

        任务要求：
        1. 逻辑对齐：结合【剧本核心背景】深度解读歌词。如果背景说是赛车电影，即便歌词很抽象，也要构思与赛车、速度、竞技相关的镜头。
        2. 视觉自洽：确保构思的画面在【素材库视觉概况】中具有可行性。
        3. 检索词精练：提供极其具体的英文检索词。

        输出格式：
        {{
            "reasoning": "中文，解释你如何根据【剧本核心背景】来解读这句歌词并转化为特定镜头",
            "visual_prompt": "英文，精简的视觉检索词，不超过 30 个单词"
        }}
        """

        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": "你是一个专业的短视频导演。你需要根据视频素材库背后的故事背景来调整你的创作逻辑。请直接输出 JSON。"},
                {"role": "user", "content": prompt}
            ],
            response_format={ "type": "json_object" }
        )

        data = json.loads(response.choices[0].message.content.strip())
        if 'visual_prompt' in data:
            words = data['visual_prompt'].split()
            if len(words) > 60:
                data['visual_prompt'] = " ".join(words[:60])
        return data

    async def analyze_video_library(self, image_paths):
        """
        Multi-image analysis of material library to generate a global tone report.
        """
        import base64

        def encode_image(image_path):
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')

        content = [{"type": "text", "text": "你是一个资深的素材库分析师。请分析以下这组来自同一视频（或素材库）的关键采样帧，并总结出该素材库的【核心视觉元素】、【主要场景类型】、【画面主色调】以及【动作风格】。这将作为后续 AI 剪辑导演的参考。请用一两句话简练概括。"}]

        sampled_paths = image_paths[:8]
        for img_path in sampled_paths:
            base64_image = encode_image(img_path)
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
            })

        try:
            response = self.client.chat.completions.create(
                model=self.vision_model_name,
                messages=[{"role": "user", "content": content}]
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"Warning: Library visual analysis failed: {e}")
            return "Analysis failed, please use general cinematic style."

    async def align_lyrics(self, whisper_segments, manual_lyrics):
        """
        Use LLM alignment: pair Whisper timestamps with accurate manual lyrics.
        """
        prompt = f"""
        任务：歌词文本与时间戳强制对齐
        背景：Whisper 在带背景音乐的情况下识别歌词非常不准确，会有很多错别字和幻听。

        【原始精准歌词】：
        {manual_lyrics}

        【Whisper 识别出的带时间戳草稿】：
        {json.dumps(whisper_segments, ensure_ascii=False)}

        任务要求：
        1. 请参考【原始精准歌词】，纠正【草稿段落】中的文字。
        2. 保持时间戳不变，只修改文字内容。
        3. 如果 Whisper 将一句精准歌词拆分成了多个时间段，请合理分配文字。
        4. 结果必须覆盖整首歌的时间线。

        输出格式：纯 JSON 数组
        [
            {{"start": 0.0, "end": 5.0, "text": "校准后的第一句"}},
            ...
        ]
        """

        response = self.client.chat.completions.create(
            model="qwen-turbo",
            messages=[
                {"role": "system", "content": "你是一个专业的歌词校准器。请直接输出 JSON 存储的结果。"},
                {"role": "user", "content": prompt}
            ],
            response_format={ "type": "json_object" }
        )

        content = response.choices[0].message.content.strip()
        try:
            data = json.loads(content)
            if isinstance(data, dict) and "segments" in data:
                return data["segments"]
            if isinstance(data, list):
                return data
            return data
        except:
            return whisper_segments
