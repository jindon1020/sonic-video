import os
import json
from dotenv import load_dotenv

load_dotenv()

DEFAULT_CONFIG = {
    "api_keys": {
        "dashscope_api_key": "",
        "gemini_api_key": "",
        "openai_api_key": "",
        "anthropic_api_key": ""
    },
    "models": {
        "llm_model": "qwen-plus",
        "vision_model": "qwen-vl-plus",
        "gemini_model": "gemini-1.5-flash",
        "openai_model": "gpt-4o",
        "anthropic_model": "claude-3-5-sonnet-20241022",
        "clip_model": "ViT-B/32"
    },
    "llm_routing": {
        "default": "qwen",
        "tasks": {
            "visual_script": "qwen",
            "scene_analysis": "gemini",
            "lyrics_alignment": "qwen",
            "reranking": "qwen",
            "library_analysis": "gemini"
        }
    },
    "advanced": {
        "output_width": 1920,
        "output_height": 1080,
        "output_fps": 24,
        "scene_threshold": 3.0,
        "min_scene_length": 25,
        "max_scenes": 800,
        "concurrent_workers": 5,
        "vector_search_top_k": 40,
        "ai_fallback_score": 0.22
    }
}


class ConfigManager:
    def __init__(self):
        self._config_dir = os.path.join(
            os.path.expanduser("~"), "Library", "Application Support", "Sonic-AI"
        )
        self._config_path = os.path.join(self._config_dir, "config.json")
        self._data = {}
        self.load()

    def load(self):
        """Load config from disk, creating defaults if absent."""
        if os.path.exists(self._config_path):
            try:
                with open(self._config_path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._data = {}

        # Merge missing keys from defaults
        for section, defaults in DEFAULT_CONFIG.items():
            if section not in self._data:
                self._data[section] = dict(defaults)
            else:
                for key, val in defaults.items():
                    if key not in self._data[section]:
                        self._data[section][key] = val

        # .env fallback: environment variables fill empty API key slots
        env_keys = {
            "dashscope_api_key": os.getenv("DASHSCOPE_API_KEY", ""),
            "gemini_api_key": os.getenv("GEMINI_API_KEY", ""),
            "openai_api_key": os.getenv("OPENAI_API_KEY", ""),
            "anthropic_api_key": os.getenv("ANTHROPIC_API_KEY", "")
        }
        for key_name, env_value in env_keys.items():
            if not self._data["api_keys"].get(key_name) and env_value:
                self._data["api_keys"][key_name] = env_value

        self.save()

    def save(self):
        """Persist current config to disk."""
        os.makedirs(self._config_dir, exist_ok=True)
        with open(self._config_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)

    def get(self, section: str, key: str, default=None):
        """Get a single value.  e.g. config.get('models', 'llm_model')"""
        return self._data.get(section, {}).get(key, default)

    def set(self, section: str, key: str, value):
        """Set a single value and persist."""
        if section not in self._data:
            self._data[section] = {}
        self._data[section][key] = value
        self.save()

    def get_section(self, section: str) -> dict:
        return dict(self._data.get(section, {}))

    def update_section(self, section: str, values: dict):
        """Merge values into a section and persist."""
        if section not in self._data:
            self._data[section] = {}
        self._data[section].update(values)
        self.save()

    def to_dict(self) -> dict:
        """Return full config (deep copy)."""
        return json.loads(json.dumps(self._data))

    def to_safe_dict(self) -> dict:
        """Return config with API keys masked for frontend display."""
        data = self.to_dict()
        api_key_names = ("dashscope_api_key", "gemini_api_key", "openai_api_key", "anthropic_api_key")
        for key_name in api_key_names:
            raw = data.get("api_keys", {}).get(key_name, "")
            if raw and len(raw) > 8:
                data["api_keys"][key_name] = raw[:4] + "*" * (len(raw) - 8) + raw[-4:]
        return data
