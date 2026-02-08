"""
Stock video fetching from Pexels API.
Downloads vertical/portrait videos for viral content.
Uses GPT to evaluate video descriptions for quality and fact potential.
"""
from __future__ import annotations

import json
import requests
import random
import re
from pathlib import Path
from dataclasses import dataclass
from openai import OpenAI


@dataclass
class VideoClip:
    """Metadata for a downloaded video clip."""

    path: Path
    url: str
    duration: int
    width: int
    height: int
    source: str  # "pexels"
    description: str  # What the video shows (extracted from URL)
    search_term: str  # The search term that found this video


# Search topics - focus on SPECIFIC subjects that have interesting fact potential
VIRAL_TOPICS = [
    # Animals - mammals
    "lion", "tiger", "elephant", "wolf", "bear", "fox", "deer", "horse",
    "gorilla", "cheetah", "leopard", "giraffe", "zebra", "rhino", "hippo",
    "kangaroo", "koala", "panda", "monkey", "chimpanzee", "orangutan",
    "sloth", "otter", "seal", "walrus", "polar bear", "buffalo", "moose",
    "camel", "platypus", "pangolin", "capybara", "red panda", "armadillo",
    "porcupine", "hedgehog", "bat", "raccoon", "badger", "weasel",
    "wolverine", "hyena", "jackal", "wild boar", "bison", "yak",
    "meerkat", "lemur", "tapir", "manatee", "narwhal", "wombat",

    # Animals - marine
    "shark", "dolphin", "whale", "octopus", "jellyfish", "sea turtle",
    "manta ray", "stingray", "seahorse", "clownfish", "orca", "squid",
    "crab", "lobster", "starfish", "coral", "anemone", "pufferfish",
    "moray eel", "sea otter", "barracuda", "swordfish", "tuna",
    "hammerhead shark", "whale shark", "nautilus", "sea lion",
    "hermit crab", "sea urchin", "anglerfish", "parrotfish",

    # Animals - birds
    "eagle", "owl", "parrot", "hummingbird", "peacock", "flamingo",
    "penguin", "hawk", "falcon", "toucan", "pelican", "swan", "crane",
    "heron", "kingfisher", "woodpecker", "crow", "raven", "albatross",
    "ostrich", "condor", "vulture", "robin", "cardinal", "blue jay",
    "stork", "ibis", "kiwi bird", "cockatoo", "macaw",

    # Animals - reptiles & amphibians
    "snake", "crocodile", "alligator", "iguana", "chameleon", "gecko",
    "komodo dragon", "tortoise", "frog", "salamander", "lizard",
    "python", "cobra", "rattlesnake", "sea snake", "tree frog",
    "poison dart frog", "axolotl", "newt", "monitor lizard",

    # Animals - insects & arachnids
    "spider", "tarantula", "scorpion", "bee", "butterfly", "dragonfly",
    "ant", "beetle", "ladybug", "moth", "firefly", "grasshopper",
    "caterpillar", "praying mantis", "wasp", "hornet", "termite",
    "centipede", "millipede", "stick insect", "cicada",

    # Space & astronomy
    "galaxy", "nebula", "planet", "moon", "stars", "sun", "eclipse",
    "meteor", "aurora", "astronaut", "rocket", "satellite", "comet",
    "asteroid", "milky way", "constellation", "mars", "jupiter",
    "saturn rings", "black hole", "supernova", "space station",
    "telescope", "solar system",

    # Nature phenomena
    "volcano", "lava", "lightning", "tornado", "hurricane", "tsunami",
    "earthquake", "avalanche", "wildfire", "geyser", "rainbow",
    "waterfall", "glacier", "iceberg", "sinkhole", "sandstorm",
    "hailstorm", "whirlpool", "tidal wave", "hot spring",
    "stalactite", "cave",

    # Plants & fungi
    "venus flytrap", "giant sequoia", "bamboo", "cactus", "bonsai",
    "mushroom", "kelp", "moss", "orchid", "sunflower", "cherry blossom",
    "baobab tree", "mangrove", "redwood", "lotus flower", "carnivorous plant",

    # Landmarks
    "eiffel tower", "great wall", "taj mahal", "pyramids", "colosseum",
    "machu picchu", "statue liberty", "big ben", "burj khalifa",
    "stonehenge", "grand canyon", "niagara falls", "great barrier reef",
    "amazon river", "mount everest", "sahara", "antarctica",
    "yellowstone", "angkor wat", "petra jordan", "christ redeemer",
    "golden gate bridge", "mount fuji", "victoria falls", "dead sea",
    "mariana trench",

    # Cities
    "new york", "tokyo", "dubai", "hong kong", "paris", "london",
    "singapore", "sydney", "los angeles", "shanghai", "rome",
    "istanbul", "bangkok", "rio de janeiro", "cairo", "moscow",
    "venice", "amsterdam", "barcelona",

    # Science & tech
    "robot", "circuit", "laboratory", "dna", "cells", "bacteria",
    "virus", "atom", "crystal", "laser", "hologram", "3d printer",
    "drone", "solar panel", "wind turbine", "microscope", "telescope",
    "electric car", "nuclear reactor", "particle accelerator",

    # Elements & materials
    "gold", "diamond", "crystal", "gemstone", "mineral", "ice", "fire",
    "water", "smoke", "sand", "glass", "metal", "obsidian", "quartz",
    "amber", "copper", "iron", "silver", "platinum", "titanium",

    # Food & agriculture
    "coffee beans", "chocolate", "rice paddy", "vineyard", "beehive",
    "honey harvest", "tea plantation", "wheat field", "olive grove",
    "spices", "saffron", "vanilla bean", "sugar cane",

    # Engineering & machines
    "suspension bridge", "dam", "skyscraper", "tunnel", "crane",
    "excavator", "train", "submarine", "helicopter", "aircraft carrier",
    "oil rig", "wind farm", "hydroelectric", "assembly line",

    # Weather
    "storm", "thunder", "rain", "snow", "fog", "clouds", "sunset",
    "sunrise", "northern lights", "blizzard", "typhoon", "monsoon",
    "dust devil", "frost",

    # Ocean & underwater
    "deep sea", "ocean floor", "coral reef", "underwater cave",
    "shipwreck", "hydrothermal vent", "kelp forest", "tide pool",
]


