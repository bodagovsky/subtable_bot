"""Message storage for tracking chat messages."""
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import defaultdict
import logging
import pytz

utc=pytz.UTC

logger = logging.getLogger(__name__)


class MessageStorage:
    """In-memory storage for chat messages."""
    
    def __init__(self):
        # Structure: {chat_id: [(timestamp, user_id, message_id), ...]}
        self.messages: Dict[int, List[tuple]] = defaultdict(list)
        # Keep only last 7 days of messages
        self.max_age_days = 7
    
    def add_message(self, chat_id: int, user_id: int, message_id: int, timestamp: datetime):
        """Add a message to storage."""
        # Clean old messages periodically
        self._clean_old_messages(chat_id)
        
        # Add new message
        self.messages[chat_id].append((timestamp, user_id, message_id))
        logger.debug(f"Stored message {message_id} from user {user_id} in chat {chat_id}")
    
    def get_user_counts(self, chat_id: int, time_window_hours: float) -> Dict[int, int]:
        """
        Get message counts per user within time window.
        
        Args:
            chat_id: Chat ID to query
            time_window_hours: Time window in hours
            
        Returns:
            Dictionary mapping user_id to message count
        """
        if chat_id not in self.messages:
            return {}
        
        # Calculate cutoff time
        cutoff_time = datetime.now() - timedelta(hours=time_window_hours)
        
        # Count messages per user
        user_counts = defaultdict(int)
        for timestamp, user_id, _ in self.messages[chat_id]:
            if timestamp >= utc.localize(cutoff_time):
                user_counts[user_id] += 1
        
        return dict(user_counts)
    
    def _clean_old_messages(self, chat_id: int):
        """Remove messages older than max_age_days."""
        if chat_id not in self.messages:
            return
        
        cutoff_time = datetime.now() - timedelta(days=self.max_age_days)
        self.messages[chat_id] = [
            (ts, uid, mid) for ts, uid, mid in self.messages[chat_id]
            if ts >= utc.localize(cutoff_time)
        ]


# Global message storage instance
message_storage = MessageStorage()

