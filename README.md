# TikTok Monitor 🎬

Automated TikTok monitoring system that detects new videos from monitored accounts, downloads content, stores it in Google Drive, and sends Slack notifications.

## Features

✅ **Automatic Monitoring**: Polls TikTok accounts for new videos via GitHub Actions  
✅ **Avoids duplicates**: Never processes the same post twice using SQLite state store  
✅ **Google Sheets Integration**: Manage monitored accounts from a spreadsheet  
✅ **Google Drive Storage**: Uploads videos to company Google Drive  
✅ **Slack Notifications**: Rich formatted alerts with video details  
✅ **Environment-Aware**: Uses GitHub Secrets in CI, `.env` for local development  
✅ **Comprehensive Logging**: Structured logs for observability  

## Architecture

```
┌─────────────────┐
│ GitHub Actions  │ (Runs every 30 min)
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌──────────────────┐
│   main.py       │────▶│  Google Sheets   │ (Monitored accounts)
│  (Orchestrator) │     └──────────────────┘
└────────┬────────┘
         │
         ├──▶ Apify API (Fetch TikTok stories)
         │
         ├──▶ state_store.py (Idempotency)
         │
         ├──▶ google_drive.py (Upload videos)
         │
         └──▶ slack_notifier.py (Send alerts)
```

## Setup

### 1. Local Development

1. **Clone the repository**
   ```bash
   git clone <repo-url>
   cd TikTok-skraperen
   ```

2. **Create virtual environment**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

5. **Run locally**
   ```bash
   python main.py
   ```

### 2. GitHub Actions Deployment

#### Required GitHub Secrets

Configure these secrets in your repository: `Settings → Secrets and variables → Actions → New repository secret`

| Secret Name | Description | Required |
|-------------|-------------|----------|
| `APIFY_API_TOKEN` | Apify API token ([Get here](https://console.apify.com/account/integrations)) | ✅ |
| `GOOGLE_SHEET_URL` | Google Sheet URL containing monitored accounts | ✅ |
| `GOOGLE_CREDENTIALS_JSON` | Google service account JSON credentials | ✅ |
| `GOOGLE_DRIVE_FOLDER_ID` | Google Drive folder ID for uploads | ✅ |
| `SLACK_WEBHOOK_URL` | Slack incoming webhook URL | ✅ |
| `SLACK_BOT_TOKEN` | Alternative to webhook: Slack bot token | ⚪ |
| `SLACK_CHANNEL_ID` | Required if using bot token | ⚪ |
| `MONITORED_ACCOUNTS` | Fallback: comma-separated usernames | ⚪ |

#### Google Service Account Setup

1. **Create Service Account**
   - Go to [Google Cloud Console](https://console.cloud.google.com/iam-admin/serviceaccounts)
   - Create a new service account
   - Download the JSON key file

2. **Enable APIs**
   - Enable **Google Sheets API**
   - Enable **Google Drive API**

3. **Share Resources**
   - Share your Google Sheet with the service account email (as Viewer)
   - Share your Google Drive folder with the service account email (as Editor)

4. **Add to GitHub Secrets**
   - Copy the entire JSON content and paste as `GOOGLE_CREDENTIALS_JSON`

#### Google Sheet Format

Create a sheet with these columns:

| Username | Notes | Enabled |
|----------|-------|---------|
| danieljensen | Tech content | TRUE |
| hbomax | HBO content | TRUE |
| example_user | Testing | FALSE |

#### Slack Webhook Setup

**Option 1: Webhook (Recommended)**
1. Go to [Slack API](https://api.slack.com/messaging/webhooks)
2. Create a new webhook for your channel
3. Copy the webhook URL to `SLACK_WEBHOOK_URL`

**Option 2: Bot Token**
1. Create app at [Slack API](https://api.slack.com/apps)
2. Add scopes: `chat:write`, `chat:write.public`
3. Install to workspace
4. Copy bot token to `SLACK_BOT_TOKEN`
5. Find channel ID and add to `SLACK_CHANNEL_ID`

### 3. Workflow Configuration

The workflow runs automatically every 30 minutes and can be triggered manually:

```yaml
# .github/workflows/monitor-tiktok.yml
schedule:
  - cron: '*/30 * * * *'  # Every 30 minutes
```

To change the schedule, edit the cron expression:
- `*/15 * * * *` - Every 15 minutes
- `0 * * * *` - Every hour
- `0 */2 * * *` - Every 2 hours

## Components

### state_store.py
SQLite-based state tracking to ensure idempotency. Stores processed posts with metadata.

### google_sheets.py
Fetches monitored accounts from Google Sheets with fallback to environment variables.

### google_drive.py
Uploads TikTok videos to Google Drive and returns shareable links.

### slack_notifier.py
Sends rich formatted notifications to Slack with video details and links.

### main.py
Main orchestration script that ties all components together.

### tiktok_story_downloader.py
Downloads TikTok stories using the Apify API.

## Workflow

1. **Poll**: GitHub Actions triggers every 30 minutes
2. **Fetch Accounts**: Load monitored accounts from Google Sheets
3. **Check TikTok**: For each account, fetch latest stories via Apify
4. **Process New Posts**:
   - Check if post already processed (state store)
   - Download video file
   - Upload to Google Drive
   - Extract caption, transcript, hashtags
   - Save to state store
   - Send Slack notification
5. **Cache State**: Persist state database between runs

## Monitoring

- **Logs**: Check GitHub Actions logs for each run
- **Artifacts**: Download `tiktok_monitor.log` from workflow artifacts
- **Failures**: Automatic Slack alerts on workflow failures
- **State**: SQLite database cached between runs

## Troubleshooting

**No videos found**
- Check that accounts have active stories
- Verify Apify token is valid
- Check Apify quota limits

**Google Drive upload fails**
- Verify service account has Editor access to folder
- Check that Google Drive API is enabled
- Verify credentials JSON is valid

**Slack notifications not sending**
- Test webhook URL manually with curl
- Verify bot token has correct scopes
- Check channel ID is correct

**State not persisting**
- Check GitHub Actions cache is working
- Verify database file path matches cache configuration

## Local Testing

Test individual components:

```bash
# Test Apify connection
python tiktok_story_downloader.py

# Test Google Sheets
python google_sheets.py

# Test Google Drive
python google_drive.py

# Test Slack
python slack_notifier.py

# Run full pipeline
python main.py
```

## Contributing

1. Create feature branch
2. Make changes
3. Test locally
4. Submit pull request

## License

MIT License
