"""
LLM Provider Factory

This module provides factory methods to create LLM provider instances
based on configuration and task requirements.
"""

from typing import Optional, Dict, Any
import os

from app.providers.base import LLMProvider
from app.providers.qwen import QwenProvider
from app.providers.gemini import GeminiProvider
from app.providers.openai import OpenAIProvider
from app.providers.anthropic import AnthropicProvider


class LLMProviderFactory:
    """Factory for creating LLM provider instances."""

    # Task-to-provider mapping (can be overridden by config)
    DEFAULT_TASK_ROUTING = {
        "visual_script": "qwen",       # Qwen excels at creative tasks
        "scene_analysis": "gemini",    # Gemini has strong vision understanding
        "lyrics_alignment": "qwen",    # Qwen is best for Chinese text
        "reranking": "qwen",           # Qwen for reasoning tasks
        "library_analysis": "gemini",  # Gemini for multi-image analysis
        "default": "qwen"              # Default to Qwen
    }

    @classmethod
    def create_provider(
        cls,
        provider_name: str,
        api_key: str,
        model: Optional[str] = None,
        **kwargs
    ) -> LLMProvider:
        """
        Create a specific LLM provider instance.

        Args:
            provider_name: Provider identifier ("qwen", "gemini", "openai", "anthropic")
            api_key: API key for the provider
            model: Optional model override
            **kwargs: Additional provider-specific parameters

        Returns:
            LLMProvider: Provider instance

        Raises:
            ValueError: If provider_name is not supported
        """
        provider_name = provider_name.lower()

        if provider_name == "qwen":
            return QwenProvider(
                api_key=api_key,
                model=model or "qwen-plus",
                **kwargs
            )
        elif provider_name == "gemini":
            return GeminiProvider(
                api_key=api_key,
                model=model or "gemini-1.5-flash",
                **kwargs
            )
        elif provider_name == "openai":
            return OpenAIProvider(
                api_key=api_key,
                model=model or "gpt-4o",
                **kwargs
            )
        elif provider_name == "anthropic":
            return AnthropicProvider(
                api_key=api_key,
                model=model or "claude-3-5-sonnet-20241022",
                **kwargs
            )
        else:
            raise ValueError(f"Unsupported provider: {provider_name}")

    @classmethod
    def from_config(cls, config: Any, task: Optional[str] = None) -> LLMProvider:
        """
        Create a provider based on ConfigManager settings.

        Args:
            config: ConfigManager instance
            task: Optional task identifier for task-based routing

        Returns:
            LLMProvider: Provider instance

        Raises:
            ValueError: If no valid API key is found
        """
        # Get routing configuration
        routing_config = config.get("llm_routing", "tasks", {})
        default_provider = config.get("llm_routing", "default", "qwen")

        # Determine which provider to use
        if task and task in routing_config:
            provider_name = routing_config[task]
        elif task and task in cls.DEFAULT_TASK_ROUTING:
            provider_name = cls.DEFAULT_TASK_ROUTING[task]
        else:
            provider_name = default_provider

        # Get API keys and models from config
        api_keys = {
            "qwen": config.get("api_keys", "dashscope_api_key") or os.getenv("DASHSCOPE_API_KEY"),
            "gemini": config.get("api_keys", "gemini_api_key") or os.getenv("GEMINI_API_KEY"),
            "openai": config.get("api_keys", "openai_api_key") or os.getenv("OPENAI_API_KEY"),
            "anthropic": config.get("api_keys", "anthropic_api_key") or os.getenv("ANTHROPIC_API_KEY")
        }

        models = {
            "qwen": config.get("models", "llm_model", "qwen-plus"),
            "gemini": config.get("models", "gemini_model", "gemini-1.5-flash"),
            "openai": config.get("models", "openai_model", "gpt-4o"),
            "anthropic": config.get("models", "anthropic_model", "claude-3-5-sonnet-20241022")
        }

        # Get API key for selected provider
        api_key = api_keys.get(provider_name)

        # Fallback logic: try other providers if selected one is not available
        if not api_key:
            print(f"Warning: No API key for {provider_name}, trying fallback providers...")
            for fallback in ["qwen", "gemini", "openai", "anthropic"]:
                if fallback != provider_name and api_keys.get(fallback):
                    provider_name = fallback
                    api_key = api_keys[fallback]
                    print(f"Falling back to {provider_name}")
                    break

        if not api_key:
            raise ValueError(
                "No valid API key found. Please configure at least one LLM provider "
                "in config or environment variables."
            )

        # Additional kwargs for specific providers
        kwargs = {}
        if provider_name == "qwen":
            kwargs["vision_model"] = config.get("models", "vision_model", "qwen-vl-plus")

        return cls.create_provider(
            provider_name=provider_name,
            api_key=api_key,
            model=models.get(provider_name),
            **kwargs
        )

    @classmethod
    def get_provider_for_task(
        cls,
        config: Any,
        task: str
    ) -> LLMProvider:
        """
        Convenience method to get a provider for a specific task.

        Args:
            config: ConfigManager instance
            task: Task identifier

        Returns:
            LLMProvider: Provider instance optimized for the task
        """
        return cls.from_config(config, task=task)
