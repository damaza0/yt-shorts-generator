"""
GPT Vision verification for video content.
Extracts frames from a video and asks GPT-4o to confirm the subject matches the description.
Also determines the best timestamp and vertical position of the subject for smart cropping.
"""
import json
import base64
import subprocess
import tempfile
from pathlib import Path
from dataclasses import dataclass
from openai import OpenAI


@dataclass
class VisionVerification:
    """Result of vision-based video verification."""
    approved: bool
    explanation: str
    best_frame: int = 1  # Which frame (1-based) shows subject most clearly
    video_duration: float = 0.0  # Total duration of source video


class VisionReviewer:
    """Uses GPT-4o vision to verify video content."""

    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)

    def _extract_frames(self, video_path: Path, num_frames: int = 6) -> list[str]:
        """Extract evenly-spaced frames from a video as base64 JPEG strings."""
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(video_path),
            ],
            capture_output=True, text=True, timeout=10,
        )
        duration = float(result.stdout.strip())

        frames = []
        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(num_frames):
                timestamp = (duration / (num_frames + 1)) * (i + 1)
                frame_path = Path(tmpdir) / f"frame_{i}.jpg"

                subprocess.run(
                    [
                        "ffmpeg", "-ss", str(timestamp),
                        "-i", str(video_path),
                        "-vframes", "1",
                        "-q:v", "3",
                        str(frame_path),
                    ],
                    capture_output=True, timeout=10,
                )

                if frame_path.exists():
                    with open(frame_path, "rb") as f:
                        b64 = base64.b64encode(f.read()).decode("utf-8")
                        frames.append(b64)

        return frames, duration

    def verify_video_content(self, video_path: Path, expected_description: str) -> VisionVerification:
        """Verify that a video actually shows what its description says.

        Also determines:
        - Which frame shows the subject most clearly (for start time)
        - Where the subject sits vertically in the frame (for crop offset)
        """
        print("    Running GPT Vision verification...")
        frames, duration = self._extract_frames(video_path, num_frames=6)

        if not frames:
            return VisionVerification(
                approved=False,
                explanation="Could not extract frames from video",
                video_duration=0.0,
            )

        content = [
            {
                "type": "text",
                "text": (
                    f"I have a stock video described as: \"{expected_description}\"\n\n"
                    f"Here are {len(frames)} evenly-spaced frames from the video (frame 1 is earliest, frame {len(frames)} is latest).\n\n"
                    "Answer these questions:\n"
                    "1. Does the video actually show what the description says? (matches: true/false)\n"
                    "   IMPORTANT: If the description mentions an animal, creature, or living thing, "
                    "the video MUST show the REAL, LIVING version — NOT a statue, fountain, sculpture, "
                    "toy, painting, decoration, logo, stuffed animal, or any artificial representation. "
                    "If you see a fake/artificial version instead of the real thing, set matches to FALSE.\n"
                    "2. Which frame number shows the subject MOST clearly? (best_frame: 1-6)\n"
                    "3. Brief explanation of what you see.\n\n"
                    "Respond with JSON only:\n"
                    "{\n"
                    '  "matches": true/false,\n'
                    '  "best_frame": 1-6,\n'
                    '  "explanation": "what you see"\n'
                    "}"
                ),
            }
        ]

        for i, frame_b64 in enumerate(frames):
            content.append({
                "type": "text",
                "text": f"Frame {i+1}:",
            })
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{frame_b64}",
                    "detail": "low",
                },
            })

        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "You verify video content and analyze subject positioning. Respond with JSON only.",
                },
                {"role": "user", "content": content},
            ],
            max_tokens=300,
        )

        result_text = response.choices[0].message.content
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0]
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0]

        data = json.loads(result_text.strip())
        approved = data.get("matches", False)
        explanation = data.get("explanation", "")
        best_frame = data.get("best_frame", 1)

        print(f"    Vision result: {'APPROVED' if approved else 'REJECTED'} - {explanation[:80]}")
        if approved:
            print(f"    Best frame: {best_frame}/{len(frames)}")

        return VisionVerification(
            approved=approved,
            explanation=explanation,
            best_frame=best_frame,
            video_duration=duration,
        )

    def get_best_start_time(self, verification: VisionVerification) -> float:
        """Calculate the best start time based on which frame was best.

        Frames are evenly spaced, so frame N corresponds to roughly:
        timestamp = (duration / 7) * N  (for 6 frames)

        We start a couple seconds before the best frame to give context.
        """
        if verification.video_duration <= 0:
            return 0.0

        num_frames = 6
        frame_time = (verification.video_duration / (num_frames + 1)) * verification.best_frame
        # Start 1 second before the best frame, clamped to 0
        start = max(0.0, frame_time - 1.0)
        return start
