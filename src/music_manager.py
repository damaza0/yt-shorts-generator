"""
Background music management for YouTube Shorts.
Uses free/open music sources for viral background tracks.
"""
import requests
import random
from pathlib import Path
from dataclasses import dataclass


@dataclass
class MusicTrack:
    """Metadata for a music track."""

    path: Path
    title: str
    artist: str
    duration: int
    source: str
    source_url: str


class MusicManager:
    """Manages royalty-free music for YouTube Shorts.

    BEST OPTION FOR TRENDING SOUNDS:
    1. Go to YouTube Studio > Audio Library (https://studio.youtube.com/channel/UC/music)
    2. Filter by "Popular" or browse trending tracks
    3. Download your favorite tracks
    4. Place them in assets/music/ folder
    5. Run with: python main.py generate --music-dir assets/music

    Popular trending sounds for Shorts (download these from YouTube Audio Library):
    - "Blade Runner 2049" by Aakash Gandhi (dramatic)
    - "Better Days" by NEFFEX (upbeat)
    - "Cradles" by Sub Urban (viral sound)
    - "Legends Never Die" by Against The Current (epic)
    - "Dreams" by Joakim Karud (chill hip-hop)
    """

    # Royalty-free music from Kevin MacLeod (incompetech.com)
    # All tracks licensed under Creative Commons: By Attribution 4.0
    # Dark, dramatic, and mysterious tracks to match disturbing/creepy facts
    FALLBACK_TRACKS = [
        # Dark & Creepy
        {
            "id": "dark_fog",
            "title": "Dark Fog",
            "artist": "Kevin MacLeod",
            "duration": 180,
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Dark%20Fog.mp3",
        },
        {
            "id": "danse_macabre",
            "title": "Danse Macabre",
            "artist": "Kevin MacLeod",
            "duration": 150,
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Danse%20Macabre.mp3",
        },
        {
            "id": "dark_times",
            "title": "Dark Times",
            "artist": "Kevin MacLeod",
            "duration": 180,
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Dark%20Times.mp3",
        },
        {
            "id": "nightmare_machine",
            "title": "Nightmare Machine",
            "artist": "Kevin MacLeod",
            "duration": 150,
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Nightmare%20Machine.mp3",
        },
        # Dramatic & Epic
        {
            "id": "epic_unease",
            "title": "Epic Unease",
            "artist": "Kevin MacLeod",
            "duration": 180,
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Epic%20Unease.mp3",
        },
        {
            "id": "intrepid",
            "title": "Intrepid",
            "artist": "Kevin MacLeod",
            "duration": 180,
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Intrepid.mp3",
        },
        {
            "id": "hitman",
            "title": "Hitman",
            "artist": "Kevin MacLeod",
            "duration": 150,
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Hitman.mp3",
        },
        # Mysterious & Suspenseful
        {
            "id": "investigations",
            "title": "Investigations",
            "artist": "Kevin MacLeod",
            "duration": 180,
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Investigations.mp3",
        },
        {
            "id": "cipher2",
            "title": "Cipher2",
            "artist": "Kevin MacLeod",
            "duration": 150,
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Cipher2.mp3",
        },
        {
            "id": "oppressive_gloom",
            "title": "Oppressive Gloom",
            "artist": "Kevin MacLeod",
            "duration": 150,
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Oppressive%20Gloom.mp3",
        },
        # Intense & Ominous
        {
            "id": "volatile_reaction",
            "title": "Volatile Reaction",
            "artist": "Kevin MacLeod",
            "duration": 180,
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Volatile%20Reaction.mp3",
        },
        {
            "id": "aggressor",
            "title": "Aggressor",
            "artist": "Kevin MacLeod",
            "duration": 150,
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Aggressor.mp3",
        },
        {
            "id": "heart_of_nowhere",
            "title": "Heart of Nowhere",
            "artist": "Kevin MacLeod",
            "duration": 200,
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Heart%20of%20Nowhere.mp3",
        },
        # Atmospheric & Eerie
        {
            "id": "ossuary_6_air",
            "title": "Ossuary 6 - Air",
            "artist": "Kevin MacLeod",
            "duration": 180,
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Ossuary%206%20-%20Air.mp3",
        },
        {
            "id": "ghost_story",
            "title": "Ghost Story",
            "artist": "Kevin MacLeod",
            "duration": 180,
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Ghost%20Story.mp3",
        },
    ]

    def __init__(self, api_key: str, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_random_track(self, min_duration: int = 10) -> MusicTrack:
        """Get a random music track from fallback library."""
        # Use Kevin MacLeod tracks (guaranteed to work, monetization-safe)
        # User should download YouTube Audio Library tracks manually for auto-tagging
        suitable = [t for t in self.FALLBACK_TRACKS if t["duration"] >= min_duration]
        if not suitable:
            suitable = self.FALLBACK_TRACKS

        # Pick random track
        track_data = random.choice(suitable)
        cache_path = self.cache_dir / f"music_{track_data['id']}.mp3"

        if not cache_path.exists():
            print(f"    Downloading music: {track_data['title']}...")
            try:
                headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
                response = requests.get(track_data["url"], stream=True, timeout=30, headers=headers)
                response.raise_for_status()
                with open(cache_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
            except Exception as e:
                print(f"    Warning: Could not download music: {e}")
                cache_path = None
        else:
            print(f"    Using cached music: {track_data['title']}")

        return MusicTrack(
            path=cache_path,
            title=track_data["title"],
            artist=track_data["artist"],
            duration=track_data["duration"],
            source="Kevin MacLeod (incompetech.com)",
            source_url="https://incompetech.com",
        )

    def get_local_track(self, track_path: Path) -> MusicTrack:
        """Use a locally downloaded track (e.g., from YouTube Audio Library)."""
        if not track_path.exists():
            raise FileNotFoundError(f"Track not found: {track_path}")

        return MusicTrack(
            path=track_path,
            title=track_path.stem,  # Use filename as title
            artist="YouTube Audio Library",
            duration=300,  # Placeholder
            source="YouTube Audio Library",
            source_url="https://studio.youtube.com/channel/UC/music",
        )

    def get_track_info_for_youtube(self, track: MusicTrack) -> str:
        """Get formatted track info for YouTube description."""
        return f"Music: {track.title} by {track.artist} (from {track.source_url})"
