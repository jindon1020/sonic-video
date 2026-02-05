"""
Qwen Provider Implementation for DashScope API

This module implements the LLMProvider interface for Alibaba Cloud's Qwen models.
"""

import json
import base64
from typing import List, Dict, Any, Optional
from openai import OpenAI

from app.providers.base import LLMProvider


class QwenProvider(LLMProvider):
    """LLM Provider for Alibaba Cloud Qwen models via DashScope API."""

    def __init__(
        self,
        api_key: str,
        model: str = "qwen-plus",
        vision_model: str = "qwen-vl-plus",
        **kwargs
    ):
        """
        Initialize Qwen provider.

        Args:
            api_key: DashScope API key
            model: Text model identifier (default: "qwen-plus")
            vision_model: Vision model identifier (default: "qwen-vl-plus")
            **kwargs: Additional parameters
        """
        super().__init__(api_key, model, **kwargs)
        self.vision_model = vision_model

        # Initialize OpenAI-compatible client for DashScope
        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )

    def _encode_image(self, image_path: str) -> str:
        """Encode image to base64 string."""
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode('utf-8')

    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs
    ) -> str:
        """Generate text using Qwen text model."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )
        return response.choices[0].message.content.strip()

    async def generate_json(
        self,
        prompt: str,
        schema: Optional[Dict[str, Any]] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate structured JSON using Qwen text model."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
            **kwargs
        )

        content = response.choices[0].message.content.strip()
        return json.loads(content)

    async def analyze_image(
        self,
        image_path: str,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs
    ) -> str:
        """Analyze a single image using Qwen-VL."""
        base64_image = self._encode_image(image_path)

        content = [
            {"type": "text", "text": prompt},
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
            }
        ]

        messages = [{"role": "user", "content": content}]

        response = self.client.chat.completions.create(
            model=self.vision_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )
        return response.choices[0].message.content.strip()

    async def analyze_multi_images(
        self,
        image_paths: List[str],
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs
    ) -> str:
        """Analyze multiple images using Qwen-VL."""
        content = [{"type": "text", "text": prompt}]

        # Sample max 8 images for API limits
        sampled_paths = image_paths[:8]
        for img_path in sampled_paths:
            base64_image = self._encode_image(img_path)
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
            })

        messages = [{"role": "user", "content": content}]

        response = self.client.chat.completions.create(
            model=self.vision_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )
        return response.choices[0].message.content.strip()

    async def analyze_scene_semantics(self, image_path: str) -> Dict[str, Any]:
        """
        Deep semantic analysis of a scene (returns structured data).

        Returns:
            Dict with keys: action, mood, objects, description
        """
        prompt = """
        You are a professional video content analyst. Please extract structured information in English:
        {
            "action": "Description of the main action (e.g., person turning back)",
            "mood": "Emotional tone (e.g., mysterious, epic, peaceful)",
            "objects": ["object1", "object2"],
            "description": "Detailed visual semantic description in English"
        }
        """

        base64_image = self._encode_image(image_path)

        response = self.client.chat.completions.create(
            model=self.vision_model,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                    }
                ],
            }],
            response_format={"type": "json_object"}
        )

        try:
            return json.loads(response.choices[0].message.content.strip())
        except:
            return {
                "action": "Processing error",
                "mood": "Unknown",
                "objects": [],
                "description": "Unable to analyze visual content"
            }

    async def generate_visual_script(
        self,
        lyric: str,
        intent: str,
        library_context: Optional[str] = None,
        video_description: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Convert lyrics and intent into concrete visual search terms.

        Returns:
            Dict with keys: reasoning, visual_prompt
        """
        library_info = f"\n素材库视觉摘要: {library_context}\n" if library_context else ""
        theme_info = f"\n视频素材背景知识: {video_description}\n" if video_description else ""

        prompt = f"""
        你是一位顶级视频剪辑导演。当前你正在处理一个重要的剪辑任务,请结合【剧本核心背景】和【当前素材库视觉概况】来构思镜头。

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
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "你是一个专业的短视频导演。你需要根据视频素材库背后的故事背景来调整你的创作逻辑。请直接输出 JSON。"
                },
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )

        data = json.loads(response.choices[0].message.content.strip())

        # Limit visual_prompt length
        if 'visual_prompt' in data:
            words = data['visual_prompt'].split()
            if len(words) > 60:
                data['visual_prompt'] = " ".join(words[:60])

        return data

    async def rerank_clips(self, query: str, candidates: List[Dict]) -> List[Dict]:
        """
        Rerank candidate clips based on semantic matching with query.

        Args:
            query: Visual search query
            candidates: List of candidate clips with metadata

        Returns:
            Reranked list of clips with scores and reasons
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
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a precise search ranking algorithm. Output JSON directly."
                    },
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
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

            # Add remaining candidates
            for idx, cand in enumerate(candidates):
                if idx not in seen_ids:
                    final_results.append(cand)

            return final_results

        except Exception as e:
            print(f"Warning: Ranker reranking failed: {e}")
            return candidates

    async def align_lyrics(
        self,
        whisper_segments: List[Dict],
        manual_lyrics: str
    ) -> List[Dict]:
        """
        Align manual lyrics with Whisper-detected timestamps.

        Args:
            whisper_segments: Whisper output with timestamps
            manual_lyrics: Accurate manual lyrics text

        Returns:
            Aligned segments with corrected text
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
                {
                    "role": "system",
                    "content": "你是一个专业的歌词校准器。请直接输出 JSON 存储的结果。"
                },
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
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
