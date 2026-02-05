"""
OpenAI Provider Implementation

This module implements the LLMProvider interface for OpenAI's GPT models.
"""

import json
import base64
from typing import List, Dict, Any, Optional
from openai import AsyncOpenAI

from app.providers.base import LLMProvider


class OpenAIProvider(LLMProvider):
    """LLM Provider for OpenAI GPT models."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o",
        **kwargs
    ):
        """
        Initialize OpenAI provider.

        Args:
            api_key: OpenAI API key
            model: Model identifier (default: "gpt-4o")
            **kwargs: Additional parameters
        """
        super().__init__(api_key, model, **kwargs)
        self.client = AsyncOpenAI(api_key=self.api_key)

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
        """Generate text using GPT."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = await self.client.chat.completions.create(
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
        """Generate structured JSON using GPT."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = await self.client.chat.completions.create(
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
        """Analyze a single image using GPT-4 Vision."""
        base64_image = self._encode_image(image_path)

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                }
            ]
        })

        response = await self.client.chat.completions.create(
            model=self.model,
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
        """Analyze multiple images using GPT-4 Vision."""
        content = [{"type": "text", "text": prompt}]

        # Sample max 8 images for API limits
        for img_path in image_paths[:8]:
            base64_image = self._encode_image(img_path)
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
            })

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": content})

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )
        return response.choices[0].message.content.strip()
