"""
Viral fact generation using OpenAI GPT API.
Searches the web for real crazy facts and rewrites them for YouTube Shorts.
"""
import json
import random
from dataclasses import dataclass
from typing import List, Optional
from openai import OpenAI
from ddgs import DDGS


@dataclass
class GeneratedFact:
    """A generated viral fact with metadata."""

    hook: str  # Attention-grabbing first line (e.g., "DID YOU KNOW?")
    fact_text: str  # The main fact content
    highlight_words: list[str]  # Words to highlight in color
    category: str  # e.g., "science", "nature", "psychology"
    interest_score: int  # 1-10 how interesting/fascinating this fact is


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

    PICK_FACT_PROMPT = """You are a viral content creator for YouTube Shorts with millions of followers. I have a video showing: {video_description}

I searched the internet for facts about this subject. Here are the search results:

{search_results}

YOUR JOB:
1. Read ALL the search results above
2. Sort the facts into two buckets:
   - CRAZY facts: truly wild, disturbing, dark, myth-busting, or outrageous
   - INTERESTING facts: genuinely surprising, counterintuitive, specific, or "wow I need to tell someone"
3. If there are any truly CRAZY facts (stuff that makes people say "NO WAY"), randomly pick one of those
4. If not, randomly pick from the most INTERESTING ones instead
5. REWRITE the fact in your own words. This is for YouTube Shorts so it needs to HOOK people in the first second and make them want to share it
6. Rate how good this fact is for YouTube Shorts on a scale of 1-10

WHAT SCORES 8-10 (would go viral on YouTube Shorts):
- "Wait... WHAT?" reaction — genuinely shocks or surprises
- Specific numbers, dates, or comparisons that hit hard
- Myth-busting — proving something everyone believes is actually wrong
- Dark or unsettling truths that people don't talk about
- Counterintuitive — the complete opposite of what you'd expect
- Makes someone immediately want to comment or share

WHAT SCORES 7 (decent but NOT good enough):
- Mildly interesting but no real shock factor
- Descriptive facts about how something looks or where it is ("X is really big/beautiful")
- Travel guide facts ("X is a popular destination")
- Common knowledge dressed up as interesting

WHAT SCORES 1-6 (would flop on YouTube Shorts):
- Everyone already knows it
- Vague and unspecific ("X is really important")
- Sounds like a textbook or Wikipedia intro
- Only mildly surprising — no real "wow" factor
- Too long or complicated to absorb in 5 seconds
- "This place is beautiful/breathtaking" — that's not a fact, that's an opinion
- Generic tourism facts nobody would share

IMPORTANT - MATCH THE VIDEO LITERALLY:
The fact MUST match what is VISUALLY shown in the video. Examples:
- "a star on a stick" = a DECORATION, write about decorations/crafts, NOT astronomy
- "sculptures and statues inside a museum" = write about museums/sculptures, NOT the subject of the art
- "cars on a road" = write about cars/driving/roads, NOT the destination
- "reindeer grazing" = write about REINDEER specifically, not winter in general

WRITING STYLE - THIS IS CRITICAL:
- Write like you're telling a friend something insane, not like a Wikipedia article
- Short punchy sentences. No filler words.
- Lead with the most shocking part, not the setup
- Use "you" and "your" to make it personal when it fits
- NEVER start with "Did you know" — that's overdone and boring
- NEVER use phrases like "Imagine this" or "Picture this" — just state the fact
- Numbers hit harder than adjectives: "3,000 years old" > "very ancient"

HOOK GUIDELINES:
The hook should be SPECIFIC to the fact, not generic. It should tease the most shocking/interesting part.

GOOD HOOKS: "Dolphins are murderers:" / "Honey is bee vomit:" / "Your chocolate has bugs:" / "Bananas are radioactive:"
BAD HOOKS: "Actually terrifying:" / "You've been lied to:" / "This is insane:" / "Wait for it:"

You MUST respond with valid JSON only:
{{
    "hook": "A SHORT hook (2-6 words) that teases the SPECIFIC interesting part. End with a colon.",
    "fact_text": "The rewritten fact in 2-3 punchy sentences (30-45 words). No filler. No 'did you know'. No 'imagine this'.",
    "highlight_words": ["word1", "word2", "word3", "word4"],
    "category": "category_name",
    "interest_score": 8,
    "source_fact": "Brief note of which fact you picked and whether it was crazy or interesting"
}}

If NONE of the search results contain anything good (nothing scores above 6), set interest_score to the highest you found. Be honest - don't inflate scores for boring facts."""

    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)
        self.ddgs = DDGS()

    def _clean_text(self, text: str) -> str:
        """Remove AI-style formatting like em dashes, fancy quotes, etc."""
        text = text.replace("—", " - ")  # em dash
        text = text.replace("–", " - ")  # en dash
        text = text.replace("\u201c", '"').replace("\u201d", '"')
        text = text.replace("\u2018", "'").replace("\u2019", "'")
        while "  " in text:
            text = text.replace("  ", " ")
        return text.strip()

    def _extract_subject(self, video_description: str) -> str:
        """Extract the main subject from a video description for web searching."""
        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Extract the main subject from a video description. Respond with just the subject, nothing else."},
                {"role": "user", "content": f'Video description: "{video_description}"\n\nWhat is the main subject? Examples:\n- "young lion resting on grassy hill" -> "lions"\n- "close up of a tarantula on a rock" -> "tarantulas"\n- "eiffel tower at night with lights" -> "Eiffel Tower"\n- "coral reef with tropical fish swimming" -> "coral reefs"\n\nRespond with JUST the subject (1-3 words):'},
            ],
            temperature=0.0,
            max_tokens=20,
        )
        return response.choices[0].message.content.strip().strip('"')

    def _search_facts(self, subject: str) -> str:
        """Search the web for crazy, interesting, and surprising facts about a subject."""
        all_queries = [
            f"most insane crazy facts about {subject}",
            f"disturbing facts about {subject} you didn't know",
            f"shocking truth about {subject}",
            f"most interesting facts about {subject}",
            f"surprising things about {subject}",
        ]
        # Pick 3 random queries each time for variety
        search_queries = random.sample(all_queries, min(3, len(all_queries)))

        all_results = []
        for query in search_queries:
            try:
                results = self.ddgs.text(query, max_results=5)
                for r in results:
                    title = r.get("title", "")
                    body = r.get("body", "")
                    if title or body:
                        all_results.append(f"- {title}: {body}")
            except Exception as e:
                print(f"    Search failed for '{query}': {e}")
                continue

        if not all_results:
            return ""

        # Deduplicate and limit
        seen = set()
        unique = []
        for r in all_results:
            if r not in seen:
                seen.add(r)
                unique.append(r)

        return "\n".join(unique[:15])

    def generate_for_video(self, video_description: str) -> GeneratedFact:
        """Search for interesting facts about the video subject, pick one, and rewrite it."""
        # Step 1: Extract the main subject from the video description
        subject = self._extract_subject(video_description)
        print(f"    Subject extracted: {subject}")

        # Step 2: Search the web for interesting facts about this subject
        print(f"    Searching web for interesting facts about '{subject}'...")
        search_results = self._search_facts(subject)

        if not search_results:
            print("    No search results found, falling back to GPT knowledge")
            search_results = "(No search results found. Use your own knowledge to find the most INTERESTING fact about this subject.)"

        # Step 3: GPT picks an interesting fact and rewrites it
        prompt = self.PICK_FACT_PROMPT.format(
            video_description=video_description,
            search_results=search_results,
        )

        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You pick the most interesting facts from search results and rewrite them for viral YouTube Shorts. Always respond with valid JSON only. NEVER use em dashes or en dashes. Use commas or periods instead."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.9,
            max_tokens=400,
        )

        content = response.choices[0].message.content

        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        data = json.loads(content.strip())

        interest_score = int(data.get("interest_score", 5))
        source_fact = data.get("source_fact", "")
        if source_fact:
            print(f"    Source: {source_fact[:80]}")
        print(f"    Interest score: {interest_score}/10")

        return GeneratedFact(
            hook=self._clean_text(data["hook"]),
            fact_text=self._clean_text(data["fact_text"]),
            highlight_words=[w for w in data["highlight_words"] if len(w) > 2],
            category=data["category"],
            interest_score=interest_score,
        )

    def score_fact_independently(self, fact: GeneratedFact) -> int:
        """Score a fact with a separate, independent GPT call.

        This is a cold judge — it receives ONLY the hook and fact text,
        with no context about the topic, search results, or video.
        It has no ego investment in the fact because it didn't write it.

        Returns an integer score 1-10.
        """
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a brutally honest content judge for YouTube Shorts. "
                            "You score facts on a 1-10 scale. You are HARSH. Most facts are 5-7. "
                            "Only truly shocking, specific, counterintuitive facts score 8+. "
                            "You have no bias — you didn't write this fact and you don't care about being nice."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Rate this YouTube Short fact 1-10. Would it make someone stop scrolling and share it?\n\n"
                            f"Hook: \"{fact.hook}\"\n"
                            f"Fact: \"{fact.fact_text}\"\n\n"
                            "SCORING RULES:\n"
                            "9-10: Genuinely jaw-dropping. I'd screenshot this and send it to 5 friends right now.\n"
                            "8: Really surprising. Makes you go 'wait, seriously?' and want to verify it.\n"
                            "7: Decent trivia. Mildly interesting but wouldn't make anyone share it.\n"
                            "5-6: Boring. Sounds like a Wikipedia summary or travel brochure.\n"
                            "1-4: Terrible. Common knowledge, vague, or just an opinion disguised as a fact.\n\n"
                            "Be honest. Most facts are NOT 8+. If it doesn't genuinely shock you, don't score it high.\n\n"
                            "Respond with JSON only:\n"
                            "{\"score\": 7, \"reason\": \"brief reason\"}"
                        ),
                    },
                ],
                temperature=0.3,  # Low temp for consistent, honest scoring
                max_tokens=100,
            )

            content = response.choices[0].message.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            data = json.loads(content.strip())
            score = int(data.get("score", 5))
            reason = data.get("reason", "")
            print(f"    Independent score: {score}/10 — {reason[:80]}")
            return score

        except Exception as e:
            print(f"    Independent scoring failed ({e}), using original score")
            return fact.interest_score

    METADATA_PROMPT = """Based on this viral fact, generate YouTube Shorts metadata.

Fact Hook: {hook}
Fact Text: {fact_text}
Category: {category}

RULES:
1. Title: MUST be under 70 characters. NO emojis. Be curiosity-driving and specific.
2. Tags: 8-12 relevant keywords for discovery (no hashtags, just words)

TITLE TIPS (make it clickable):
- Use numbers when possible ("99% of people don't know...")
- Create curiosity gap ("The truth about...")
- Use power words (shocking, insane, never, always)
- Match the hook's energy
- NO EMOJIS in the title

Respond with JSON only:
{{
    "title": "Catchy title WITHOUT emojis (under 70 chars)",
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

        # Strip any emojis from title
        import re
        title = data["title"][:100]
        title = re.sub(r'[^\w\s\-\'\",.:;!?&%()/]', '', title).strip()

        # Description is just 3 hashtags
        tags = data.get("tags", [])[:3]
        hashtags = " ".join(f"#{tag.replace(' ', '')}" for tag in tags)
        description = f"#Shorts {hashtags}"

        return YouTubeMetadata(
            title=self._clean_text(title),
            description=description,
            tags=data.get("tags", [])[:30],
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
            interest_score=10,  # Standalone generation assumed interesting
        )
