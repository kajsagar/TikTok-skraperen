#!/usr/bin/env python3
"""
TikTok Story Downloader using Apify
Downloads TikTok user stories via the Apify TikTok Story Viewer actor
"""

import os
import requests
import json
from apify_client import ApifyClient

# Configuration
APIFY_API_TOKEN = ""  # Replace with your Apify API token
DOWNLOAD_DIR = "tiktok_stories"  # Directory to save downloaded stories


def fetch_tiktok_stories(username, apify_token=APIFY_API_TOKEN):
    """
    Fetch TikTok stories for a given username using Apify
    
    Args:
        username: TikTok username to fetch stories from
        apify_token: Apify API token
        
    Returns:
        List of story data from Apify
    """
    client = ApifyClient(apify_token)
    
    # Prepare the Actor input
    run_input = {
        "usernames": [username],
    }
    
    print(f"Fetching stories for @{username}...")
    
    # Run the Actor and wait for it to finish
    run = client.actor("igview-owner/tiktok-story-viewer").call(run_input=run_input)
    
    # Fetch results from the run's dataset
    stories = []
    for item in client.dataset(run["defaultDatasetId"]).iterate_items():
        stories.append(item)
    
    print(f"Found {len(stories)} stories")
    return stories


def download_story_media(story_data, download_dir=DOWNLOAD_DIR):
    """
    Download media files from story data
    
    Args:
        story_data: Story data from Apify containing media URLs
        download_dir: Directory to save downloaded files
    """
    # Create download directory if it doesn't exist
    os.makedirs(download_dir, exist_ok=True)
    
    # Extract username and story ID from Apify response
    username = story_data.get('unique_id', 'unknown')
    story_id = story_data.get('aweme_id') or story_data.get('video_id', 'unknown')
    
    # Create user-specific directory
    user_dir = os.path.join(download_dir, str(username))
    os.makedirs(user_dir, exist_ok=True)
    
    # Get media URL from Apify response (top-level field)
    media_url = story_data.get('video_url')
    
    if not media_url:
        print(f"No media URL found for story {story_id}")
        return None
    
    # Determine file extension based on URL or default to mp4
    if '.jpg' in media_url or '.jpeg' in media_url or '.webp' in media_url:
        extension = '.jpg'
    else:
        extension = '.mp4'
    
    # Create filename
    filename = f"{story_id}{extension}"
    filepath = os.path.join(user_dir, filename)
    
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


def download_user_stories(username, apify_token=APIFY_API_TOKEN, download_dir=DOWNLOAD_DIR):
    """
    Fetch and download all stories for a TikTok user
    
    Args:
        username: TikTok username
        apify_token: Apify API token
        download_dir: Directory to save downloads
        
    Returns:
        List of downloaded file paths
    """
    # Fetch stories
    stories = fetch_tiktok_stories(username, apify_token)
    
    if not stories:
        print(f"No stories found for @{username}")
        return []
    
    # Download each story
    downloaded_files = []
    for story in stories:
        filepath = download_story_media(story, download_dir)
        if filepath:
            downloaded_files.append(filepath)
    
    print(f"\n✓ Downloaded {len(downloaded_files)} stories to {download_dir}/{username}/")
    return downloaded_files


def main():
    """Main function with example usage"""
    # Example: Download stories from multiple users
    usernames = [
        "danieljensen",  # Replace with actual TikTok username
        # "username2",
        # Add more usernames as needed
    ]
    
    # Check if API token is set
    if APIFY_API_TOKEN == "YOUR_APIFY_API_TOKEN":
        print("ERROR: Please set your Apify API token in the script")
        print("Get your token from: https://console.apify.com/account/integrations")
        return
    
    # Download stories for each user
    for username in usernames:
        print(f"\n{'='*50}")
        print(f"Processing @{username}")
        print('='*50)
        try:
            download_user_stories(username)
        except Exception as e:
            print(f"Error processing @{username}: {e}")
    
    print("\n✓ All done!")


if __name__ == "__main__":
    main()
