"""
YouTube Shorts uploader using OAuth 2.0.
Handles authentication, video upload, and metadata management.
"""

import os
import time
import httplib2
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError


@dataclass
class VideoMetadata:
    """Metadata for YouTube upload."""
    title: str              # Max 100 chars
    description: str        # Max 5000 chars
    tags: List[str]         # Keywords for discovery
    category_id: str = "27" # 22 = People & Blogs, 27 = Education
    privacy_status: str = "public"  # "public", "private", or "unlisted"


@dataclass
class UploadResult:
    """Result of a YouTube upload."""
    success: bool
    video_id: Optional[str] = None
    video_url: Optional[str] = None
    error_message: Optional[str] = None


class YouTubeUploader:
    """Uploads videos to YouTube using OAuth 2.0."""

    SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
    API_SERVICE_NAME = "youtube"
    API_VERSION = "v3"

    # Retry configuration
    MAX_RETRIES = 5
    RETRIABLE_STATUS_CODES = [500, 502, 503, 504]

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        refresh_token: Optional[str] = None,
    ):
        """
        Initialize with OAuth credentials.

        If no arguments provided, reads from environment variables:
        - YOUTUBE_CLIENT_ID
        - YOUTUBE_CLIENT_SECRET
        - YOUTUBE_REFRESH_TOKEN
        """
        self.client_id = client_id or os.getenv("YOUTUBE_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("YOUTUBE_CLIENT_SECRET")
        self.refresh_token = refresh_token or os.getenv("YOUTUBE_REFRESH_TOKEN")

        if not all([self.client_id, self.client_secret, self.refresh_token]):
            raise ValueError(
                "Missing YouTube credentials. Provide client_id, client_secret, "
                "and refresh_token, or set YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, "
                "and YOUTUBE_REFRESH_TOKEN environment variables."
            )

        self.credentials = self._build_credentials()
        self.youtube = self._build_service()

    def _build_credentials(self) -> Credentials:
        """Build OAuth2 credentials from refresh token."""
        credentials = Credentials(
            token=None,  # Will be obtained via refresh
            refresh_token=self.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=self.client_id,
            client_secret=self.client_secret,
            scopes=self.SCOPES,
        )

        # Force refresh to get access token
        credentials.refresh(Request())
        return credentials

    def _build_service(self):
        """Build YouTube API service."""
        return build(
            self.API_SERVICE_NAME,
            self.API_VERSION,
            credentials=self.credentials,
        )

    def upload(
        self,
        video_path: Path,
        metadata: VideoMetadata,
        notify_subscribers: bool = True,
    ) -> UploadResult:
        """
        Upload video to YouTube with metadata.

        Args:
            video_path: Path to the video file
            metadata: VideoMetadata with title, description, tags, etc.
            notify_subscribers: Whether to notify channel subscribers

        Returns:
            UploadResult with success status and video URL or error message
        """
        video_path = Path(video_path)

        # Validate video exists
        if not video_path.exists():
            return UploadResult(
                success=False,
                error_message=f"Video file not found: {video_path}"
            )

        # Ensure #Shorts is in tags for proper categorization
        tags = list(metadata.tags) if metadata.tags else []
        if "Shorts" not in tags:
            tags.insert(0, "Shorts")

        # Build request body
        body = {
            "snippet": {
                "title": metadata.title[:100],  # YouTube limit
                "description": metadata.description[:5000],  # YouTube limit
                "tags": tags[:500],  # YouTube limit
                "categoryId": metadata.category_id,
            },
            "status": {
                "privacyStatus": metadata.privacy_status,
                "selfDeclaredMadeForKids": False,
            },
        }

        # Create media upload with resumable protocol
        media = MediaFileUpload(
            str(video_path),
            mimetype="video/mp4",
            resumable=True,
            chunksize=1024 * 1024,  # 1MB chunks
        )

        # Execute upload with retry
        try:
            print(f"Uploading: {metadata.title}")

            insert_request = self.youtube.videos().insert(
                part=",".join(body.keys()),
                body=body,
                media_body=media,
                notifySubscribers=notify_subscribers,
            )

            response = self._resumable_upload(insert_request)

            video_id = response.get("id")
            return UploadResult(
                success=True,
                video_id=video_id,
                video_url=f"https://youtube.com/shorts/{video_id}",
            )

        except HttpError as e:
            error_content = e.content.decode() if hasattr(e.content, 'decode') else str(e.content)
            return UploadResult(
                success=False,
                error_message=f"YouTube API error {e.resp.status}: {error_content}",
            )
        except Exception as e:
            return UploadResult(
                success=False,
                error_message=f"Upload failed: {str(e)}",
            )

    def _resumable_upload(self, insert_request):
        """Execute upload with retry logic for transient failures."""
        response = None
        error = None
        retry = 0

        while response is None:
            try:
                status, response = insert_request.next_chunk()

                if status:
                    progress = int(status.progress() * 100)
                    print(f"  Upload progress: {progress}%")

            except HttpError as e:
                if e.resp.status in self.RETRIABLE_STATUS_CODES:
                    error = f"Retriable HTTP error {e.resp.status}: {e.content}"
                else:
                    raise

            except (httplib2.HttpLib2Error, IOError) as e:
                error = f"Network error: {str(e)}"

            if error:
                retry += 1
                if retry > self.MAX_RETRIES:
                    raise Exception(f"Upload failed after {self.MAX_RETRIES} retries: {error}")

                # Exponential backoff
                sleep_seconds = 2 ** retry
                print(f"  Retry {retry}/{self.MAX_RETRIES} in {sleep_seconds}s: {error}")
                time.sleep(sleep_seconds)
                error = None

        print("  Upload complete!")
        return response

    def check_channel(self) -> dict:
        """
        Verify API access and get channel info.

        Returns:
            dict with channel info or error status
        """
        try:
            response = self.youtube.channels().list(
                part="snippet,statistics",
                mine=True
            ).execute()

            if response.get("items"):
                channel = response["items"][0]
                return {
                    "status": "ok",
                    "channel_id": channel["id"],
                    "channel_title": channel["snippet"]["title"],
                    "subscriber_count": channel["statistics"].get("subscriberCount", "hidden"),
                }
            else:
                return {"status": "error", "message": "No channel found for this account"}

        except HttpError as e:
            if e.resp.status == 403:
                return {"status": "quota_exceeded", "message": str(e)}
            return {"status": "error", "message": str(e)}


def upload_video(
    video_path: str,
    title: str,
    description: str,
    tags: List[str],
    privacy: str = "public",
    category_id: str = "27",
) -> UploadResult:
    """
    Convenience function to upload a video with minimal setup.

    Reads credentials from environment variables:
    - YOUTUBE_CLIENT_ID
    - YOUTUBE_CLIENT_SECRET
    - YOUTUBE_REFRESH_TOKEN

    Args:
        video_path: Path to video file
        title: Video title (max 100 chars)
        description: Video description (max 5000 chars)
        tags: List of tags for discovery
        privacy: "public", "private", or "unlisted"
        category_id: YouTube category (default "27" = Education)

    Returns:
        UploadResult with success status and video URL
    """
    uploader = YouTubeUploader()

    metadata = VideoMetadata(
        title=title,
        description=description,
        tags=tags,
        category_id=category_id,
        privacy_status=privacy,
    )

    return uploader.upload(Path(video_path), metadata)
