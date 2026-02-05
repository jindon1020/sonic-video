"""
Abstract base class for LLM providers.

This module defines the interface that all LLM providers must implement,
enabling seamless switching between different LLM services.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    def __init__(self, api_key: str, model: str, **kwargs):
        """
        Initialize the LLM provider.

        Args:
            api_key: API key for the LLM service
            model: Model identifier (e.g., "gpt-4", "claude-3-5-sonnet")
            **kwargs: Additional provider-specific parameters
        """
        self.api_key = api_key
        self.model = model
        self.kwargs = kwargs

    @abstractmethod
    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs
    ) -> str:
        """
        Generate text from a prompt.

        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional provider-specific parameters

        Returns:
            str: Generated text
        """
        pass

    @abstractmethod
    async def generate_json(
        self,
        prompt: str,
        schema: Optional[Dict[str, Any]] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate structured JSON from a prompt.

        Args:
            prompt: The user prompt
            schema: Optional JSON schema for validation
            system_prompt: Optional system prompt
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional provider-specific parameters

        Returns:
            Dict[str, Any]: Parsed JSON object
        """
        pass

    @abstractmethod
    async def analyze_image(
        self,
        image_path: str,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs
    ) -> str:
        """
        Analyze a single image with a prompt.

        Args:
            image_path: Path to the image file
            prompt: The analysis prompt
            system_prompt: Optional system prompt
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional provider-specific parameters

        Returns:
            str: Analysis result
        """
        pass

    @abstractmethod
    async def analyze_multi_images(
        self,
        image_paths: List[str],
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs
    ) -> str:
        """
        Analyze multiple images with a prompt.

        Args:
            image_paths: List of image file paths
            prompt: The analysis prompt
            system_prompt: Optional system prompt
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional provider-specific parameters

        Returns:
            str: Analysis result
        """
        pass

    def get_model_info(self) -> Dict[str, str]:
        """
        Get information about the current model.

        Returns:
            Dict[str, str]: Model information (name, provider, etc.)
        """
        return {
            "model": self.model,
            "provider": self.__class__.__name__.replace("Provider", "").lower()
        }
