#!/usr/bin/env python3
"""
YouTube Shorts Historical Facts Generator

CLI interface for generating viral YouTube Shorts with historical facts.
"""
import sys
from pathlib import Path
from datetime import datetime

import click

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import settings
from src.fact_generator import FactGenerator
from src.video_fetcher import VideoFetcher
from src.text_renderer import TextRenderer
from src.music_manager import MusicManager
from src.video_composer import VideoComposer
from src.vision_reviewer import VisionReviewer


@click.group()
def cli():
    """YouTube Shorts Historical Facts Generator.

    Generate viral YouTube Shorts featuring fascinating historical facts
    with stock footage and trending music.
    """
    pass


@cli.command()
def check():
    """Check configuration and dependencies."""
    click.echo("Checking configuration...\n")

    # Check API keys
    checks = [
        ("OpenAI API Key", bool(settings.openai_api_key), "Required"),
        ("Pexels API Key", bool(settings.pexels_api_key), "Required for video"),
        ("Pixabay API Key", bool(settings.pixabay_api_key), "Optional"),
    ]

    all_ok = True
    for name, ok, note in checks:
        if ok:
            status = click.style("OK", fg="green")
        else:
            status = click.style("MISSING", fg="red")
            if "Required" in note:
                all_ok = False
        click.echo(f"  {name}: {status} ({note})")

    # Check directories
    click.echo("\nChecking directories...")
    for name, dir_path in [
        ("Video cache", settings.video_cache_dir),
        ("Music cache", settings.music_cache_dir),
        ("Output", settings.output_dir),
    ]:
        dir_path.mkdir(parents=True, exist_ok=True)
        click.echo(f"  {name}: {click.style('OK', fg='green')} ({dir_path})")

    # Check FFmpeg
    click.echo("\nChecking FFmpeg...")
    import subprocess

    try:
        result = subprocess.run(
            ["ffmpeg", "-version"], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            version = result.stdout.split("\n")[0]
            click.echo(f"  FFmpeg: {click.style('OK', fg='green')} ({version[:50]})")
        else:
            click.echo(f"  FFmpeg: {click.style('ERROR', fg='red')}")
            all_ok = False
    except Exception:
        click.echo(f"  FFmpeg: {click.style('NOT FOUND', fg='red')} (required for video encoding)")
        all_ok = False

    click.echo()
    if all_ok:
        click.echo(click.style("All checks passed! Ready to generate videos.", fg="green"))
    else:
        click.echo(click.style("Some checks failed. Please fix the issues above.", fg="red"))
        click.echo("\nTo get started:")
        click.echo("  1. Copy .env.example to .env")
        click.echo("  2. Add your OPENAI_API_KEY to .env")
        click.echo("  3. Get a free Pexels API key at https://www.pexels.com/api/")
        click.echo("  4. Add PEXELS_API_KEY to .env")


@cli.command()
@click.option("--topic", "-t", default=None, help="Video topic (e.g., 'ocean', 'space', 'animals')")
@click.option("--duration", "-d", default=8, help="Video duration in seconds (default: 8)")
@click.option("--no-music", is_flag=True, default=False, help="Generate without background music")
@click.option("--output", "-o", default=None, help="Output filename")
def generate(topic, duration, no_music, output):
    """Generate a new YouTube Short with a viral fact."""

    # Validate configuration
    errors = settings.validate()
    if errors:
        for error in errors:
            click.echo(click.style(f"Error: {error}", fg="red"))
        click.echo("\nRun 'python main.py check' for setup instructions.")
        return

    click.echo(click.style("\n=== YouTube Shorts Generator ===\n", fg="cyan", bold=True))

    MIN_INTEREST_SCORE = 8
    MAX_TOPIC_ATTEMPTS = 10

    fetcher = VideoFetcher(settings.pexels_api_key, settings.video_cache_dir, settings.openai_api_key)
    reviewer = VisionReviewer(settings.openai_api_key)
    fact_gen = FactGenerator(settings.openai_api_key)

    output_path = None

    for topic_attempt in range(MAX_TOPIC_ATTEMPTS):
        if topic_attempt > 0:
            click.echo(click.style(f"\n--- Restarting with new topic (attempt {topic_attempt + 1}/{MAX_TOPIC_ATTEMPTS}) ---\n", fg="yellow"))

        # Step 1: Find a viral video and verify with GPT Vision
        click.echo("1. Finding viral video content...")
        video_clip = None
        vision_result = None
        for attempt in range(5):
            candidate = fetcher.fetch_viral_video(min_duration=duration, topic=topic)
            click.echo(f"   Candidate: {click.style(candidate.description, fg='cyan')} ({candidate.duration}s)")

            click.echo("   Verifying with GPT Vision...")
            result = reviewer.verify_video_content(candidate.path, candidate.description)

            if result.approved:
                video_clip = candidate
                vision_result = result
                click.echo(f"   {click.style('APPROVED', fg='green')} - {result.explanation[:60]}")
                break
            else:
                click.echo(f"   {click.style('REJECTED', fg='red')} - {result.explanation[:60]}")
                click.echo(f"   Trying another video... (attempt {attempt + 1}/5)")

        if not video_clip:
            click.echo(click.style("Could not find a verified video, trying new topic...", fg="red"))
            continue

        # Calculate best start time from vision analysis
        start_time = reviewer.get_best_start_time(vision_result)
        click.echo(f"   Best start time: {start_time:.1f}s")

        # Step 2: Search web for interesting facts and pick one
        click.echo("\n2. Searching for interesting facts...")
        fact = fact_gen.generate_for_video(video_clip.description)

        click.echo(f"   Hook: {click.style(fact.hook, fg='yellow')}")
        click.echo(f"   Fact: {fact.fact_text}")
        click.echo(f"   Highlights: {', '.join(fact.highlight_words)}")
        click.echo(f"   Category: {fact.category}")
        click.echo(f"   Writer's score: {fact.interest_score}/10")

        # Independent scoring — a separate GPT call judges the fact cold
        click.echo("   Running independent quality check...")
        independent_score = fact_gen.score_fact_independently(fact)
        fact.interest_score = independent_score
        click.echo(f"   Final score: {click.style(str(independent_score) + '/10', fg='yellow' if independent_score >= MIN_INTEREST_SCORE else 'red')}")

        if independent_score < MIN_INTEREST_SCORE:
            click.echo(click.style(f"   Not interesting enough (score {independent_score}/10, need {MIN_INTEREST_SCORE}+). Trying new topic...", fg="red"))
            continue

        click.echo(click.style(f"   Passed quality gate! (score {independent_score}/10)", fg="green"))

        # Step 3: Get music
        music_track = None
        if not no_music:
            click.echo("\n3. Picking background music...")
            clips_dir = Path(__file__).parent / "clips"
            music_mgr = MusicManager(clips_dir, settings.openai_api_key)
            music_track = music_mgr.pick_track(fact.hook, fact.fact_text, fact.category)
            click.echo(f"   Track: {click.style(music_track.title, fg='magenta')}")
        else:
            click.echo("\n3. Skipping music (--no-music flag)")

        # Step 4: Render text with branding
        click.echo("\n4. Rendering text overlay with branding...")
        renderer = TextRenderer(
            height=990,
            font_size_hook=settings.font_size_hook,
            font_size_fact=settings.font_size_fact,
            text_color=settings.text_color,
            bg_color=settings.bg_color,
            logo_path=settings.logo_path,
            channel_name=settings.channel_name,
            channel_handle=settings.channel_handle,
        )
        click.echo(f"   Channel: {settings.channel_name}")
        click.echo(f"   Highlight color: RGB{renderer.highlight_color}")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        text_image_path = settings.output_dir / f"_temp_text_{timestamp}.png"
        renderer.render(fact.hook, fact.fact_text, fact.highlight_words, text_image_path)
        click.echo("   Text image created")

        # Step 5: Compose video
        click.echo("\n5. Composing final video...")
        composer = VideoComposer(
            width=settings.video_width,
            height=settings.video_height,
            duration=duration,
        )

        if output:
            output_path = Path(output)
        else:
            safe_category = fact.category.replace("/", "_").replace(" ", "_").replace(":", "")
            output_path = settings.output_dir / f"short_{safe_category}_{timestamp}.mp4"

        music_path = music_track.path if music_track else None
        composer.compose(
            text_image_path, video_clip.path, output_path, music_path,
            start_time=start_time,
        )

        # Cleanup temp text image
        if text_image_path.exists():
            text_image_path.unlink()

        # Step 6: Final GPT Vision check — is the subject visible in the finished video?
        click.echo("\n6. Final verification — checking subject visibility...")
        subject_visible = reviewer.verify_final_video(output_path, fact.hook, fact.fact_text)

        if subject_visible:
            click.echo(click.style("   Subject is visible! Video is good.", fg="green"))
            break
        else:
            click.echo(click.style("   Subject NOT visible in final video. Rejecting and restarting...", fg="red"))
            # Delete the bad video
            if output_path.exists():
                output_path.unlink()
            output_path = None

    if not output_path or not output_path.exists():
        click.echo(click.style(f"Could not produce a good video after {MAX_TOPIC_ATTEMPTS} attempts.", fg="red"))
        return

    # Final output
    click.echo(click.style("\n=== Video Generated Successfully! ===\n", fg="green", bold=True))
    click.echo(f"Output: {click.style(str(output_path), fg='cyan')}")
    click.echo(f"Duration: {duration} seconds")
    click.echo(f"Resolution: {settings.video_width}x{settings.video_height}")


@cli.command()
@click.option("--count", "-n", default=5, help="Number of videos to generate")
@click.option("--topic", "-t", default=None, help="Video topic filter")
@click.option("--duration", "-d", default=8, help="Video duration in seconds")
@click.pass_context
def batch(ctx, count, topic, duration):
    """Generate multiple YouTube Shorts in batch."""
    click.echo(click.style(f"\n=== Batch Generation: {count} videos ===\n", fg="cyan", bold=True))

    for i in range(count):
        click.echo(f"\n{'='*50}")
        click.echo(f"Video {i+1}/{count}")
        click.echo(f"{'='*50}")
        ctx.invoke(generate, topic=topic, duration=duration)

    click.echo(click.style(f"\n=== Batch complete! Generated {count} videos ===", fg="green", bold=True))


@cli.command()
@click.option("--topic", "-t", default=None, help="Video topic (e.g., 'ocean', 'space', 'animals')")
@click.option("--duration", "-d", default=8, help="Video duration in seconds (default: 8)")
@click.option("--privacy", "-p", default="public", type=click.Choice(["public", "private", "unlisted"]),
              help="YouTube video privacy (default: public)")
@click.option("--upload", is_flag=True, default=False, help="Upload to YouTube after generating video")
def auto(topic, duration, privacy, upload):
    """Generate a YouTube Short automatically.

    This command generates a video locally. Pass --upload to also upload it to YouTube.

    Required environment variables for upload:
    - YOUTUBE_CLIENT_ID
    - YOUTUBE_CLIENT_SECRET
    - YOUTUBE_REFRESH_TOKEN

    Run 'python scripts/setup_youtube_oauth.py' to generate these credentials.
    """
    import os

    # Validate configuration
    errors = settings.validate()
    if errors:
        for error in errors:
            click.echo(click.style(f"Error: {error}", fg="red"))
        click.echo("\nRun 'python main.py check' for setup instructions.")
        sys.exit(1)

    # Check YouTube credentials if upload is enabled
    if not no_upload:
        required_vars = ["YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN"]
        missing = [v for v in required_vars if not os.getenv(v)]
        if missing:
            click.echo(click.style("Error: Missing YouTube credentials:", fg="red"))
            for v in missing:
                click.echo(f"  - {v}")
            click.echo("\nRun 'python scripts/setup_youtube_oauth.py' to generate credentials.")
            click.echo("Then add them to your environment or GitHub Secrets.")
            sys.exit(1)

    click.echo(click.style("\n=== YouTube Shorts Auto Generator ===\n", fg="cyan", bold=True))

    MIN_INTEREST_SCORE = 8
    MAX_TOPIC_ATTEMPTS = 10

    fetcher = VideoFetcher(settings.pexels_api_key, settings.video_cache_dir, settings.openai_api_key)
    reviewer = VisionReviewer(settings.openai_api_key)
    fact_gen = FactGenerator(settings.openai_api_key)

    output_path = None
    fact = None

    for topic_attempt in range(MAX_TOPIC_ATTEMPTS):
        if topic_attempt > 0:
            click.echo(click.style(f"\n--- Restarting with new topic (attempt {topic_attempt + 1}/{MAX_TOPIC_ATTEMPTS}) ---\n", fg="yellow"))

        # Step 1: Find a viral video and verify with GPT Vision
        click.echo("1. Finding viral video content...")
        video_clip = None
        vision_result = None
        for attempt in range(5):
            candidate = fetcher.fetch_viral_video(min_duration=duration, topic=topic)
            click.echo(f"   Candidate: {click.style(candidate.description, fg='cyan')} ({candidate.duration}s)")

            click.echo("   Verifying with GPT Vision...")
            result = reviewer.verify_video_content(candidate.path, candidate.description)

            if result.approved:
                video_clip = candidate
                vision_result = result
                click.echo(f"   {click.style('APPROVED', fg='green')} - {result.explanation[:60]}")
                break
            else:
                click.echo(f"   {click.style('REJECTED', fg='red')} - {result.explanation[:60]}")
                click.echo(f"   Trying another video... (attempt {attempt + 1}/5)")

        if not video_clip:
            click.echo(click.style("Could not find a verified video, trying new topic...", fg="red"))
            continue

        # Calculate best start time from vision analysis
        start_time = reviewer.get_best_start_time(vision_result)
        click.echo(f"   Best start time: {start_time:.1f}s")

        # Step 2: Search web for interesting facts and pick one
        click.echo("\n2. Searching for interesting facts...")
        fact = fact_gen.generate_for_video(video_clip.description)

        click.echo(f"   Hook: {click.style(fact.hook, fg='yellow')}")
        click.echo(f"   Fact: {fact.fact_text}")
        click.echo(f"   Category: {fact.category}")
        click.echo(f"   Writer's score: {fact.interest_score}/10")

        # Independent scoring — a separate GPT call judges the fact cold
        click.echo("   Running independent quality check...")
        independent_score = fact_gen.score_fact_independently(fact)
        fact.interest_score = independent_score
        click.echo(f"   Final score: {click.style(str(independent_score) + '/10', fg='yellow' if independent_score >= MIN_INTEREST_SCORE else 'red')}")

        if independent_score < MIN_INTEREST_SCORE:
            click.echo(click.style(f"   Not interesting enough (score {independent_score}/10, need {MIN_INTEREST_SCORE}+). Trying new topic...", fg="red"))
            continue

        click.echo(click.style(f"   Passed quality gate! (score {independent_score}/10)", fg="green"))

        # Step 3: Get music
        click.echo("\n3. Picking background music...")
        clips_dir = Path(__file__).parent / "clips"
        music_mgr = MusicManager(clips_dir, settings.openai_api_key)
        music_track = music_mgr.pick_track(fact.hook, fact.fact_text, fact.category)
        click.echo(f"   Track: {click.style(music_track.title, fg='magenta')}")

        # Step 4: Render text
        click.echo("\n4. Rendering text overlay...")
        renderer = TextRenderer(
            height=990,
            font_size_hook=settings.font_size_hook,
            font_size_fact=settings.font_size_fact,
            text_color=settings.text_color,
            bg_color=settings.bg_color,
            logo_path=settings.logo_path,
            channel_name=settings.channel_name,
            channel_handle=settings.channel_handle,
        )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        text_image_path = settings.output_dir / f"_temp_text_{timestamp}.png"
        renderer.render(fact.hook, fact.fact_text, fact.highlight_words, text_image_path)
        click.echo("   Text image created")

        # Step 5: Compose video
        click.echo("\n5. Composing final video...")
        composer = VideoComposer(
            width=settings.video_width,
            height=settings.video_height,
            duration=duration,
        )

        safe_category = fact.category.replace("/", "_").replace(" ", "_").replace(":", "")
        output_path = settings.output_dir / f"short_{safe_category}_{timestamp}.mp4"

        music_path = music_track.path if music_track else None
        composer.compose(
            text_image_path, video_clip.path, output_path, music_path,
            start_time=start_time,
        )

        # Cleanup temp text image
        if text_image_path.exists():
            text_image_path.unlink()

        # Step 6: Final GPT Vision check — is the subject visible in the finished video?
        click.echo("\n6. Final verification — checking subject visibility...")
        subject_visible = reviewer.verify_final_video(output_path, fact.hook, fact.fact_text)

        if subject_visible:
            click.echo(click.style("   Subject is visible! Video is good.", fg="green"))
            break
        else:
            click.echo(click.style("   Subject NOT visible in final video. Rejecting and restarting...", fg="red"))
            if output_path.exists():
                output_path.unlink()
            output_path = None

    if not output_path or not output_path.exists():
        click.echo(click.style(f"Could not produce a good video after {MAX_TOPIC_ATTEMPTS} attempts.", fg="red"))
        sys.exit(1)

    click.echo(f"   Video saved: {output_path}")

    # Step 7: Generate YouTube metadata
    click.echo("\n7. Generating YouTube metadata...")
    metadata = fact_gen.generate_metadata(
        fact=fact,
        channel_name=settings.channel_name,
    )
    click.echo(f"   Title: {click.style(metadata.title, fg='yellow')}")
    click.echo(f"   Tags: {', '.join(metadata.tags[:5])}...")

    # Step 8: Upload to YouTube (if enabled)
    if not upload:
        click.echo("\n8. Skipping upload (pass --upload to upload)")
        click.echo(click.style("\n=== Video Generated Successfully! ===\n", fg="green", bold=True))
        click.echo(f"Output: {output_path}")
    else:
        click.echo(f"\n8. Uploading to YouTube ({privacy})...")

        from src.youtube_uploader import YouTubeUploader, VideoMetadata

        try:
            uploader = YouTubeUploader()

            video_metadata = VideoMetadata(
                title=metadata.title,
                description=metadata.description,
                tags=metadata.tags,
                category_id="27",  # Education
                privacy_status=privacy,
            )

            result = uploader.upload(output_path, video_metadata)

            if result.success:
                click.echo(click.style("\n=== Video Uploaded Successfully! ===\n", fg="green", bold=True))
                click.echo(f"Video URL: {click.style(result.video_url, fg='cyan')}")
                click.echo(f"Video ID: {result.video_id}")
                click.echo(f"Privacy: {privacy}")
            else:
                click.echo(click.style(f"\n=== Upload Failed ===\n", fg="red", bold=True))
                click.echo(f"Error: {result.error_message}")
                sys.exit(1)

        except Exception as e:
            click.echo(click.style(f"\n=== Upload Failed ===\n", fg="red", bold=True))
            click.echo(f"Error: {str(e)}")
            sys.exit(1)

    click.echo(f"\nMusic: {music_track.title}")


if __name__ == "__main__":
    cli()
