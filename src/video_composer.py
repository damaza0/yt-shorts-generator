"""
Video composition using MoviePy.
Assembles text, video clips, and music into final YouTube Short.
Uses YOLOv8 for precise subject detection and centering.
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
        self._yolo_model = None  # Lazy-loaded

    def _get_yolo_model(self):
        """Lazy-load YOLOv8 nano model (only loads once)."""
        if self._yolo_model is None:
            from ultralytics import YOLO
            self._yolo_model = YOLO("yolov8n.pt")
            print("    YOLO model loaded")
        return self._yolo_model

    def _detect_subject_center(self, clip: VideoFileClip) -> dict:
        """Use YOLOv8 to find the subject's center coordinates in the video.

        Samples 5 evenly-spaced frames, runs object detection on each,
        picks the largest/most prominent detection, and averages its center
        position across frames.

        Returns:
            dict with 'center_y_pct' (0-100, percent from top) and
            'center_x_pct' (0-100, percent from left). Returns 50/50 if
            no objects detected (fallback to center crop).
        """
        model = self._get_yolo_model()
        num_samples = 5

        # Sample frames evenly across the clip
        frame_times = [
            (clip.duration / (num_samples + 1)) * (i + 1)
            for i in range(num_samples)
        ]

        all_centers_y = []
        all_centers_x = []

        for t in frame_times:
            try:
                frame = clip.get_frame(min(t, clip.duration - 0.1))
            except Exception:
                continue

            # Run YOLO detection (verbose=False suppresses output)
            results = model(frame, verbose=False)

            if len(results) == 0 or len(results[0].boxes) == 0:
                continue

            # Find the largest detection by area (most prominent subject)
            boxes = results[0].boxes
            best_box = None
            best_area = 0

            for box in boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                area = (x2 - x1) * (y2 - y1)
                if area > best_area:
                    best_area = area
                    best_box = (x1, y1, x2, y2)

            if best_box:
                x1, y1, x2, y2 = best_box
                center_y = (y1 + y2) / 2
                center_x = (x1 + x2) / 2
                # Convert to percentage of frame dimensions
                all_centers_y.append(center_y / frame.shape[0] * 100)
                all_centers_x.append(center_x / frame.shape[1] * 100)

        if not all_centers_y:
            print("    YOLO: No objects detected, defaulting to center crop")
            return {"center_y_pct": 50, "center_x_pct": 50}

        avg_y = sum(all_centers_y) / len(all_centers_y)
        avg_x = sum(all_centers_x) / len(all_centers_x)
        print(f"    YOLO: Subject center at {avg_y:.0f}% from top, {avg_x:.0f}% from left ({len(all_centers_y)}/{num_samples} frames)")

        return {"center_y_pct": avg_y, "center_x_pct": avg_x}

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
                audio = audio.with_effects([MultiplyVolume(0.5)])
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

        Uses start_time to pick the best segment, then runs YOLOv8 to detect
        the subject and centers the crop on it.
        """
        target_width = self.width  # 1080
        target_height = self.video_height  # 750

        # --- Temporal: pick the best segment ---
        if start_time > 0 and clip.duration > self.duration:
            max_start = clip.duration - self.duration
            actual_start = min(start_time, max_start)
            clip = clip.subclipped(actual_start, actual_start + self.duration)

        # --- Detect subject BEFORE scaling (run YOLO on original resolution) ---
        subject = self._detect_subject_center(clip)
        subject_y_pct = subject["center_y_pct"]
        subject_x_pct = subject["center_x_pct"]

        # Calculate scaling to COVER target area (scale up to fill, then crop)
        scale_w = target_width / clip.w
        scale_h = target_height / clip.h
        scale = max(scale_w, scale_h)  # Use max to ensure full coverage

        # Resize to cover
        clip = clip.resized(scale)

        # --- Spatial: crop centered on the subject ---
        excess_y = clip.h - target_height
        excess_x = clip.w - target_width

        if excess_y > 0:
            # The subject's center in the scaled frame (in pixels)
            subject_center_y = int(clip.h * subject_y_pct / 100)
            # We want the subject center to be at the middle of our crop window
            y1 = subject_center_y - (target_height // 2)
            # Clamp so we don't go out of bounds
            y1 = max(0, min(y1, excess_y))
        else:
            y1 = 0

        if excess_x > 0:
            subject_center_x = int(clip.w * subject_x_pct / 100)
            x1 = subject_center_x - (target_width // 2)
            x1 = max(0, min(x1, excess_x))
        else:
            x1 = 0

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
