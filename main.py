#!/usr/bin/env python3
"""
TikTok Monitor - Main Orchestration Script
Monitors TikTok accounts, downloads videos, and sends Slack alerts (BATCH OPTIMIZED)
"""

import os
import sys
import logging
from datetime import datetime
from typing import List, Dict, Optional
from dotenv import load_dotenv

from apify_client import ApifyClient
from state_store import StateStore
from google_sheets import GoogleSheetsMonitor
from google_drive import GoogleDriveUploader
from slack_notifier import SlackNotifier
# VIKTIG ENDRING HER: Vi importerer den nye batch-funksjonen
from tiktok_story_downloader import fetch_tiktok_stories_batch, download_story_media, DOWNLOAD_DIR


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('tiktok_monitor.log')
    ]
)
logger = logging.getLogger(__name__)


class TikTokMonitor:
    """Main orchestration class for TikTok monitoring"""
    
    def __init__(self):
        """Initialize the TikTok monitor with all required components"""
        load_dotenv()
        
        self.apify_token = os.getenv("APIFY_API_TOKEN")
        self.state_store = StateStore(db_path=os.getenv("STATE_DB_PATH", "tiktok_state.db"))
        self.sheets_monitor = GoogleSheetsMonitor()
        self.drive_uploader = GoogleDriveUploader()
        self.slack_notifier = SlackNotifier()
        
        if not self.apify_token:
            raise ValueError("APIFY_API_TOKEN is required")
        
        logger.info("TikTok Monitor initialized")
        logger.info(f"Google Drive configured: {self.drive_uploader.is_configured()}")
        logger.info(f"Slack configured: {self.slack_notifier.is_configured()}")
    
    def run(self):
        """Main execution flow - BATCH OPTIMIZED"""
        logger.info("=" * 60)
        logger.info("Starting TikTok monitoring cycle (Batch Mode)")
        logger.info("=" * 60)
        
        try:
            # Step 1: Get monitored accounts from Sheets
            accounts = self._get_monitored_accounts()
            if not accounts:
                logger.warning("No accounts to monitor. Exiting.")
                return 0
                
            # Extract just the usernames into a list
            usernames = [account['username'] for account in accounts]
            logger.info(f"Found {len(usernames)} accounts to monitor in Google Sheets")
            
            # Step 2: Fetch ALL stories in ONE Apify call (Saves money!)
            logger.info("Fetching data from Apify for all users...")
            all_stories = fetch_tiktok_stories_batch(usernames, self.apify_token)
            
            logger.info(f"Apify returned {len(all_stories)} total stories across all users")
            
            # Step 3: Process the results
            total_new_posts = 0
            for story in all_stories:
                # Get username from story data
                username = story.get('unique_id', 'unknown')
                
                # Check if this story is new
                if self._process_story(username, story):
                    total_new_posts += 1
            
            logger.info("=" * 60)
            logger.info(f"Monitoring cycle complete: {total_new_posts} new posts processed and downloaded")
            logger.info("=" * 60)
            
            return total_new_posts
            
        except Exception as e:
            logger.error(f"Error in monitoring cycle: {e}", exc_info=True)
            raise
    
    def _get_monitored_accounts(self) -> List[Dict]:
        """Get list of accounts to monitor"""
        try:
            accounts = self.sheets_monitor.get_monitored_accounts()
            if not accounts:
                logger.warning("No accounts found in Google Sheets, using fallback")
                return self.sheets_monitor._get_fallback_accounts()
            return accounts
        except Exception as e:
            logger.error(f"Error fetching accounts: {e}")
            return self.sheets_monitor._get_fallback_accounts()
    
    def _process_story(self, username: str, story: Dict) -> bool:
        """
        Process a single story/post
        
        Returns:
            True if this was a new post, False if already processed or invalid
        """
        post_id = story.get('aweme_id') or story.get('video_id')
        if not post_id:
             logger.warning(f"Found story without ID for {username}. Skipping.")
             return False
             
        # Check if already processed (avoids re-downloading!)
        if self.state_store.is_processed(post_id):
            logger.debug(f"Skipping already processed post: {post_id}")
            return False
        
        logger.info(f"Processing new post from @{username} (ID: {post_id})")
        
        metadata = self._extract_metadata(username, story)
        
        # Download video locally
        logger.info(f"Downloading video for @{username}...")
        filepath = download_story_media(story, download_dir=DOWNLOAD_DIR)
        
        if not filepath:
             logger.error(f"Failed to download video {post_id}")
             return False

        # Upload to Google Drive
        storage_url = None
        if self.drive_uploader.is_configured():
            logger.info("Uploading to Google Drive...")
            try:
                storage_url = self.drive_uploader.upload_story(
                    file_path=filepath,
                    username=username,
                    story_id=post_id,
                    caption=metadata['caption']
                )
            except Exception as e:
                 logger.error(f"Drive upload failed: {e}")
        else:
            logger.warning("Google Drive not configured, keeping file locally only")
        
        # Save to state store so we don't download it again next time
        success = self.state_store.add_post(
            post_id=post_id,
            author=username,
            published_at=metadata['published_at'],
            url=metadata['url'],
            caption=metadata['caption'],
            transcript=metadata.get('transcript'),
            hashtags=metadata.get('hashtags', []),
            storage_url=storage_url
        )
        
        if not success:
            logger.error(f"Failed to add post to state store: {post_id}")
            return False
        
        # Send Slack notification
        if self.slack_notifier.is_configured():
            try:
                slack_success = self.slack_notifier.send_new_video_alert(
                    author=username,
                    published_at=metadata['published_at'],
                    caption=metadata['caption'],
                    transcript=metadata.get('transcript'),
                    tiktok_url=metadata['url'],
                    storage_url=storage_url
                )
                if slack_success:
                    self.state_store.mark_slack_sent(post_id)
            except Exception as e:
                 logger.error(f"Slack notification failed: {e}")
        
        logger.info(f"✓ Successfully fully processed post: {post_id}")
        return True
    
    def _extract_metadata(self, username: str, story: Dict) -> Dict:
        """Extract metadata from story data"""
        post_id = story.get('aweme_id') or story.get('video_id', 'unknown')
        url = story.get('video_url_base', f"https://www.tiktok.com/@{username}/video/{post_id}")
        caption = story.get('desc') or story.get('title') or ''
        
        transcript = story.get('subtitles')
        if not transcript and story.get('text_extra'):
            transcript = ' '.join([t.get('hashtag_name', '') for t in story.get('text_extra', [])])
            
        hashtags = [item['hashtag_name'] for item in story.get('text_extra', []) if item.get('hashtag_name')]
        
        published_at = story.get('create_time')
        if published_at:
            try:
                published_at = datetime.fromtimestamp(int(published_at)).isoformat()
            except:
                published_at = str(published_at)
        else:
            published_at = datetime.utcnow().isoformat()
        
        return {
            'post_id': post_id,
            'author': username,
            'published_at': published_at,
            'url': url,
            'caption': caption,
            'transcript': transcript,
            'hashtags': hashtags
        }

def main():
    """Main entry point"""
    try:
        monitor = TikTokMonitor()
        new_posts = monitor.run()
        
        if new_posts == 0:
            logger.info("No new posts found during this cycle")
            
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()