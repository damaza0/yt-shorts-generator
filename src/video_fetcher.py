"""
Stock video fetching from Pexels API.
Downloads vertical/portrait videos for viral content.
Uses URL-based descriptions for accurate fact matching.
"""
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
# Generic scenery searches removed because they return boring videos
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

# Words that indicate vague/unclear descriptions - skip these videos
VAGUE_WORDS = [
    # People-related (we want nature/science, not people)
    "person", "people", "man", "woman", "women", "men", "boy", "girl", "child", "kid",
    "someone", "couple", "group", "team", "worker", "employee", "staff",
    "model", "athlete", "player", "dancer", "singer", "actor",
    "young", "old", "elderly", "adult", "teen", "teenager",
    "friend", "friends", "family", "tourist", "tourists", "visitor",
    "teacher", "student", "students", "class", "classroom", "school",
    "doctor", "nurse", "patient", "chef", "waiter", "customer",

    # Actions that indicate focus on humans
    "preparing", "cooking", "eating", "drinking", "holding", "using",
    "making", "doing", "working", "sitting", "standing", "walking",
    "running", "talking", "looking", "watching", "reading", "writing",
    "typing", "playing", "dancing", "singing", "shopping", "driving",

    # Body parts
    "hand", "hands", "finger", "fingers", "face", "head", "body",
    "arm", "leg", "foot", "feet", "eye", "eyes",

    # Generic/unclear descriptors
    "view of", "shot of", "footage of", "video of", "photo of",
    "close up of a", "image of", "picture of", "scene of",
    "beautiful", "amazing", "stunning", "gorgeous", "lovely",
    "nice", "good", "great", "best", "top",

    # Indoor/office settings (usually boring)
    "office", "desk", "computer", "laptop", "phone", "screen",
    "meeting", "conference", "presentation", "interview",
    "room", "house", "home", "apartment", "building interior",

    # Fashion/lifestyle (not viral fact content)
    "fashion", "clothes", "dress", "suit", "outfit", "style",
    "makeup", "beauty", "hair", "salon", "spa",

    # Stock footage clichés
    "business", "corporate", "professional", "success", "teamwork",
    "handshake", "celebration", "party", "wedding", "birthday",

    # Generic nature/scenery with no interesting fact potential
    "sunset", "sunrise", "serene", "tranquil", "peaceful", "calm",
    "scenic", "landscape", "waves", "clouds", "sky", "horizon",
    "leaves", "grass", "field", "meadow", "hillside",
    "raindrops", "droplets", "dew", "mist", "fog",
    "winter wonderland", "snowy landscape", "snow covered",
    "star on", "decoration", "decorative", "ornament",
    "abstract", "background", "texture", "pattern",
    "generic", "stock", "b-roll",
]

