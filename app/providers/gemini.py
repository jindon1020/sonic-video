"""
Gemini Provider Implementation

This module implements the LLMProvider interface for Google's Gemini models.
"""

import json
from typing import List, Dict, Any, Optional
import google.generativeai as genai
from PIL import Image

from app.providers.base import LLMProvider


class GeminiProvider(LLMProvider):
    """LLM Provider for Google Gemini models."""

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-1.5-flash",
        **kwargs
    ):
        """
        Initialize Gemini provider.

        Args:
            api_key: Google AI API key
            model: Model identifier (default: "gemini-1.5-flash")
            **kwargs: Additional parameters
        """
        super().__init__(api_key, model, **kwargs)

        # Configure Gemini
        genai.configure(api_key=self.api_key)
        self.client = genai.GenerativeModel(self.model)

    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs
    ) -> str:
        """Generate text using Gemini."""
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"

        generation_config = genai.GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
            **kwargs
        )

        response = self.client.generate_content(
            full_prompt,
            generation_config=generation_config
        )
        return response.text.strip()

    async def generate_json(
        self,
        prompt: str,
        schema: Optional[Dict[str, Any]] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate structured JSON using Gemini."""
        json_instruction = "\n\nPlease respond with valid JSON only."
        full_prompt = f"{prompt}{json_instruction}"

        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{full_prompt}"

        generation_config = genai.GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
            response_mime_type="application/json",
            **kwargs
        )

        response = self.client.generate_content(
            full_prompt,
            generation_config=generation_config
        )

        content = response.text.strip()
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
        """Analyze a single image using Gemini Vision."""
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"

        generation_config = genai.GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
            **kwargs
        )

        # Load image
        img = Image.open(image_path)

        response = self.client.generate_content(
            [full_prompt, img],
            generation_config=generation_config
        )
        return response.text.strip()

    async def analyze_multi_images(
        self,
        image_paths: List[str],
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs
    ) -> str:
        """Analyze multiple images using Gemini Vision."""
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"

        generation_config = genai.GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
            **kwargs
        )

        # Load images (limit to 8 for API constraints)
        content_parts = [full_prompt]
        for img_path in image_paths[:8]:
            img = Image.open(img_path)
            content_parts.append(img)

        response = self.client.generate_content(
            content_parts,
            generation_config=generation_config
        )
        return response.text.strip()
