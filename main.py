#!/usr/bin/env python3
"""
TikTok Monitor - Main Orchestration Script
Monitors TikTok accounts, downloads videos, and sends Slack alerts
"""

import os
import sys
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional
from dotenv import load_dotenv

from apify_client import ApifyClient
from state_store import StateStore
from google_sheets import GoogleSheetsMonitor
from google_drive import GoogleDriveUploader
from slack_notifier import SlackNotifier
from tiktok_story_downloader import fetch_tiktok_stories, download_story_media


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
        # Load environment variables (for local dev)
        load_dotenv()
        
        # Initialize components
        self.apify_token = os.getenv("APIFY_API_TOKEN")
        self.state_store = StateStore(db_path=os.getenv("STATE_DB_PATH", "tiktok_state.db"))
        self.sheets_monitor = GoogleSheetsMonitor()
        self.drive_uploader = GoogleDriveUploader()
        self.slack_notifier = SlackNotifier()
        
        # Validate configuration
        if not self.apify_token:
            raise ValueError("APIFY_API_TOKEN is required")
        
        logger.info("TikTok Monitor initialized")
        logger.info(f"Google Drive configured: {self.drive_uploader.is_configured()}")
        logger.info(f"Slack configured: {self.slack_notifier.is_configured()}")
    
    def run(self):
        """Main execution flow"""
        logger.info("=" * 60)
        logger.info("Starting TikTok monitoring cycle")
        logger.info("=" * 60)
        
        try:
            # Step 1: Get monitored accounts
            accounts = self._get_monitored_accounts()
            logger.info(f"Found {len(accounts)} accounts to monitor")
            
            # Step 2: Process each account
            total_new_posts = 0
            for account in accounts:
                username = account['username']
                logger.info(f"\nProcessing @{username}...")
                
                new_posts = self._process_account(username)
                total_new_posts += new_posts
                
                logger.info(f"Processed {new_posts} new posts from @{username}")
            
            logger.info("=" * 60)
            logger.info(f"Monitoring cycle complete: {total_new_posts} new posts processed")
            logger.info("=" * 60)
            
            return total_new_posts
            
        except Exception as e:
            logger.error(f"Error in monitoring cycle: {e}", exc_info=True)
            raise
    
    def _get_monitored_accounts(self) -> List[Dict]:
        """
        Get list of accounts to monitor
        
        Returns:
            List of account dictionaries
        """
        try:
            accounts = self.sheets_monitor.get_monitored_accounts()
            if not accounts:
                logger.warning("No accounts found in Google Sheets, using fallback")
            return accounts
        except Exception as e:
            logger.error(f"Error fetching accounts: {e}")
            return self.sheets_monitor._get_fallback_accounts()
    
    def _process_account(self, username: str) -> int:
        """
        Process all stories/posts for a single account
        
        Args:
            username: TikTok username
            
        Returns:
            Number of new posts processed
        """
        try:
            # Fetch stories from TikTok via Apify
            stories = fetch_tiktok_stories(username, self.apify_token)
            
            if not stories:
                logger.info(f"No stories found for @{username}")
                return 0
            
            logger.info(f"Found {len(stories)} stories from @{username}")
            
            new_posts = 0
            for story in stories:
                if self._process_story(username, story):
                    new_posts += 1
            
            return new_posts
            
        except Exception as e:
            logger.error(f"Error processing account @{username}: {e}", exc_info=True)
            return 0
    
    def _process_story(self, username: str, story: Dict) -> bool:
        """
        Process a single story/post
        
        Args:
            username: TikTok username
            story: Story data from Apify
            
        Returns:
            True if this was a new post, False if already processed
        """
        # Extract metadata
        post_id = story.get('aweme_id') or story.get('video_id', 'unknown')
        
        # Check if already processed
        if self.state_store.is_processed(post_id):
            logger.debug(f"Skipping already processed post: {post_id}")
            return False
        
        logger.info(f"Processing new post: {post_id}")
        
        # Extract all metadata
        metadata = self._extract_metadata(username, story)
        
        # Download video if Drive is configured
        storage_url = None
        if self.drive_uploader.is_configured():
            storage_url = self._download_and_upload(username, story, metadata)
        else:
            logger.warning("Google Drive not configured, skipping video upload")
        
        # Save to state store BEFORE sending Slack (for idempotency)
        success = self.state_store.add_post(
            post_id=metadata['post_id'],
            author=metadata['author'],
            published_at=metadata['published_at'],
            url=metadata['url'],
            caption=metadata['caption'],
            transcript=metadata['transcript'],
            hashtags=metadata['hashtags'],
            storage_url=storage_url
        )
        
        if not success:
            logger.error(f"Failed to add post to state store: {post_id}")
            return False
        
        # Send Slack notification
        if self.slack_notifier.is_configured():
            slack_success = self.slack_notifier.send_new_video_alert(
                author=metadata['author'],
                published_at=metadata['published_at'],
                caption=metadata['caption'],
                transcript=metadata['transcript'],
                tiktok_url=metadata['url'],
                storage_url=storage_url
            )
            
            if slack_success:
                self.state_store.mark_slack_sent(post_id)
        else:
            logger.warning("Slack not configured, skipping notification")
        
        logger.info(f"✓ Successfully processed post: {post_id}")
        return True
    
    def _extract_metadata(self, username: str, story: Dict) -> Dict:
        """
        Extract metadata from story data
        
        Args:
            username: TikTok username
            story: Story data from Apify
            
        Returns:
            Dict with extracted metadata
        """
        post_id = story.get('aweme_id') or story.get('video_id', 'unknown')
        
        # Build TikTok URL
        url = f"https://www.tiktok.com/@{username}/video/{post_id}"
        if story.get('video_url_base'):
            url = story.get('video_url_base')
        
        # Extract caption
        caption = story.get('desc') or story.get('title') or ''
        
        # Extract transcript/subtitles if available
        transcript = None
        if story.get('subtitles'):
            transcript = story.get('subtitles')
        elif story.get('text_extra'):
            # Sometimes captions are in text_extra
            transcript = ' '.join([t.get('hashtag_name', '') for t in story.get('text_extra', [])])
        
        # Extract hashtags
        hashtags = []
        if story.get('text_extra'):
            for item in story.get('text_extra', []):
                if item.get('hashtag_name'):
                    hashtags.append(item['hashtag_name'])
        
        # Extract published timestamp
        published_at = story.get('create_time')
        if published_at:
            # Convert timestamp to ISO format
            try:
                dt = datetime.fromtimestamp(int(published_at))
                published_at = dt.isoformat()
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
    
    def _download_and_upload(
        self,
        username: str,
        story: Dict,
        metadata: Dict
    ) -> Optional[str]:
        """
        Download video and upload to Google Drive
        
        Args:
            username: TikTok username
            story: Story data from Apify
            metadata: Extracted metadata
            
        Returns:
            Google Drive URL or None if upload fails
        """
        try:
            # Download video
            logger.info("Downloading video...")
            filepath = download_story_media(story, download_dir="tiktok_stories")
            
            if not filepath:
                logger.warning("Failed to download video")
                return None
            
            # Upload to Google Drive
            logger.info("Uploading to Google Drive...")
            storage_url = self.drive_uploader.upload_story(
                file_path=filepath,
                username=username,
                story_id=metadata['post_id'],
                caption=metadata['caption']
            )
            
            # Clean up local file (optional)
            # os.remove(filepath)
            
            return storage_url
            
        except Exception as e:
            logger.error(f"Error downloading/uploading video: {e}", exc_info=True)
            return None


def main():
    """Main entry point"""
    try:
        monitor = TikTokMonitor()
        new_posts = monitor.run()
        
        if new_posts == 0:
            logger.info("No new posts found")
        
        sys.exit(0)
        
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
