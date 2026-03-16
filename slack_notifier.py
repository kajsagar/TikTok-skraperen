#!/usr/bin/env python3
"""
Slack Notification Module
Sends formatted alerts about new TikTok videos to Slack
"""

import os
import json
from datetime import datetime
from typing import Optional, Dict, List
import requests


class SlackNotifier:
    """Sends notifications to Slack via webhook or bot token"""
    
    def __init__(self, webhook_url: str = None, bot_token: str = None, channel_id: str = None):
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
        message = self._format_message(
            author=author,
            published_at=published_at,
            caption=caption,
            transcript=transcript,
            tiktok_url=tiktok_url,
            storage_url=storage_url
        )
        if self.webhook_url:
            return self._send_webhook(message)
        elif self.bot_token and self.channel_id:
            return self._send_bot_message(message)
        else:
            print("Error: No Slack configuration found (webhook or bot token)")
            return False

    def send_daily_summary(self, posts: List[Dict]) -> bool:
        """
        Send a daily digest of all new TikTok stories found the past 24 hours.
        Groups stories by author and shows count + Drive link per user.

        Args:
            posts: List of post dicts from StateStore.get_posts_since()

        Returns:
            True if message was sent successfully
        """
        if not posts:
            print("No new posts – skipping daily summary.")
            return True

        # Group posts by author
        by_author: Dict[str, List[Dict]] = {}
        for post in posts:
            author = post["author"]
            by_author.setdefault(author, []).append(post)

        today = datetime.utcnow().strftime("%-d. %B %Y")
        total = len(posts)
        num_accounts = len(by_author)

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"📋 Daglig TikTok-oppsummering – {today}"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"Siste 24 timer ble det funnet *{total} nye {'story' if total == 1 else 'stories'}* "
                        f"fra *{num_accounts} {'bruker' if num_accounts == 1 else 'brukere'}*."
                    )
                }
            },
            {"type": "divider"}
        ]

        # One section per author
        for author, author_posts in sorted(by_author.items()):
            count = len(author_posts)

            # Prefer the Drive folder link stored on the first post that has one,
            # otherwise fall back to a TikTok profile link.
            drive_url = next(
                (p["storage_url"] for p in author_posts if p.get("storage_url")),
                None
            )
            tiktok_profile = f"https://www.tiktok.com/@{author}"

            if drive_url:
                link_text = f"<{drive_url}|Åpne Drive-mappe> · <{tiktok_profile}|TikTok-profil>"
            else:
                link_text = f"<{tiktok_profile}|TikTok-profil> _(ingen Drive-lenke tilgjengelig)_"

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*@{author}*\n"
                        f"{count} ny{'' if count == 1 else 'e'} {'story' if count == 1 else 'stories'}\n"
                        f"{link_text}"
                    )
                }
            })

        blocks.append({"type": "divider"})
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "Denne meldingen sendes automatisk kl. 08:00 hver dag av TikTok-skraperen."
                }
            ]
        })

        message = {
            "blocks": blocks,
            "text": f"Daglig TikTok-oppsummering: {total} nye stories fra {num_accounts} brukere"
        }

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
        transcript_text = "Not available"
        if transcript:
            transcript_text = transcript[:500]
            if len(transcript) > 500:
                transcript_text += "..."
        
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
        
        if caption:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Caption:*\n{caption}"
                }
            })

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Transcript:*\n{transcript_text}"
            }
        })

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
        blocks.append({"type": "divider"})

        return {
            "blocks": blocks,
            "text": f"New TikTok video from @{author}"
        }

    def _send_webhook(self, message: Dict) -> bool:
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
        try:
            url = "https://slack.com/api/chat.postMessage"
            payload = {"channel": self.channel_id, **message}
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
        return bool(self.webhook_url or (self.bot_token and self.channel_id))
