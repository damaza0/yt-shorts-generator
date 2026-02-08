"""
Video composition using MoviePy.
Assembles text, video clips, and music into final YouTube Short.
"""
from pathlib import Path
from moviepy import (
    VideoFileClip,
    ImageClip,
    AudioFileClip,
    CompositeVideoClip,
    concatenate_videoclips,
)
from moviepy.audio.fx import MultiplyVolume
import numpy as np


class VideoComposer:
    """Composes final YouTube Short from components."""

    def __init__(
        self,
        width: int = 1080,
        height: int = 1920,
        fps: int = 30,
        duration: int = 8,
    ):
        self.width = width
        self.height = height
        self.fps = fps
        self.duration = duration
        # Text takes top portion, video takes bottom portion with padding
        self.bottom_padding = 180  # More padding at bottom of screen (3x previous)
        self.video_height = 750  # Smaller video to accommodate more bottom padding
        self.text_height = height - self.video_height - self.bottom_padding  # ~990px for text

    def compose(
        self,
        text_image_path: Path,
        video_clip_path: Path,
        output_path: Path,
        music_path: Path = None,
        start_time: float = 0.0,
    ) -> Path:
        """Compose final video with text on top, video on bottom, and music.

        Args:
            start_time: Where to start playing the source video (seconds).
        """

        # Create black background
        bg_array = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        background = ImageClip(bg_array).with_duration(self.duration)

        # Load and prepare text image (top half)
        text_clip = (
            ImageClip(str(text_image_path))
            .with_duration(self.duration)
            .resized(width=self.width)
            .with_position(("center", 0))
        )

        # Load and prepare video clip (below text, with bottom padding)
        video_clip = VideoFileClip(str(video_clip_path))
        video_clip = self._prepare_video_clip(video_clip, start_time)
        # Position video below text area, leaving padding at bottom
        video_y = self.text_height
        video_clip = video_clip.with_position(("center", video_y))

        # Composite the clips
        final = CompositeVideoClip(
            [background, text_clip, video_clip],
            size=(self.width, self.height),
        )

        # Add music if provided
        audio = None
        if music_path and music_path.exists():
            try:
                audio = AudioFileClip(str(music_path))
                # Trim audio to match video duration
                if audio.duration > self.duration:
                    audio = audio.subclipped(0, self.duration)
                # Lower music volume to sit in the background
                audio = audio.with_effects([MultiplyVolume(0.15)])
                final = final.with_audio(audio)
            except Exception as e:
                print(f"    Warning: Could not add music: {e}")

        # Write output
        print(f"    Encoding video to {output_path.name}...")
        final.write_videofile(
            str(output_path),
            fps=self.fps,
            codec="libx264",
            audio_codec="aac",
            preset="medium",
            threads=4,
            logger=None,  # Suppress moviepy output
        )

        # Cleanup
        video_clip.close()
        final.close()
        if music_path:
            try:
                audio.close()
            except:
                pass

        return output_path

    def _prepare_video_clip(
        self,
        clip: VideoFileClip,
        start_time: float = 0.0,
    ) -> VideoFileClip:
        """Resize and crop video to fit video area exactly (no letterboxing).

        Uses start_time to pick the best segment, then center-crops to fit.
        """
        target_width = self.width  # 1080
        target_height = self.video_height  # 750

        # --- Temporal: pick the best segment ---
        if start_time > 0 and clip.duration > self.duration:
            max_start = clip.duration - self.duration
            actual_start = min(start_time, max_start)
            clip = clip.subclipped(actual_start, actual_start + self.duration)

        # Calculate scaling to COVER target area (scale up to fill, then crop)
        scale_w = target_width / clip.w
        scale_h = target_height / clip.h
        scale = max(scale_w, scale_h)  # Use max to ensure full coverage

        # Resize to cover
        clip = clip.resized(scale)

        # Center crop
        excess_y = clip.h - target_height
        excess_x = clip.w - target_width
        y1 = max(0, excess_y // 2)
        x1 = max(0, excess_x // 2)

        clip = clip.cropped(
            x1=x1,
            y1=y1,
            width=target_width,
            height=target_height,
        )

        # Loop if needed to fill duration
        if clip.duration < self.duration:
            loops_needed = int(np.ceil(self.duration / clip.duration))
            clips_to_concat = [clip] * loops_needed
            clip = concatenate_videoclips(clips_to_concat)

        # Trim to exact duration
        clip = clip.subclipped(0, self.duration)

        # Remove audio from video (we'll use music instead)
        clip = clip.without_audio()

        return clip
