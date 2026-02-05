#!/usr/bin/env python3
"""
One-time script to generate YouTube OAuth refresh token.

USAGE:
1. Create a Google Cloud project at https://console.cloud.google.com
2. Enable YouTube Data API v3
3. Create OAuth 2.0 credentials (Desktop app type)
4. Download credentials JSON and save as 'client_secrets.json' in this directory
5. Run this script: python scripts/setup_youtube_oauth.py
6. Copy the refresh token to GitHub Secrets as YOUTUBE_REFRESH_TOKEN

IMPORTANT: This script must be run LOCALLY (not in GitHub Actions)
because it requires browser-based OAuth consent.
"""

import json
import sys
from pathlib import Path

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
except ImportError:
    print("ERROR: google-auth-oauthlib not installed!")
    print()
    print("Install with: pip install google-auth-oauthlib")
    sys.exit(1)


SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def find_client_secrets():
    """Find client_secrets.json in common locations."""
    search_paths = [
        Path("client_secrets.json"),
        Path("scripts/client_secrets.json"),
        Path.home() / "Downloads" / "client_secrets.json",
    ]

    # Also check for files matching client_secret_*.json pattern
    for pattern_path in [Path("."), Path("scripts"), Path.home() / "Downloads"]:
        if pattern_path.exists():
            for f in pattern_path.glob("client_secret*.json"):
                search_paths.insert(0, f)

    for path in search_paths:
        if path.exists():
            return path

    return None


def main():
    print("=" * 60)
    print("YouTube OAuth Setup")
    print("=" * 60)
    print()

    # Check for client secrets file
    secrets_file = find_client_secrets()

    if not secrets_file:
        print("ERROR: client_secrets.json not found!")
        print()
        print("To create this file:")
        print("1. Go to https://console.cloud.google.com")
        print("2. Create a new project (or select existing)")
        print("3. Enable 'YouTube Data API v3':")
        print("   - APIs & Services > Library > search 'YouTube Data API v3' > Enable")
        print("4. Configure OAuth consent screen:")
        print("   - APIs & Services > OAuth consent screen")
        print("   - Select 'External' user type")
        print("   - Fill in app name and email fields")
        print("   - Add scope: youtube.upload")
        print("   - Add yourself as a test user")
        print("5. Create OAuth credentials:")
        print("   - APIs & Services > Credentials")
        print("   - Create Credentials > OAuth 2.0 Client ID")
        print("   - Select 'Desktop app' as application type")
        print("   - Download the JSON file")
        print("6. Save the downloaded file as 'client_secrets.json' in this directory")
        print()
        print("Then run this script again.")
        sys.exit(1)

    print(f"Found credentials file: {secrets_file}")
    print()

    # Load client secrets
    with open(secrets_file) as f:
        client_config = json.load(f)

    # Get client ID and secret for output
    if "installed" in client_config:
        client_id = client_config["installed"]["client_id"]
        client_secret = client_config["installed"]["client_secret"]
    elif "web" in client_config:
        client_id = client_config["web"]["client_id"]
        client_secret = client_config["web"]["client_secret"]
    else:
        print("ERROR: Invalid client_secrets.json format")
        print("Expected 'installed' or 'web' key in JSON")
        sys.exit(1)

    print("Starting OAuth flow...")
    print("A browser window will open for authentication.")
    print()
    print("IMPORTANT: Sign in with the Google account that owns your YouTube channel!")
    print()

    # Run OAuth flow
    flow = InstalledAppFlow.from_client_secrets_file(
        str(secrets_file),
        scopes=SCOPES,
    )

    # This will open a browser for user consent
    try:
        credentials = flow.run_local_server(
            port=8080,
            prompt="consent",  # Force consent screen to ensure refresh token
            access_type="offline",  # Required for refresh token
        )
    except Exception as e:
        print(f"ERROR: OAuth flow failed: {e}")
        print()
        print("Make sure:")
        print("- You're not blocking popups")
        print("- Port 8080 is not in use")
        print("- You complete the authorization in your browser")
        sys.exit(1)

    if not credentials.refresh_token:
        print("ERROR: No refresh token received!")
        print()
        print("This can happen if you've already authorized this app before.")
        print("To fix this:")
        print("1. Go to https://myaccount.google.com/permissions")
        print("2. Find and remove your app")
        print("3. Run this script again")
        sys.exit(1)

    print()
    print("=" * 60)
    print("SUCCESS! Add these to GitHub Secrets:")
    print("=" * 60)
    print()
    print("Go to your GitHub repository:")
    print("  Settings > Secrets and variables > Actions > New repository secret")
    print()
    print("-" * 60)
    print("Secret name: YOUTUBE_CLIENT_ID")
    print(f"Secret value: {client_id}")
    print("-" * 60)
    print()
    print("-" * 60)
    print("Secret name: YOUTUBE_CLIENT_SECRET")
    print(f"Secret value: {client_secret}")
    print("-" * 60)
    print()
    print("-" * 60)
    print("Secret name: YOUTUBE_REFRESH_TOKEN")
    print(f"Secret value: {credentials.refresh_token}")
    print("-" * 60)
    print()
    print("=" * 60)
    print("IMPORTANT: Keep these values secret!")
    print("Never commit them to version control.")
    print("=" * 60)
    print()

    # Optionally save to a local file for testing
    save_local = input("Save credentials to .env.youtube for local testing? (y/n): ").lower().strip()
    if save_local == 'y':
        env_content = f"""# YouTube OAuth Credentials (DO NOT COMMIT!)
YOUTUBE_CLIENT_ID={client_id}
YOUTUBE_CLIENT_SECRET={client_secret}
YOUTUBE_REFRESH_TOKEN={credentials.refresh_token}
"""
        env_path = Path(".env.youtube")
        env_path.write_text(env_content)
        print(f"Saved to {env_path}")
        print("Add '.env.youtube' to your .gitignore!")


if __name__ == "__main__":
    main()
