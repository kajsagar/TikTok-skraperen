#!/usr/bin/env python3
"""
Slack Notification Module
Sends formatted alerts about new TikTok videos to Slack
"""

import os
import json
from typing import Optional, Dict
import requests


class SlackNotifier:
    """Sends notifications to Slack via webhook or bot token"""
    
    def __init__(self, webhook_url: str = None, bot_token: str = None, channel_id: str = None):
        """
        Initialize Slack notifier
        
        Args:
            webhook_url: Slack Webhook URL (preferred method)
            bot_token: Slack Bot Token (alternative method)
            channel_id: Slack Channel ID (required if using bot_token)
        """
        self.webhook_url = webhook_url or os.getenv("SLACK_WEBHOOK_URL")
        self.bot_token = bot_token or os.getenv("SLACK_BOT_TOKEN")
        self.channel_id = channel_id or os.getenv("SLACK_CHANNEL_ID")
    
    def send_new_video_alert(
        self,
        author: str,
        published_at: str,
        caption: Optional[str],
        transcript: Optional[str],
        tiktok_url: str,
        storage_url: Optional[str] = None
    ) -> bool:
        """
        Send a formatted alert about a new TikTok video
        
        Args:
            author: TikTok username
            published_at: Publication timestamp
            caption: Video caption
            transcript: Video transcript/captions
            tiktok_url: Original TikTok URL
            storage_url: Internal Google Drive URL (if available)
            
        Returns:
            True if message sent successfully
        """
        # Format the message
        message = self._format_message(
            author=author,
            published_at=published_at,
            caption=caption,
            transcript=transcript,
            tiktok_url=tiktok_url,
            storage_url=storage_url
        )
        
        # Send via webhook or bot token
        if self.webhook_url:
            return self._send_webhook(message)
        elif self.bot_token and self.channel_id:
            return self._send_bot_message(message)
        else:
            print("Error: No Slack configuration found (webhook or bot token)")
            return False
    
    def _format_message(
        self,
        author: str,
        published_at: str,
        caption: Optional[str],
        transcript: Optional[str],
        tiktok_url: str,
        storage_url: Optional[str]
    ) -> Dict:
        """
        Format Slack message with blocks for rich formatting
        
        Returns:
            Dict with Slack message payload
        """
        # Truncate transcript to 500 chars
        transcript_text = "Not available"
        if transcript:
            transcript_text = transcript[:500]
            if len(transcript) > 500:
                transcript_text += "..."
        
        # Build message blocks
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"🎬 New TikTok video: @{author}"
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Published:*\n{published_at}"
                    }
                ]
            }
        ]
        
        # Add caption if available
        if caption:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Caption:*\n{caption}"
                }
            })
        
        # Add transcript
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Transcript:*\n{transcript_text}"
            }
        })
        
        # Add URLs section
        url_text = f"*TikTok:* <{tiktok_url}|View on TikTok>\n"
        
        if storage_url:
            url_text += f"*Internal video:* <{storage_url}|View on Google Drive>"
        else:
            url_text += "*Internal video:* Video download not permitted; sharing TikTok link instead."
        
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": url_text
            }
        })
        
        # Add divider
        blocks.append({"type": "divider"})
        
        return {
            "blocks": blocks,
            "text": f"New TikTok video from @{author}"  # Fallback text
        }
    
    def _send_webhook(self, message: Dict) -> bool:
        """
        Send message via Slack webhook
        
        Args:
            message: Formatted message payload
            
        Returns:
            True if successful
        """
        try:
            response = requests.post(
                self.webhook_url,
                json=message,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                print("✓ Slack notification sent via webhook")
                return True
            else:
                print(f"✗ Slack webhook failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"✗ Error sending Slack webhook: {e}")
            return False
    
    def _send_bot_message(self, message: Dict) -> bool:
        """
        Send message via Slack Bot API
        
        Args:
            message: Formatted message payload
            
        Returns:
            True if successful
        """
        try:
            url = "https://slack.com/api/chat.postMessage"
            
            payload = {
                "channel": self.channel_id,
                **message
            }
            
            response = requests.post(
                url,
                json=payload,
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {self.bot_token}'
                }
            )
            
            result = response.json()
            
            if result.get('ok'):
                print("✓ Slack notification sent via bot")
                return True
            else:
                print(f"✗ Slack bot failed: {result.get('error')}")
                return False
                
        except Exception as e:
            print(f"✗ Error sending Slack message: {e}")
            return False
    
    def is_configured(self) -> bool:
        """
        Check if Slack is properly configured
        
        Returns:
            True if webhook or bot token is set
        """
        return bool(self.webhook_url or (self.bot_token and self.channel_id))


def main():
    """Test Slack notification"""
    notifier = SlackNotifier()
    
    if not notifier.is_configured():
        print("Slack not configured. Set SLACK_WEBHOOK_URL or SLACK_BOT_TOKEN + SLACK_CHANNEL_ID")
        return
    
    # Send test notification
    success = notifier.send_new_video_alert(
        author="danieljensen",
        published_at="2026-02-06T10:30:00Z",
        caption="Check out this amazing content! #fyp #viral",
        transcript="This is a sample transcript of the video content...",
        tiktok_url="https://www.tiktok.com/@danieljensen/video/1234567890",
        storage_url="https://drive.google.com/file/d/sample123/view"
    )
    
    print(f"Test notification {'succeeded' if success else 'failed'}")


if __name__ == "__main__":
    main()