class PexelsClient:
    """Pexels API client for video search and download."""

    BASE_URL = "https://api.pexels.com/videos"

    def __init__(self, api_key: str, cache_dir: Path):
        self.api_key = api_key
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers["Authorization"] = api_key

    def search(
        self, query: str, orientation: str = "portrait", per_page: int = 80
    ) -> list[dict]:
        """Search for videos matching query. Fetches many results for variety."""
        page = random.randint(1, 5)
        response = self.session.get(
            f"{self.BASE_URL}/search",
            params={
                "query": query,
                "orientation": orientation,
                "per_page": per_page,
                "size": "medium",
                "page": page,
            },
        )
        response.raise_for_status()
        return response.json().get("videos", [])

    def extract_description_from_url(self, url: str) -> str:
        """Extract description from Pexels video URL.

        URL format: https://www.pexels.com/video/young-lion-resting-on-grassy-hill-29960562/
        Returns: "young lion resting on grassy hill"
        """
        match = re.search(r'/video/(.+)-(\d+)/?$', url)
        if match:
            slug = match.group(1)
            return slug.replace('-', ' ')

        match = re.search(r'/video/([^/]+)/?$', url)
        if match:
            slug = match.group(1)
            slug = re.sub(r'-?\d+$', '', slug)
            return slug.replace('-', ' ')

        return ""

    def download(self, video_data: dict, description: str) -> VideoClip:
        """Download a video and return clip metadata."""
        video_files = video_data.get("video_files", [])
        best_file = self._select_best_file(video_files)

        video_id = video_data["id"]
        cache_path = self.cache_dir / f"pexels_{video_id}.mp4"

        if not cache_path.exists():
            print(f"    Downloading video {video_id}...")
            response = requests.get(best_file["link"], stream=True)
            response.raise_for_status()
            with open(cache_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
        else:
            print(f"    Using cached video {video_id}")

        return VideoClip(
            path=cache_path,
            url=best_file["link"],
            duration=video_data["duration"],
            width=best_file["width"],
            height=best_file["height"],
            source="pexels",
            description=description,
            search_term=video_data.get("url", ""),
        )

    def _select_best_file(self, files: list[dict]) -> dict:
        """Select best quality video file, preferring portrait/vertical."""
        portrait_files = [f for f in files if f.get("height", 0) > f.get("width", 0)]
        candidates = portrait_files if portrait_files else files

        if not candidates:
            raise ValueError("No video files available")

        sorted_files = sorted(candidates, key=lambda f: abs(f.get("height", 0) - 1920))
        return sorted_files[0]


class VideoFetcher:
    """Fetches viral-worthy videos from stock footage APIs."""

    def __init__(self, pexels_key: str, cache_dir: Path, openai_api_key: str = None):
        self.cache_dir = cache_dir
        self.pexels = PexelsClient(pexels_key, cache_dir) if pexels_key else None
        self.openai_client = OpenAI(api_key=openai_api_key) if openai_api_key else None
        self._used_topics = set()  # Track used topics to avoid repeats

    def _ai_pick_best_video(self, candidates: list[tuple[dict, str]]) -> tuple[dict, str] | None:
        """Use GPT to pick the best video from a batch of candidates.

        Sends all descriptions at once and asks GPT to pick the single best one
        for a viral fact video. Returns None if none are good enough.
        """
        if not self.openai_client or not candidates:
            return None

        # Build a numbered list of descriptions
        desc_list = "\n".join(
            f"{i+1}. \"{desc}\"" for i, (_, desc) in enumerate(candidates)
        )

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You pick the best stock video for a viral YouTube Shorts fact video. Respond with JSON only."},
                    {"role": "user", "content": f"""I have these stock video descriptions (extracted from URLs). Pick the SINGLE BEST one for a viral fact video.

{desc_list}

A GOOD video for facts shows:
- A REAL, specific subject (real animal, real landmark, real phenomenon, real machine, etc.)
- Something you could tell a CRAZY or MIND-BLOWING fact about
- The actual thing, not a representation of it
- Something people find inherently fascinating (dangerous animals, extreme nature, weird science, etc.)

REJECT videos that show:
- Statues, fountains, sculptures, paintings, toys, logos, or any ARTIFICIAL version of a thing
- Generic scenery with no specific subject (just sky, grass, water, sunsets, sunrises, clouds, etc.)
- BORING subjects nobody cares about (generic bridges, random skylines, calm lakes, flower fields, etc.)
- People as the main focus (unless the person IS the interesting subject, like an astronaut)
- Vague stock footage (office, business, lifestyle, fashion)
- Abstract patterns, textures, or backgrounds
- Indoor/domestic settings (rooms, desks, kitchens)
- Generic city footage, traffic, or buildings (unless it's an iconic landmark)
- Tourism/travel footage with no specific interesting subject

If NONE of the options are good, set "pick" to 0.

Respond with JSON only:
{{"pick": 1, "reason": "short reason"}}"""},
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
            pick = int(data.get("pick", 0))
            reason = data.get("reason", "")

            if pick > 0 and pick <= len(candidates):
                print(f"    AI picked #{pick}: {reason}")
                return candidates[pick - 1]
            else:
                print(f"    AI rejected all candidates: {reason}")
                return None

        except Exception as e:
            print(f"    AI pick failed ({e}), using random")
            return random.choice(candidates) if candidates else None

    def _get_related_topic(self, original_topic: str) -> str:
        """Use GPT to suggest a random loosely related topic.

        Given "tiger", might return "lynx" or "camouflage" or "savanna".
        The goal is variety — jump to a different but related subject at the
        same level of vagueness, NOT a more specific version of the original.
        """
        if not self.openai_client:
            return original_topic

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You suggest video search terms. Respond with JSON only."},
                    {"role": "user", "content": f"""I'm searching for stock video footage about: "{original_topic}"

Instead of searching for that exact term, suggest a DIFFERENT but loosely related topic. It should be:
1. A DIFFERENT subject, NOT a more specific version of the original
2. At the SAME level of vagueness/specificity (1-2 words)
3. Related by category, theme, or loose association
4. Something that would have good stock video footage

Think of it as a random hop to a neighbor topic, NOT drilling deeper.

Examples:
- "tiger" -> "lynx" or "camouflage" or "jungle"
- "volcano" -> "geysers" or "tectonic plates" or "obsidian"
- "eagle" -> "falcon" or "talons" or "migration"
- "diamond" -> "sapphire" or "mining" or "pressure"
- "coral" -> "plankton" or "tide pool" or "sea anemone"
- "shark" -> "barracuda" or "deep sea" or "predator"
- "eiffel tower" -> "colosseum" or "arc de triomphe" or "wrought iron"

Respond with JSON only:
{{"search_term": "your suggested term"}}"""},
                    ],
                    temperature=1.0,
                    max_tokens=50,
                )

            content = response.choices[0].message.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            data = json.loads(content.strip())
            related = data["search_term"].strip().lower()
            if related and len(related) < 40:
                return related
        except Exception as e:
            print(f"    GPT related topic failed ({e}), using original")

        return original_topic

    def fetch_viral_video(self, min_duration: int = 5, topic: str = None) -> VideoClip:
        """Fetch a video on a viral topic.

        Collects candidates from Pexels search results, then uses GPT to pick
        the best one for a viral fact video.
        """
        if not self.pexels:
            raise ValueError("No video API configured. Set PEXELS_API_KEY.")

        # If topic specified, use it directly
        if topic:
            topics_to_try = [topic]
        else:
            # Get unused topics first, then fall back to all
            available = [t for t in VIRAL_TOPICS if t not in self._used_topics]
            if not available:
                self._used_topics.clear()
                available = VIRAL_TOPICS.copy()

            # Shuffle for variety
            random.shuffle(available)
            topics_to_try = available[:10]  # Try up to 10 random topics

        for search_term in topics_to_try:
            try:
                # 75% of the time, ask GPT for a related topic
                actual_search = search_term
                if self.openai_client and random.random() < 0.75:
                    actual_search = self._get_related_topic(search_term)
                    if actual_search != search_term:
                        print(f"  Searching for: {actual_search} (related to {search_term})")
                    else:
                        print(f"  Searching for: {search_term}")
                else:
                    print(f"  Searching for: {search_term}")
                results = self.pexels.search(actual_search)

                # Collect all candidates with descriptions (basic filters only)
                candidates = []
                for video in results:
                    # Check duration
                    if video.get("duration", 0) < min_duration:
                        continue

                    # Extract description from URL
                    url = video.get("url", "")
                    description = self.pexels.extract_description_from_url(url)

                    # Must have at least 3 words to be useful
                    if len(description.split()) < 3:
                        continue

                    candidates.append((video, description))

                if not candidates:
                    print(f"    No videos with descriptions found")
                    continue

                # Let GPT pick the best one from up to 15 random candidates
                random.shuffle(candidates)
                batch = candidates[:15]

                result = self._ai_pick_best_video(batch)
                if result:
                    video, description = result
                    self._used_topics.add(search_term)
                    return self.pexels.download(video, description)
                else:
                    print(f"    AI found no suitable videos in {len(batch)} candidates")

            except Exception as e:
                print(f"    Search failed: {e}")
                continue

        raise ValueError("Could not find suitable viral video")

    def fetch(self, keywords: list[str], min_duration: int = 5) -> VideoClip:
        """Legacy method - fetch video by keywords."""
        for keyword in keywords:
            try:
                print(f"  Searching for: {keyword}")
                results = self.pexels.search(keyword)
                candidates = []
                for video in results:
                    if video.get("duration", 0) >= min_duration:
                        url = video.get("url", "")
                        description = self.pexels.extract_description_from_url(url)
                        if len(description.split()) >= 3:
                            candidates.append((video, description))
                if candidates:
                    result = self._ai_pick_best_video(candidates[:15])
                    if result:
                        video, description = result
                        return self.pexels.download(video, description)
            except Exception as e:
                print(f"    Search failed for '{keyword}': {e}")
                continue

        raise ValueError(f"No suitable video found for keywords: {keywords}")
