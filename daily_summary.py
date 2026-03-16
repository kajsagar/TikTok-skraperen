#!/usr/bin/env python3
"""
Daily Summary Script
Sends a Slack digest of all new TikTok stories found the past 24 hours.
Triggered by a separate GitHub Actions workflow at 08:00 every morning.
"""

import os
import sys
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv

from state_store import StateStore
from slack_notifier import SlackNotifier

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


def main():
    load_dotenv()

    state_store = StateStore(db_path=os.getenv("STATE_DB_PATH", "tiktok_state.db"))
    slack = SlackNotifier()

    if not slack.is_configured():
        logger.error("Slack is not configured. Set SLACK_WEBHOOK_URL or SLACK_BOT_TOKEN + SLACK_CHANNEL_ID.")
        sys.exit(1)

    # Fetch everything processed in the last 24 hours
    since = datetime.utcnow() - timedelta(hours=24)
    logger.info(f"Fetching posts processed since {since.isoformat()} UTC")

    posts = state_store.get_posts_since(since)
    logger.info(f"Found {len(posts)} new posts to summarise")

    if not posts:
        logger.info("Nothing new – no summary sent.")
        return

    success = slack.send_daily_summary(posts)

    if success:
        logger.info("✓ Daily summary sent to Slack")
    else:
        logger.error("✗ Failed to send daily summary")
        sys.exit(1)


if __name__ == "__main__":
    main()
