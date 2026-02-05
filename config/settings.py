"""
Configuration management for YouTube Shorts generator.
Loads API keys from environment variables.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root
load_dotenv(Path(__file__).parent.parent / ".env")


class Settings:
    """Application settings loaded from environment."""

    def __init__(self):
        # API Keys
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        self.pexels_api_key = os.getenv("PEXELS_API_KEY", "")
        self.pixabay_api_key = os.getenv("PIXABAY_API_KEY", "")

        # Video Settings
        self.video_width = 1080
        self.video_height = 1920
        self.video_fps = 30
        self.default_duration = 8  # seconds (under 10 for quick shorts)

        # Text Settings
        self.font_size_hook = 64
        self.font_size_fact = 42
        self.text_color = (255, 255, 255)  # White
        self.bg_color = (0, 0, 0)  # Black background
        # Note: highlight_color is now randomized per video in TextRenderer

        # Channel Branding
        self.channel_name = "Daily Incredible Facts"
        self.channel_handle = "@daily_incredible_facts"

        # Paths
        self.base_dir = Path(__file__).parent.parent
        self.assets_dir = self.base_dir / "assets"
        self.logo_path = self.assets_dir / "logo.png"
        self.cache_dir = self.base_dir / "cache"
        self.video_cache_dir = self.cache_dir / "videos"
        self.music_cache_dir = self.cache_dir / "music"
        self.output_dir = self.base_dir / "output"

        # YouTube Audio Library music folder (for trending sounds)
        # Download tracks from: https://studio.youtube.com/channel/UC/music
        self.yt_music_dir = self.assets_dir / "music"

        # Ensure directories exist
        self.video_cache_dir.mkdir(parents=True, exist_ok=True)
        self.music_cache_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.yt_music_dir.mkdir(parents=True, exist_ok=True)

    def validate(self) -> list[str]:
        """Validate settings and return list of errors."""
        errors = []

        if not self.openai_api_key:
            errors.append("OPENAI_API_KEY not set")

        if not self.pexels_api_key and not self.pixabay_api_key:
            errors.append("At least one of PEXELS_API_KEY or PIXABAY_API_KEY required")

        return errors


# Global settings instance
settings = Settings()
