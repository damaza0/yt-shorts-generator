"""
Viral fact generation using OpenAI GPT API.
Generates shocking/interesting facts based on available video content.
"""
import json
from dataclasses import dataclass
from typing import List, Optional
from openai import OpenAI


@dataclass
class GeneratedFact:
    """A generated viral fact with metadata."""

    hook: str  # Attention-grabbing first line (e.g., "DID YOU KNOW?")
    fact_text: str  # The main fact content
    highlight_words: list[str]  # Words to highlight in color
    category: str  # e.g., "science", "nature", "psychology"


@dataclass
class YouTubeMetadata:
    """Metadata for YouTube upload."""

    title: str  # Video title (max 100 chars)
    description: str  # Full description with hashtags
    tags: List[str]  # Discovery tags


class FactGenerator:
    """Generates viral facts using OpenAI GPT."""

    SYSTEM_PROMPT = """You are a viral content creator for YouTube Shorts. You create SHOCKING, INTERESTING, and MIND-BLOWING facts that make people stop scrolling.

Your facts should be:
1. SHOCKING or SURPRISING - things that make people say "wait, WHAT?!"
2. VERY SHORT - must be readable in 5-8 seconds (max 25-30 words)
3. SHAREABLE - facts people want to tell their friends
4. Can be about ANYTHING: science, psychology, nature, space, human body, animals, technology, history, food, money, relationships, sports, celebrities, crime, mysteries, etc.

You MUST respond with valid JSON in this exact format:
{
    "hook": "A 2-4 word attention grabber like 'WAIT WHAT?!' or 'THIS IS INSANE:' or 'NOBODY KNOWS THIS:' or 'SHOCKING FACT:'",
    "fact_text": "The actual fact in 1-2 SHORT sentences. Make it punchy and memorable.",
    "highlight_words": ["word1", "word2", "word3"],
    "category": "category_name"
}

For highlight_words: Pick 2-4 words that are most shocking/impactful (numbers, percentages, surprising words).
For category: science, nature, psychology, space, animals, technology, history, human body, food, money, crime, mystery, sports, or other.

Examples of VIRAL facts:
- "90% of the ocean is still unexplored. We know more about Mars than our own planet."
- "Honey never spoils. 3000-year-old honey from Egyptian tombs is still edible."
- "You're more likely to die from a vending machine than a shark attack."
- "Bananas are radioactive. Eating 10 million at once could kill you."
- "Your brain uses 20% of your body's energy but is only 2% of your weight." """

    MATCH_VIDEO_PROMPT = """You are a viral content creator for YouTube Shorts. I have a video showing: {video_description}

Generate a MIND-BLOWING fact that relates to this video. The fact should make viewers STOP SCROLLING and think "wait, WHAT?!"

IMPORTANT - MATCH THE VIDEO LITERALLY:
The fact MUST match what is VISUALLY shown in the video. Examples:
- "a star on a stick" = a DECORATION, write about decorations/crafts, NOT astronomy
- "sculptures and statues inside a museum" = write about museums/sculptures, NOT the subject of the art
- "cars on a road" = write about cars/driving/roads, NOT the destination
- "reindeer grazing" = write about REINDEER specifically, not winter in general
Think about what the VIEWER SEES, not abstract connections.

PRIORITY: CONTROVERSIAL FACTS WHEN POSSIBLE
Try to find a controversial, debate-sparking, or myth-busting fact first. These get the most engagement:
- Things people commonly believe that are WRONG
- Dark truths companies/industries hide
- Facts that challenge common knowledge
- Uncomfortable truths people don't want to hear

If no good controversial fact exists for the topic, a genuinely interesting/shocking fact is fine. Don't force controversy if it doesn't fit.

FACT TYPES (in order of preference):
1. MYTH-BUSTING - things people commonly believe that are wrong
2. HIDDEN TRUTH - things companies or industries don't want you to know
3. DARK/CREEPY - unsettling facts about death, danger, or the unknown
4. SHOCKING - genuinely surprising facts that make people go "no way"
5. GROSS - disgusting facts about food, bodies, animals
6. WEIRD SCIENCE - bizarre true facts about nature, the human body

CRITICAL RULES:
1. The fact MUST be 100% TRUE and VERIFIABLE
2. The fact MUST match what is VISUALLY shown in the video (see examples above)
3. NO boring textbook facts - if it's not interesting, find a better one
4. The hook should match the tone - don't use dramatic hooks for mild facts
5. NEVER say "tag a friend" or ask questions like "did you know this?"
6. Let the fact speak for itself
7. Length: 2-3 punchy sentences (30-45 words)

HOOK GUIDELINES:
The hook should be SPECIFIC to the fact, not generic. It should tease the most interesting part.

GOOD HOOKS (specific, tease the fact):
- "Dolphins are murderers:" (specific to dolphin fact)
- "Honey is bee vomit:" (specific, attention-grabbing)
- "Your chocolate has bugs:" (specific to FDA insect fact)
- "Octopuses have 3 hearts:" (specific, intriguing)
- "Breakfast is a scam:" (specific to cereal company fact)
- "Deer kill more than sharks:" (specific, surprising comparison)

BAD HOOKS (generic, boring):
- "Actually terrifying:" (too generic)
- "You've been lied to:" (overused, generic)
- "Most people don't know:" (generic filler)
- "This is insane:" (generic)
- "EXPOSED:" (clickbait, generic)

The hook should make someone curious about THIS SPECIFIC fact, not just signal "here comes a fact."

GOOD FULL EXAMPLES:
- Hook: "Breakfast is a marketing scam:" Fact: "The idea that breakfast is 'the most important meal' was invented by cereal companies in the 1900s. They paid doctors to promote it."
- Hook: "Dolphins kill for fun:" Fact: "They've been documented torturing baby sharks and tossing their corpses around for hours. Not so cute anymore."
- Hook: "Your chocolate has insects:" Fact: "The FDA allows up to 60 insect fragments per 100 grams of chocolate. You've eaten thousands of bug parts and didn't know it."
- Hook: "Honey is just bee vomit:" Fact: "Bees regurgitate nectar repeatedly to make it. It never spoils because it's too acidic for bacteria. 3000-year-old Egyptian honey is still edible."
- Hook: "Octopuses have 3 hearts:" Fact: "And blue blood. When they swim, one heart stops beating entirely. That's why they prefer crawling instead."

BAD EXAMPLES:
- Video shows "a star decoration" but fact is about outer space stars (WRONG - doesn't match visuals)
- "Mountains are tall and snowy" (boring, who cares?)
- Generic hooks like "This is CRAZY:" for any fact (lazy)
- "Tag someone who needs to see this!" (annoying)

You MUST respond with valid JSON only:
{{
    "hook": "A SHORT hook (2-6 words) that teases the SPECIFIC interesting part of THIS fact. End with a colon.",
    "fact_text": "The actual interesting fact in 2-3 sentences (30-45 words). No questions, no 'tag a friend', just the fact.",
    "highlight_words": ["word1", "word2", "word3", "word4"],
    "category": "category_name"
}}"""

    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)

    def _clean_text(self, text: str) -> str:
        """Remove AI-style formatting like em dashes, fancy quotes, etc."""
        # Replace em dashes and en dashes with regular dashes or commas
        text = text.replace("—", " - ")  # em dash
        text = text.replace("–", " - ")  # en dash
        # Replace fancy quotes with regular quotes
        text = text.replace(""", '"').replace(""", '"')
        text = text.replace("'", "'").replace("'", "'")
        # Remove double spaces that might result
        while "  " in text:
            text = text.replace("  ", " ")
        return text.strip()

    def generate_for_video(self, video_description: str) -> GeneratedFact:
        """Generate a viral fact that matches a specific video."""
        prompt = self.MATCH_VIDEO_PROMPT.format(video_description=video_description)

        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You create viral YouTube Shorts facts. Always respond with valid JSON only. NEVER use em dashes (—) or en dashes (–). Use commas or periods instead."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.9,
            max_tokens=300,
        )

        content = response.choices[0].message.content

        # Handle potential markdown code blocks
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        data = json.loads(content.strip())

        # Clean up AI formatting from text
        return GeneratedFact(
            hook=self._clean_text(data["hook"]),
            fact_text=self._clean_text(data["fact_text"]),
            highlight_words=[w for w in data["highlight_words"] if len(w) > 2],
            category=data["category"],
        )

    METADATA_PROMPT = """Based on this viral fact, generate YouTube Shorts metadata that will maximize views and engagement.

Fact Hook: {hook}
Fact Text: {fact_text}
Category: {category}

RULES:
1. Title: MUST be under 70 characters, include 1 emoji, be curiosity-driving
2. Description: Include the fact and relevant hashtags (#Shorts is REQUIRED). Keep it short and punchy.
3. Tags: 8-12 relevant keywords for discovery (no hashtags, just words)

TITLE TIPS (make it clickable):
- Use numbers when possible ("99% of people don't know...")
- Create curiosity gap ("The truth about...")
- Use power words (shocking, insane, never, always)
- Match the hook's energy

Respond with JSON only:
{{
    "title": "Catchy title with emoji (under 70 chars)",
    "description": "Short description with hashtags",
    "tags": ["tag1", "tag2", "tag3", ...]
}}"""

    def generate_metadata(
        self,
        fact: GeneratedFact,
        channel_name: str = "Daily Incredible Facts",
    ) -> YouTubeMetadata:
        """
        Generate YouTube metadata for a fact.

        Args:
            fact: The generated fact to create metadata for
            channel_name: YouTube channel name for branding

        Returns:
            YouTubeMetadata with title, description, and tags
        """
        prompt = self.METADATA_PROMPT.format(
            hook=fact.hook,
            fact_text=fact.fact_text,
            category=fact.category,
        )

        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "You create viral YouTube metadata. Respond with JSON only. No markdown.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=500,
        )

        content = response.choices[0].message.content

        # Handle markdown code blocks
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        data = json.loads(content.strip())

        # Ensure required elements
        title = data["title"][:100]  # YouTube limit
        description = data["description"]

        # Ensure #Shorts is in description
        if "#Shorts" not in description:
            description = description.rstrip() + "\n\n#Shorts"

        # Add subscribe CTA
        if "Subscribe" not in description:
            description += "\n\nSubscribe for more interesting facts!"

        return YouTubeMetadata(
            title=self._clean_text(title),
            description=description[:5000],  # YouTube limit
            tags=data.get("tags", [])[:30],  # YouTube limit ~500 chars total
        )

    def generate(self, topic: str = None) -> GeneratedFact:
        """Generate a random viral fact, optionally about a topic."""
        user_prompt = "Generate a SHOCKING viral fact"
        if topic:
            user_prompt += f" about {topic}"
        user_prompt += ". Make it something that will blow people's minds and make them share it."

        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT + "\n\nNEVER use em dashes (—) or en dashes (–). Use commas or periods instead."},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.95,  # High creativity for variety
            max_tokens=300,
        )

        content = response.choices[0].message.content

        # Handle potential markdown code blocks
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        data = json.loads(content.strip())

        # Clean up AI formatting from text
        return GeneratedFact(
            hook=self._clean_text(data["hook"]),
            fact_text=self._clean_text(data["fact_text"]),
            highlight_words=[w for w in data["highlight_words"] if len(w) > 2],
            category=data["category"],
        )
