"""
Background music management for YouTube Shorts.
Picks the best clip from the clips/ folder using GPT to match the video's mood.
"""
import json
import random
from pathlib import Path
from dataclasses import dataclass
from openai import OpenAI


@dataclass
class MusicTrack:
    """Metadata for a music track."""

    path: Path
    title: str


class MusicManager:
    """Picks the best music clip for a video from the clips/ folder.

    Randomly selects 3 candidates from clips/, then uses GPT to pick
    the one whose name best matches the fact's mood/category.
    """

    def __init__(self, clips_dir: Path, openai_api_key: str):
        self.clips_dir = clips_dir
        self.client = OpenAI(api_key=openai_api_key)

    def pick_track(self, hook: str, fact_text: str, category: str) -> MusicTrack:
        """Pick the best music track for this fact.

        Randomly samples 3 clips, asks GPT which name fits best,
        and returns that track.
        """
        all_clips = list(self.clips_dir.glob("*.mp3"))
        if not all_clips:
            raise FileNotFoundError(f"No mp3 files found in {self.clips_dir}")

        # Pick 3 random candidates (or fewer if less than 3 available)
        candidates = random.sample(all_clips, min(3, len(all_clips)))

        # If only 1 clip, just return it
        if len(candidates) == 1:
            return MusicTrack(path=candidates[0], title=candidates[0].stem)

        # Ask GPT which track name fits the mood best
        track_names = [c.stem for c in candidates]
        prompt = f"""I'm making a YouTube Short with this content:

Hook: {hook}
Fact: {fact_text}
Category: {category}

Which background music track fits the mood best? Pick ONE.

Options:
{chr(10).join(f'{i}. {name}' for i, name in enumerate(track_names))}

Respond with JSON only:
{{"best_index": 0, "reason": "brief reason"}}"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You pick background music for short videos. Respond with JSON only."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=100,
            )

            content = response.choices[0].message.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            data = json.loads(content.strip())
            idx = data["best_index"]
            if 0 <= idx < len(candidates):
                chosen = candidates[idx]
                print(f"    GPT picked: {chosen.stem} — {data.get('reason', '')}")
                return MusicTrack(path=chosen, title=chosen.stem)
        except Exception as e:
            print(f"    GPT music selection failed ({e}), picking randomly")

        # Fallback: random pick
        chosen = random.choice(candidates)
        return MusicTrack(path=chosen, title=chosen.stem)
