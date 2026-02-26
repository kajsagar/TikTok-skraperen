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
APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN")  # Load from .env file
DOWNLOAD_DIR = "stories"  # Directory to save downloaded stories


def fetch_tiktok_stories_batch(usernames, apify_token=APIFY_API_TOKEN):
    """
    Fetch TikTok stories for MULTIPLE usernames using Apify in a single run
    """
    client = ApifyClient(apify_token)
    
    # Prepare the Actor input - THIS IS THE COST SAVER (Batching)
    run_input = {
        "uniqueIds": usernames,
    }
    
    print(f"Fetching stories for {len(usernames)} users simultaneously...")

    # Run the Actor and wait for it to finish
    run = client.actor("igview-owner/tiktok-story-viewer").call(run_input=run_input)

    # Fetch results from the run's dataset
    stories = []
    for item in client.dataset(run["defaultDatasetId"]).iterate_items():
        stories.append(item)

    print(f"Found {len(stories)} stories in total")
    return stories


def download_story_media(story_data, download_dir=DOWNLOAD_DIR):
    """
    Download media files from story data safely handling both video and photo modes
    """
    # Create download directory if it doesn't exist
    os.makedirs(download_dir, exist_ok=True)

    # Extract username and story ID from Apify response
    username = story_data.get('unique_id', 'unknown')
    story_id = story_data.get('aweme_id') or story_data.get('video_id', 'unknown')

    # Create user-specific directory
    user_dir = os.path.join(download_dir, str(username))
    os.makedirs(user_dir, exist_ok=True)

    # --- NY LOGIKK FOR Å SKILLE MELLOM VIDEO OG BILDE (PHOTO MODE) ---
    media_url = None
    extension = '.mp4' # Vi antar video som standard
    
    # 1. Sjekk om dette er en bilde-story (Photo mode)
    if story_data.get('imagePost') or story_data.get('images') or story_data.get('image_url'):
        extension = '.jpg'
        
        # Prøv å hente ut bilde-lenken fra de ulike formatene Apify kan returnere
        if story_data.get('image_url'):
            media_url = story_data.get('image_url')
        elif story_data.get('images') and isinstance(story_data['images'], list) and len(story_data['images']) > 0:
            first_img = story_data['images'][0]
            if isinstance(first_img, str):
                media_url = first_img
            elif isinstance(first_img, dict):
                # TikTok sine komplekse bilde-strukturer
                media_url = first_img.get('imageURL', {}).get('urlList', [None])[0] or first_img.get('url')
    
    # 2. Hvis det IKKE var et bilde, let etter den vanlige videoen
    if not media_url:
        media_url = story_data.get('video_url') or story_data.get('download_url') or story_data.get('playAddr')
        
    # 3. Siste sikkerhetssjekk: Hvis lenken tilfeldigvis slutter på bildeformat uansett
    if media_url and any(ext in media_url.lower() for ext in ['.jpg', '.jpeg', '.webp', '.png']):
        extension = '.jpg'
    # -----------------------------------------------------------------

    if not media_url:
        print(f"No media URL found for story {story_id}")
        return None

    # Create filename
    filename = f"{story_id}{extension}"
    filepath = os.path.join(user_dir, filename)

    # COST SAVER: Check if we already have the file
    if os.path.exists(filepath):
        print(f"File {filename} already exists. Skipping download.")
        return filepath

    # Download the file
    print(f"Downloading {filename}...")
    try:
        response = requests.get(media_url, stream=True)
        response.raise_for_status()
        
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        print(f"✓ Saved to {filepath}")
        return filepath
    
    except Exception as e:
        print(f"✗ Error downloading {filename}: {e}")
        return None


def process_all_users(usernames, apify_token=APIFY_API_TOKEN, download_dir=DOWNLOAD_DIR):
    """
    Fetch and download all stories for a list of TikTok users efficiently
    """
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
    """Main function with example usage"""
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