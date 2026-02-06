#!/usr/bin/env python3
"""
State Store for TikTok Monitoring
Tracks processed posts to ensure idempotency
"""

import sqlite3
import json
from datetime import datetime
from typing import Optional, Dict, List
import os


class StateStore:
    """SQLite-based state store for tracking processed TikTok posts"""
    
    def __init__(self, db_path: str = "tiktok_state.db"):
        """
        Initialize the state store
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize the database schema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processed_posts (
                post_id TEXT PRIMARY KEY,
                author TEXT NOT NULL,
                published_at TEXT NOT NULL,
                url TEXT NOT NULL,
                caption TEXT,
                transcript TEXT,
                hashtags TEXT,
                storage_url TEXT,
                processed_at TEXT NOT NULL,
                slack_sent BOOLEAN DEFAULT 0
            )
        """)
        
        # Create index for faster lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_author_published 
            ON processed_posts(author, published_at DESC)
        """)
        
        conn.commit()
        conn.close()
    
    def is_processed(self, post_id: str) -> bool:
        """
        Check if a post has already been processed
        
        Args:
            post_id: TikTok post ID
            
        Returns:
            True if post has been processed, False otherwise
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT 1 FROM processed_posts WHERE post_id = ? LIMIT 1",
            (post_id,)
        )
        
        result = cursor.fetchone()
        conn.close()
        
        return result is not None
    
    def add_post(
        self,
        post_id: str,
        author: str,
        published_at: str,
        url: str,
        caption: Optional[str] = None,
        transcript: Optional[str] = None,
        hashtags: Optional[List[str]] = None,
        storage_url: Optional[str] = None
    ) -> bool:
        """
        Add a processed post to the state store
        
        Args:
            post_id: TikTok post ID
            author: TikTok username
            published_at: Publication timestamp
            url: TikTok URL
            caption: Post caption
            transcript: Video transcript/captions
            hashtags: List of hashtags
            storage_url: Internal storage URL (Google Drive)
            
        Returns:
            True if added successfully, False if already exists
        """
        if self.is_processed(post_id):
            return False
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO processed_posts (
                    post_id, author, published_at, url, caption,
                    transcript, hashtags, storage_url, processed_at, slack_sent
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """, (
                post_id,
                author,
                published_at,
                url,
                caption,
                transcript,
                json.dumps(hashtags) if hashtags else None,
                storage_url,
                datetime.utcnow().isoformat()
            ))
            
            conn.commit()
            conn.close()
            return True
            
        except sqlite3.IntegrityError:
            conn.close()
            return False
    
    def mark_slack_sent(self, post_id: str) -> bool:
        """
        Mark that Slack notification was sent for a post
        
        Args:
            post_id: TikTok post ID
            
        Returns:
            True if updated successfully
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "UPDATE processed_posts SET slack_sent = 1 WHERE post_id = ?",
            (post_id,)
        )
        
        updated = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return updated
    
    def get_post(self, post_id: str) -> Optional[Dict]:
        """
        Get post details from state store
        
        Args:
            post_id: TikTok post ID
            
        Returns:
            Dict with post details or None if not found
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT * FROM processed_posts WHERE post_id = ?",
            (post_id,)
        )
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            post = dict(row)
            if post.get('hashtags'):
                post['hashtags'] = json.loads(post['hashtags'])
            return post
        
        return None
    
    def get_recent_posts(self, author: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """
        Get recent processed posts
        
        Args:
            author: Filter by author (optional)
            limit: Maximum number of posts to return
            
        Returns:
            List of post dictionaries
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if author:
            cursor.execute("""
                SELECT * FROM processed_posts 
                WHERE author = ?
                ORDER BY published_at DESC 
                LIMIT ?
            """, (author, limit))
        else:
            cursor.execute("""
                SELECT * FROM processed_posts 
                ORDER BY published_at DESC 
                LIMIT ?
            """, (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        posts = []
        for row in rows:
            post = dict(row)
            if post.get('hashtags'):
                post['hashtags'] = json.loads(post['hashtags'])
            posts.append(post)
        
        return posts
