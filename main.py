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
@click.option("--music-dir", "-m", default=None, help="Path to folder with YouTube Audio Library mp3s")
@click.option("--output", "-o", default=None, help="Output filename")
def generate(topic, duration, no_music, music_dir, output):
    """Generate a new YouTube Short with a viral fact."""

    # Validate configuration
    errors = settings.validate()
    if errors:
        for error in errors:
            click.echo(click.style(f"Error: {error}", fg="red"))
        click.echo("\nRun 'python main.py check' for setup instructions.")
        return

    click.echo(click.style("\n=== YouTube Shorts Generator ===\n", fg="cyan", bold=True))

    # Step 1: Find a viral video and verify with GPT Vision
    click.echo("1. Finding viral video content...")
    fetcher = VideoFetcher(settings.pexels_api_key, settings.video_cache_dir)
    reviewer = VisionReviewer(settings.openai_api_key)

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
        click.echo(click.style("Could not find a verified video after 5 attempts.", fg="red"))
        return

    # Calculate best start time and crop position from vision analysis
    start_time = reviewer.get_best_start_time(vision_result)
    subject_position = vision_result.subject_position
    click.echo(f"   Smart crop: start at {start_time:.1f}s, subject at {subject_position}")

    # Step 2: Generate fact that MATCHES the video
    click.echo("\n2. Generating matching viral fact...")
    fact_gen = FactGenerator(settings.openai_api_key)
    # Use the description (not search_term) - this is the exact description of what the video shows
    fact = fact_gen.generate_for_video(video_clip.description)

    click.echo(f"   Hook: {click.style(fact.hook, fg='yellow')}")
    click.echo(f"   Fact: {fact.fact_text}")
    click.echo(f"   Highlights: {', '.join(fact.highlight_words)}")
    click.echo(f"   Category: {fact.category}")

    # Step 3: Get music
    music_track = None
    if not no_music:
        click.echo("\n3. Getting background music...")
        music_mgr = MusicManager("", settings.music_cache_dir)

        # Determine music folder (custom or default assets/music)
        music_folder = Path(music_dir) if music_dir else settings.yt_music_dir
        using_yt_library = False

        # Check for YouTube Audio Library tracks in music folder
        if music_folder.exists():
            mp3_files = list(music_folder.glob("*.mp3"))
            if mp3_files:
                import random
                selected_track = random.choice(mp3_files)
                music_track = music_mgr.get_local_track(selected_track)
                using_yt_library = True
                click.echo(f"   Track: {click.style(music_track.title, fg='magenta')}")
                click.echo(f"   Source: {click.style('YouTube Audio Library', fg='cyan')}")
                click.echo(f"   {click.style('✓ Safe for monetization & may auto-tag!', fg='green')}")

        # Fallback to Kevin MacLeod tracks
        if not using_yt_library:
            music_track = music_mgr.get_random_track(min_duration=duration)
            if music_track and music_track.path:
                click.echo(f"   Track: {click.style(music_track.title, fg='magenta')}")
                click.echo(f"   Artist: {music_track.artist}")
                click.echo(f"   {click.style('TIP: Add trending sounds to assets/music/ for auto-tagging!', fg='yellow')}")
    else:
        click.echo("\n3. Skipping music (--no-music flag)")

    # Step 4: Render text with branding (highlight color is randomized automatically)
    click.echo("\n4. Rendering text overlay with branding...")
    # Text area height = total height - video height - bottom padding
    # 1920 - 750 (video) - 180 (bottom padding) = 990
    renderer = TextRenderer(
        height=990,  # Text area height
        font_size_hook=settings.font_size_hook,
        font_size_fact=settings.font_size_fact,
        text_color=settings.text_color,
        bg_color=settings.bg_color,
        logo_path=settings.logo_path,
        channel_name=settings.channel_name,
        channel_handle=settings.channel_handle,
    )
    # Show which color was randomly selected
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
        # Make category safe for filename (remove slashes, spaces, special chars)
        safe_category = fact.category.replace("/", "_").replace(" ", "_").replace(":", "")
        output_path = settings.output_dir / f"short_{safe_category}_{timestamp}.mp4"

    music_path = music_track.path if music_track else None
    composer.compose(
        text_image_path, video_clip.path, output_path, music_path,
        start_time=start_time, subject_position=subject_position,
    )

    # Cleanup temp files
    if text_image_path.exists():
        text_image_path.unlink()

    # Final output
    click.echo(click.style("\n=== Video Generated Successfully! ===\n", fg="green", bold=True))
    click.echo(f"Output: {click.style(str(output_path), fg='cyan')}")
    click.echo(f"Duration: {duration} seconds")
    click.echo(f"Resolution: {settings.video_width}x{settings.video_height}")

    if music_track and music_track.path:
        click.echo(f"\n{click.style('Music Credit (for YouTube description):', fg='yellow')}")
        click.echo(f"  {music_track.title} by {music_track.artist}")
        click.echo(f"  Source: {music_track.source_url}")


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
@click.option("--no-upload", is_flag=True, default=False, help="Generate video without uploading to YouTube")
def auto(topic, duration, privacy, no_upload):
    """Generate and upload a YouTube Short automatically.

    This command is designed for automation (GitHub Actions, cron jobs, etc.).
    It generates a video and uploads it to YouTube with auto-generated metadata.

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

    # Step 1: Find a viral video and verify with GPT Vision
    click.echo("1. Finding viral video content...")
    fetcher = VideoFetcher(settings.pexels_api_key, settings.video_cache_dir)
    reviewer = VisionReviewer(settings.openai_api_key)

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
        click.echo(click.style("Could not find a verified video after 5 attempts.", fg="red"))
        sys.exit(1)

    # Calculate best start time and crop position from vision analysis
    start_time = reviewer.get_best_start_time(vision_result)
    subject_position = vision_result.subject_position
    click.echo(f"   Smart crop: start at {start_time:.1f}s, subject at {subject_position}")

    # Step 2: Generate fact that matches the video
    click.echo("\n2. Generating matching viral fact...")
    fact_gen = FactGenerator(settings.openai_api_key)
    fact = fact_gen.generate_for_video(video_clip.description)

    click.echo(f"   Hook: {click.style(fact.hook, fg='yellow')}")
    click.echo(f"   Fact: {fact.fact_text}")
    click.echo(f"   Category: {fact.category}")

    # Step 3: Get music
    click.echo("\n3. Getting background music...")
    music_mgr = MusicManager("", settings.music_cache_dir)

    music_track = None
    music_credit = ""

    # Check for YouTube Audio Library tracks first
    if settings.yt_music_dir.exists():
        mp3_files = list(settings.yt_music_dir.glob("*.mp3"))
        if mp3_files:
            import random
            selected_track = random.choice(mp3_files)
            music_track = music_mgr.get_local_track(selected_track)
            music_credit = f"{music_track.title} (YouTube Audio Library)"
            click.echo(f"   Track: {click.style(music_track.title, fg='magenta')}")

    # Fallback to Kevin MacLeod tracks
    if not music_track:
        music_track = music_mgr.get_random_track(min_duration=duration)
        if music_track and music_track.path:
            music_credit = f"{music_track.title} by {music_track.artist} ({music_track.source_url})"
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
        start_time=start_time, subject_position=subject_position,
    )

    # Cleanup temp files
    if text_image_path.exists():
        text_image_path.unlink()

    click.echo(f"   Video saved: {output_path}")

    # Step 6: Generate YouTube metadata
    click.echo("\n6. Generating YouTube metadata...")
    metadata = fact_gen.generate_metadata(
        fact=fact,
        channel_name=settings.channel_name,
    )
    click.echo(f"   Title: {click.style(metadata.title, fg='yellow')}")
    click.echo(f"   Tags: {', '.join(metadata.tags[:5])}...")

    # Step 7: Upload to YouTube (if enabled)
    if no_upload:
        click.echo("\n7. Skipping upload (--no-upload flag)")
        click.echo(click.style("\n=== Video Generated Successfully! ===\n", fg="green", bold=True))
        click.echo(f"Output: {output_path}")
    else:
        click.echo(f"\n7. Uploading to YouTube ({privacy})...")

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

    # Output music credit for reference
    if music_credit:
        click.echo(f"\nMusic Credit: {music_credit}")


if __name__ == "__main__":
    cli()