# Words that indicate the video has a SPECIFIC subject worth making a fact about
# Video must contain at least one of these to be selected
GOOD_SUBJECT_WORDS = [
    # Specific animals
    "lion", "tiger", "elephant", "wolf", "bear", "fox", "deer", "horse",
    "gorilla", "cheetah", "leopard", "giraffe", "zebra", "rhino", "hippo",
    "kangaroo", "koala", "panda", "monkey", "chimpanzee", "orangutan",
    "sloth", "otter", "seal", "walrus", "polar bear", "buffalo", "moose",
    "camel", "shark", "dolphin", "whale", "octopus", "jellyfish", "turtle",
    "manta", "stingray", "seahorse", "clownfish", "orca", "squid", "crab",
    "lobster", "starfish", "coral", "eagle", "owl", "parrot", "hummingbird",
    "peacock", "flamingo", "penguin", "hawk", "falcon", "toucan", "pelican",
    "swan", "crane", "heron", "kingfisher", "woodpecker", "crow", "raven",
    "snake", "crocodile", "alligator", "iguana", "chameleon", "gecko",
    "komodo", "tortoise", "frog", "salamander", "lizard", "spider",
    "tarantula", "scorpion", "bee", "butterfly", "dragonfly", "ant",
    "beetle", "ladybug", "moth", "firefly", "grasshopper", "caterpillar",
    "reindeer", "boar", "wild boar",
    # New animals
    "platypus", "pangolin", "capybara", "red panda", "armadillo",
    "porcupine", "hedgehog", "bat", "raccoon", "badger", "weasel",
    "wolverine", "hyena", "jackal", "bison", "yak", "meerkat", "lemur",
    "tapir", "manatee", "narwhal", "wombat", "pufferfish", "moray",
    "barracuda", "swordfish", "tuna", "hammerhead", "whale shark",
    "nautilus", "sea lion", "hermit crab", "sea urchin", "anglerfish",
    "parrotfish", "albatross", "ostrich", "condor", "vulture", "robin",
    "cardinal", "blue jay", "stork", "ibis", "kiwi", "cockatoo", "macaw",
    "python", "cobra", "rattlesnake", "sea snake", "tree frog",
    "poison dart", "axolotl", "newt", "monitor lizard", "praying mantis",
    "wasp", "hornet", "termite", "centipede", "millipede", "stick insect",
    "cicada",

    # Specific places/landmarks
    "eiffel", "pyramids", "colosseum", "taj mahal", "great wall",
    "stonehenge", "machu picchu", "statue of liberty", "big ben",
    "burj khalifa", "grand canyon", "niagara", "everest", "sahara",
    "amazon", "yellowstone", "barrier reef", "angkor wat", "petra",
    "christ redeemer", "golden gate", "mount fuji", "victoria falls",
    "dead sea", "mariana trench",

    # Specific phenomena
    "volcano", "lava", "eruption", "lightning", "tornado", "hurricane",
    "tsunami", "earthquake", "avalanche", "wildfire", "geyser", "aurora",
    "northern lights", "eclipse", "meteor", "sinkhole", "sandstorm",
    "hailstorm", "whirlpool", "hot spring", "stalactite", "cave",
    "blizzard", "typhoon", "monsoon",

    # Plants & fungi
    "venus flytrap", "sequoia", "bamboo", "cactus", "bonsai", "mushroom",
    "kelp", "orchid", "sunflower", "cherry blossom", "baobab",
    "mangrove", "redwood", "lotus", "carnivorous plant",

    # Specific things with fact potential
    "diamond", "gold", "crystal", "gemstone", "fossil", "obsidian",
    "quartz", "amber", "copper", "iron", "silver", "platinum", "titanium",
    "rocket", "satellite", "astronaut", "space station",
    "microscope", "bacteria", "virus", "cell", "dna",
    "robot", "drone", "laboratory", "telescope",
    "coffee", "chocolate", "honey", "saffron", "vanilla", "sugar cane",
    "submarine", "helicopter", "aircraft carrier", "oil rig",
    "dam", "skyscraper", "tunnel", "bridge",
    "coral reef", "shipwreck", "hydrothermal", "kelp forest",
    "black hole", "supernova", "mars", "jupiter", "saturn",

    # Cities (can have interesting facts)
    "new york", "tokyo", "dubai", "hong kong", "paris", "london",
    "singapore", "sydney", "shanghai", "rome", "istanbul", "bangkok",
    "rio de janeiro", "cairo", "moscow", "venice", "amsterdam", "barcelona",
]


