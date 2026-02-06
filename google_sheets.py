#!/usr/bin/env python3
"""
Google Sheets Integration
Fetches list of monitored TikTok accounts from Google Sheet
"""

import os
from typing import List, Dict
import json


class GoogleSheetsMonitor:
    """Fetches monitored accounts from Google Sheets"""
    
    def __init__(self, sheet_url: str = None, credentials_json: str = None):
        """
        Initialize Google Sheets monitor
        
        Args:
            sheet_url: Google Sheet URL or ID
            credentials_json: Google service account credentials (JSON string)
        """
        self.sheet_url = sheet_url or os.getenv("GOOGLE_SHEET_URL")
        self.credentials_json = credentials_json or os.getenv("GOOGLE_CREDENTIALS_JSON")
        
        self._client = None
        self._sheet = None
    
    def _init_client(self):
        """Initialize Google Sheets API client"""
        if self._client is not None:
            return
        
        try:
            import gspread
            from google.oauth2.service_account import Credentials
            
            # Parse credentials from JSON string
            if isinstance(self.credentials_json, str):
                creds_dict = json.loads(self.credentials_json)
            else:
                creds_dict = self.credentials_json
            
            # Define the scope
            scopes = [
                'https://www.googleapis.com/auth/spreadsheets.readonly',
                'https://www.googleapis.com/auth/drive.readonly'
            ]
            
            # Create credentials
            credentials = Credentials.from_service_account_info(
                creds_dict,
                scopes=scopes
            )
            
            # Create client
            self._client = gspread.authorize(credentials)
            
        except ImportError:
            raise ImportError(
                "Google Sheets dependencies not installed. "
                "Run: pip install gspread google-auth"
            )
    
    def get_monitored_accounts(self) -> List[Dict[str, str]]:
        """
        Fetch list of monitored TikTok accounts from Google Sheet
        
        Expected sheet format:
        | Username | Notes | Enabled |
        |----------|-------|---------|
        | user1    | ...   | TRUE    |
        | user2    | ...   | FALSE   |
        
        Returns:
            List of account dictionaries with 'username' and 'enabled' keys
        """
        self._init_client()
        
        try:
            # Open the sheet by URL or key
            if self.sheet_url.startswith('http'):
                self._sheet = self._client.open_by_url(self.sheet_url)
            else:
                self._sheet = self._client.open_by_key(self.sheet_url)
            
            # Get first worksheet
            worksheet = self._sheet.get_worksheet(0)
            
            # Get all records as dictionaries
            records = worksheet.get_all_records()
            
            # Filter and format accounts
            accounts = []
            for record in records:
                username = record.get('Username', '').strip()
                enabled = str(record.get('Enabled', 'TRUE')).upper() == 'TRUE'
                notes = record.get('Notes', '')
                
                if username and enabled:
                    accounts.append({
                        'username': username,
                        'notes': notes
                    })
            
            return accounts
            
        except Exception as e:
            print(f"Error fetching accounts from Google Sheets: {e}")
            # Fallback to hardcoded list if Sheets unavailable
            return self._get_fallback_accounts()
    
    def _get_fallback_accounts(self) -> List[Dict[str, str]]:
        """
        Fallback accounts when Google Sheets is unavailable
        
        Returns:
            List of default accounts
        """
        # Try to get from environment variable
        accounts_env = os.getenv('MONITORED_ACCOUNTS', '')
        if accounts_env:
            usernames = [u.strip() for u in accounts_env.split(',') if u.strip()]
            return [{'username': u, 'notes': ''} for u in usernames]
        
        # Default fallback
        return [{'username': 'danieljensen', 'notes': 'Default account'}]


def main():
    """Test Google Sheets integration"""
    monitor = GoogleSheetsMonitor()
    
    print("Fetching monitored accounts...")
    accounts = monitor.get_monitored_accounts()
    
    print(f"\nFound {len(accounts)} accounts to monitor:")
    for account in accounts:
        print(f"  - @{account['username']}")
        if account.get('notes'):
            print(f"    Notes: {account['notes']}")


if __name__ == "__main__":
    main()
