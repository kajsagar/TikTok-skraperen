#!/usr/bin/env python3
"""
Google Drive Integration
Uploads TikTok videos to company Google Drive storage
"""

import os
import json
from typing import Optional


class GoogleDriveUploader:
    """Uploads files to Google Drive"""
    
    def __init__(self, credentials_json: str = None, folder_id: str = None):
        """
        Initialize Google Drive uploader
        
        Args:
            credentials_json: Google service account credentials (JSON string)
            folder_id: Google Drive folder ID where files will be uploaded
        """
        self.credentials_json = credentials_json or os.getenv("GOOGLE_CREDENTIALS_JSON")
        self.folder_id = folder_id or os.getenv("GOOGLE_DRIVE_FOLDER_ID")
        
        self._service = None
    
    def _init_service(self):
        """Initialize Google Drive API service"""
        if self._service is not None:
            return
        
        try:
            from googleapiclient.discovery import build
            from google.oauth2.service_account import Credentials
            
            # Parse credentials from JSON string
            if isinstance(self.credentials_json, str):
                creds_dict = json.loads(self.credentials_json)
            else:
                creds_dict = self.credentials_json
            
            # Define the scope
            scopes = ['https://www.googleapis.com/auth/drive.file']
            
            # Create credentials
            credentials = Credentials.from_service_account_info(
                creds_dict,
                scopes=scopes
            )
            
            # Build the service
            self._service = build('drive', 'v3', credentials=credentials)
            
        except ImportError:
            raise ImportError(
                "Google Drive dependencies not installed. "
                "Run: pip install google-api-python-client google-auth"
            )
    
    def upload_video(
        self,
        file_path: str,
        filename: Optional[str] = None,
        description: Optional[str] = None
    ) -> Optional[str]:
        """
        Upload a video file to Google Drive
        
        Args:
            file_path: Path to the video file to upload
            filename: Custom filename (optional, uses original if not provided)
            description: File description/metadata
            
        Returns:
            Shareable URL to the uploaded file, or None if upload fails
        """
        if not os.path.exists(file_path):
            print(f"Error: File not found: {file_path}")
            return None
        
        self._init_service()
        
        try:
            from googleapiclient.http import MediaFileUpload
            
            # Prepare file metadata
            file_metadata = {
                'name': filename or os.path.basename(file_path),
            }
            
            # Add description if provided
            if description:
                file_metadata['description'] = description
            
            # Add to folder if specified
            if self.folder_id:
                file_metadata['parents'] = [self.folder_id]
            
            # Determine MIME type
            mime_type = 'video/mp4'
            if file_path.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                mime_type = 'image/jpeg'
            
            # Upload file
            media = MediaFileUpload(
                file_path,
                mimetype=mime_type,
                resumable=True
            )
            
            print(f"Uploading {filename or os.path.basename(file_path)} to Google Drive...")
            
            file = self._service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, webViewLink, webContentLink',
                supportsAllDrives=True
            ).execute()
            
            file_id = file.get('id')
            
            # Make file shareable (anyone with link can view)
            self._service.permissions().create(
                fileId=file_id,
                body={
                    'type': 'anyone',
                    'role': 'reader'
                },
                supportsAllDrives=True
            ).execute()
            
            # Get shareable link
            share_link = file.get('webViewLink') or file.get('webContentLink')
            
            print(f"✓ Uploaded successfully: {share_link}")
            return share_link
            
        except Exception as e:
            print(f"Error uploading to Google Drive: {e}")
            return None
    
    def upload_story(
        self,
        file_path: str,
        username: str,
        story_id: str,
        caption: Optional[str] = None
    ) -> Optional[str]:
        """
        Upload a TikTok story with proper naming and metadata
        
        Args:
            file_path: Path to the video file
            username: TikTok username
            story_id: TikTok story/video ID
            caption: Story caption for description
            
        Returns:
            Shareable URL to the uploaded file
        """
        # Create descriptive filename
        extension = os.path.splitext(file_path)[1]
        filename = f"tiktok_{username}_{story_id}{extension}"
        
        # Create description
        description = f"TikTok video from @{username}"
        if caption:
            description += f"\n\n{caption}"
        
        return self.upload_video(
            file_path=file_path,
            filename=filename,
            description=description
        )
    
    def is_configured(self) -> bool:
        """
        Check if Google Drive is properly configured
        
        Returns:
            True if credentials and folder are set
        """
        return bool(self.credentials_json and self.folder_id)


def main():
    """Test Google Drive upload"""
    uploader = GoogleDriveUploader()
    
    if not uploader.is_configured():
        print("Google Drive not configured. Set GOOGLE_CREDENTIALS_JSON and GOOGLE_DRIVE_FOLDER_ID")
        return
    
    # Test with a sample file
    test_file = "tiktok_stories/warnerbros/sample.mp4"
    if os.path.exists(test_file):
        url = uploader.upload_story(
            file_path=test_file,
            username="warnerbros",
            story_id="test123",
            caption="Test upload"
        )
        print(f"Upload result: {url}")
    else:
        print(f"Test file not found: {test_file}")


if __name__ == "__main__":
    main()
