"""
Anthropic Provider Implementation

This module implements the LLMProvider interface for Anthropic's Claude models.
"""

import json
import base64
from typing import List, Dict, Any, Optional
from anthropic import AsyncAnthropic

from app.providers.base import LLMProvider


class AnthropicProvider(LLMProvider):
    """LLM Provider for Anthropic Claude models."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-3-5-sonnet-20241022",
        **kwargs
    ):
        """
        Initialize Anthropic provider.

        Args:
            api_key: Anthropic API key
            model: Model identifier (default: "claude-3-5-sonnet-20241022")
            **kwargs: Additional parameters
        """
        super().__init__(api_key, model, **kwargs)
        self.client = AsyncAnthropic(api_key=self.api_key)

    def _encode_image(self, image_path: str) -> tuple[str, str]:
        """
        Encode image to base64 and detect media type.

        Returns:
            Tuple of (base64_data, media_type)
        """
        with open(image_path, "rb") as f:
            data = base64.standard_b64encode(f.read()).decode('utf-8')

        # Detect media type
        if image_path.lower().endswith('.png'):
            media_type = "image/png"
        elif image_path.lower().endswith(('.jpg', '.jpeg')):
            media_type = "image/jpeg"
        elif image_path.lower().endswith('.webp'):
            media_type = "image/webp"
        elif image_path.lower().endswith('.gif'):
            media_type = "image/gif"
        else:
            media_type = "image/jpeg"  # Default

        return data, media_type

    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs
    ) -> str:
        """Generate text using Claude."""
        messages = [{"role": "user", "content": prompt}]

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt if system_prompt else "",
            messages=messages,
            **kwargs
        )
        return response.content[0].text.strip()

    async def generate_json(
        self,
        prompt: str,
        schema: Optional[Dict[str, Any]] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate structured JSON using Claude."""
        json_instruction = "\n\nPlease respond with valid JSON only."
        full_prompt = f"{prompt}{json_instruction}"

        messages = [{"role": "user", "content": full_prompt}]

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt if system_prompt else "",
            messages=messages,
            **kwargs
        )

        content = response.content[0].text.strip()
        # Remove markdown code blocks if present
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]

        return json.loads(content.strip())

    async def analyze_image(
        self,
        image_path: str,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs
    ) -> str:
        """Analyze a single image using Claude Vision."""
        base64_data, media_type = self._encode_image(image_path)

        messages = [{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": base64_data
                    }
                },
                {"type": "text", "text": prompt}
            ]
        }]

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt if system_prompt else "",
            messages=messages,
            **kwargs
        )
        return response.content[0].text.strip()

    async def analyze_multi_images(
        self,
        image_paths: List[str],
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs
    ) -> str:
        """Analyze multiple images using Claude Vision."""
        content = []

        # Add images (limit to 8 for API constraints)
        for img_path in image_paths[:8]:
            base64_data, media_type = self._encode_image(img_path)
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": base64_data
                }
            })

        # Add text prompt
        content.append({"type": "text", "text": prompt})

        messages = [{"role": "user", "content": content}]

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt if system_prompt else "",
            messages=messages,
            **kwargs
        )
        return response.content[0].text.strip()
