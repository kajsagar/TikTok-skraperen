#!/usr/bin/env python3
"""
TikTok Story Downloader using Apify
Downloads TikTok user stories via the Apify TikTok Story Viewer actor (BATCH OPTIMIZED)
"""

import os
import requests
import json
from apify_client import ApifyClient
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration
APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN")
DOWNLOAD_DIR = "stories"

def fetch_tiktok_stories_batch(usernames, apify_token=APIFY_API_TOKEN):
    """
    Fetch TikTok stories for MULTIPLE usernames using Apify in a single run
    """
    client = ApifyClient(apify_token)
    run_input = {"uniqueIds": usernames}
    
    print(f"Fetching stories for {len(usernames)} users simultaneously...")
    run = client.actor("igview-owner/tiktok-story-viewer").call(run_input=run_input)

    stories = []
    for item in client.dataset(run["defaultDatasetId"]).iterate_items():
        stories.append(item)

    print(f"Found {len(stories)} stories in total")
    return stories

def download_story_media(story_data, download_dir=DOWNLOAD_DIR):
    """
    Download media safely by reading the file's Content-Type headers directly from the internet.
    """
    os.makedirs(download_dir, exist_ok=True)

    username = story_data.get('unique_id', 'unknown')
    story_id = str(story_data.get('aweme_id') or story_data.get('video_id', 'unknown'))

    user_dir = os.path.join(download_dir, username)
    os.makedirs(user_dir, exist_ok=True)

    media_url = None
    is_photo = False

    # 1. LET ETTER BILDER FØRST (Photo mode)
    if story_data.get('images') and len(story_data['images']) > 0:
        first_img = story_data['images'][0]
        if isinstance(first_img, str):
            media_url = first_img
        elif isinstance(first_img, dict):
            media_url = first_img.get('imageURL', {}).get('urlList', [None])[0] or first_img.get('url')
        is_photo = True
    elif story_data.get('image_url'):
        media_url = story_data.get('image_url')
        is_photo = True

    # 2. HVIS INGEN BILDER FANTES, FINN VIDEO
    if not media_url:
        media_url = story_data.get('video_url') or story_data.get('download_url') or story_data.get('playAddr')

    if not media_url:
        print(f"No media URL found for story {story_id}")
        return None

    try:
        # Bank på døren til filen og be om 'ID-kortet' før vi laster den ned (stream=True)
        response = requests.get(media_url, stream=True, timeout=30)
        response.raise_for_status()

        # Den magiske sjekken: Hva ER egentlig denne filen?
        content_type = response.headers.get('Content-Type', '').lower()

        # Hvis internett sier at dette bare er lyd (feilaktig returnert av TikTok)
        if 'audio' in content_type:
            print(f"⚠️ Avbrutt: Fant bare en lydfil ({content_type}) for {story_id}. Hopper over!")
            return None

        # Sett riktig filendelse basert på ID-kortet
        if 'image' in content_type or is_photo:
            extension = '.jpg'
        else:
            extension = '.mp4'

        filename = f"{story_id}{extension}"
        filepath = os.path.join(user_dir, filename)

        if os.path.exists(filepath):
            print(f"File {filename} already exists. Skipping download.")
            return filepath

        print(f"Downloading {filename}...")
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        print(f"✓ Saved to {filepath} (Type: {content_type})")
        return filepath
    
    except Exception as e:
        print(f"✗ Error downloading {story_id}: {e}")
        return None

def process_all_users(usernames, apify_token=APIFY_API_TOKEN, download_dir=DOWNLOAD_DIR):
    stories = fetch_tiktok_stories_batch(usernames, apify_token)
    
    if not stories:
        print("No stories found for the provided users.")
        return []

    downloaded_files = []
    for story in stories:
        filepath = download_story_media(story, download_dir)
        if filepath:
            downloaded_files.append(filepath)

    print(f"\n✓ Finished processing. Handled {len(downloaded_files)} stories.")
    return downloaded_files

def main():
    usernames = ["julie__fiala", "notleahhhbeauty"]
    if not APIFY_API_TOKEN:
        print("ERROR: Please set APIFY_API_TOKEN in your .env file")
        return
    
    print(f"\n{'='*50}")
    print(f"Starting BATCH processing for {len(usernames)} users")
    print('='*50)
    
    try:
        process_all_users(usernames)
    except Exception as e:
        print(f"Error processing users: {e}")

    print("\n✓ All done!")

if __name__ == "__main__":
    main()