class PexelsClient:
    """Pexels API client for video search and download."""

    BASE_URL = "https://api.pexels.com/videos"
    MIN_DESCRIPTION_WORDS = 4  # Minimum words for a good description

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
        # Extract the slug from URL (part between /video/ and the ID)
        match = re.search(r'/video/(.+)-(\d+)/?$', url)
        if match:
            slug = match.group(1)
            # Convert hyphens to spaces
            description = slug.replace('-', ' ')
            return description

        # Fallback: try to get anything after /video/
        match = re.search(r'/video/([^/]+)/?$', url)
        if match:
            slug = match.group(1)
            # Remove trailing numbers (video ID)
            slug = re.sub(r'-?\d+$', '', slug)
            return slug.replace('-', ' ')

        return ""

    def has_good_description(self, video_data: dict, search_term: str = "") -> tuple[bool, str]:
        """Check if video has a detailed enough description in its URL.

        A good description:
        - Has at least 4 words
        - Doesn't contain vague words like "person", "holding", etc.
        - MUST contain a specific subject that has interesting fact potential

        Returns: (is_good, description)
        """
        url = video_data.get("url", "")
        description = self.extract_description_from_url(url)
        word_count = len(description.split())

        # Must have minimum words
        if word_count < self.MIN_DESCRIPTION_WORDS:
            return False, description

        # Check for vague words that indicate unclear content
        description_lower = description.lower()
        for vague_word in VAGUE_WORDS:
            if vague_word in description_lower:
                return False, description

        # MUST have a specific subject with fact potential
        # This filters out generic scenery like "raindrops on leaves"
        has_good_subject = any(
            subject in description_lower for subject in GOOD_SUBJECT_WORDS
        )
        if not has_good_subject:
            return False, description

        return True, description

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

    def _get_related_topic(self, original_topic: str) -> str:
        """Use GPT to generate a related but different search topic.

        Given "tiger", might return "bengal tiger hunting" or "tiger cub".
        The goal is to find a related subject that will produce an interesting fact
        and good Pexels results.
        """
        if not self.openai_client:
            return original_topic

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You suggest video search terms. Respond with JSON only."},
                    {"role": "user", "content": f"""I'm searching for stock video footage about: "{original_topic}"

Instead of searching for that exact term, suggest a RELATED but more specific or interesting search term that:
1. Is visually related (would show similar footage on a stock video site)
2. Has potential for a surprising/interesting fact
3. Is 1-3 words (good for stock video search)

Examples:
- "shark" -> "hammerhead shark" or "great white" or "shark teeth"
- "volcano" -> "lava flow" or "volcanic eruption" or "magma"
- "eagle" -> "bald eagle" or "golden eagle" or "eagle hunting"
- "diamond" -> "raw diamond" or "diamond mine" or "gemstone"
- "coral" -> "coral reef" or "brain coral" or "coral bleaching"

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
        """Fetch a video on a viral topic with a good description.

        Only selects videos that have detailed descriptions in their URLs,
        ensuring facts can be accurately matched to video content.
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
                # 75% of the time, ask GPT for a related but more interesting topic
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

                # Filter for suitable videos WITH good descriptions
                suitable = []
                for video in results:
                    # Check duration
                    if video.get("duration", 0) < min_duration:
                        continue

                    # Check for good description in URL
                    has_good_desc, description = self.pexels.has_good_description(video, search_term)
                    if has_good_desc:
                        suitable.append((video, description))

                if suitable:
                    # Pick a random one from ALL suitable results
                    # Shuffle to ensure variety across multiple runs
                    random.shuffle(suitable)
                    video, description = suitable[0]
                    self._used_topics.add(search_term)
                    print(f"    Found: \"{description}\" (from {len(suitable)} options)")
                    return self.pexels.download(video, description)
                else:
                    print(f"    No videos with detailed descriptions found")

            except Exception as e:
                print(f"    Search failed: {e}")
                continue

        raise ValueError("Could not find suitable viral video with good description")

    def fetch(self, keywords: list[str], min_duration: int = 5) -> VideoClip:
        """Legacy method - fetch video by keywords."""
        for keyword in keywords:
            try:
                print(f"  Searching for: {keyword}")
                results = self.pexels.search(keyword)
                for video in results:
                    if video.get("duration", 0) >= min_duration:
                        has_good_desc, description = self.pexels.has_good_description(video)
                        if has_good_desc:
                            return self.pexels.download(video, description)
            except Exception as e:
                print(f"    Search failed for '{keyword}': {e}")
                continue

        raise ValueError(f"No suitable video found for keywords: {keywords}")
