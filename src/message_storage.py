"""Message storage for tracking chat messages using Redis."""
from datetime import datetime, timedelta
from typing import Dict
from collections import defaultdict
import logging
import pytz
from redis_client import redis_client

utc = pytz.UTC

logger = logging.getLogger(__name__)


class MessageStorage:
    """Redis-based storage for chat messages."""
    
    def __init__(self):
        """Initialize message storage with Redis backend."""
        self.redis = redis_client
        # Keep only last 7 days of messages (handled automatically in Redis)
        self.max_age_days = 7
    
    def add_message(self, chat_id: int, user_id: int, message_id: int, timestamp: datetime):
        """
        Add a message to Redis storage.
        
        Args:
            chat_id: Chat ID
            user_id: User ID
            message_id: Message ID
            timestamp: Message timestamp
        """
        # Ensure timestamp is timezone-aware (UTC)
        if timestamp.tzinfo is None:
            timestamp = utc.localize(timestamp)
        
        # Append message to Redis (automatically cleans old messages)
        success = self.redis.append_message(chat_id, user_id, message_id, timestamp)
        
        if success:
            logger.debug(f"Stored message {message_id} from user {user_id} in chat {chat_id}")
        else:
            logger.warning(f"Failed to store message {message_id} from user {user_id} in chat {chat_id}")
    
    def get_user_counts(self, chat_id: int, time_window_hours: float) -> Dict[int, int]:
        """
        Get message counts per user within time window from Redis.
        
        Args:
            chat_id: Chat ID to query
            time_window_hours: Time window in hours
            
        Returns:
            Dictionary mapping user_id to message count
        """
        # Calculate cutoff time
        cutoff_time = datetime.now(utc) - timedelta(hours=time_window_hours)
        end_time = datetime.now(utc)
        
        # Get messages from Redis within time range
        messages = self.redis.get_messages_by_time_range(chat_id, cutoff_time, end_time)
        
        # Count messages per user
        user_counts = defaultdict(int)
        for message_value, _ in messages:
            # Parse message value: "{user_id}:{message_id}"
            try:
                user_id_str, _ = message_value.split(":", 1)
                user_id = int(user_id_str)
                user_counts[user_id] += 1
            except (ValueError, TypeError) as e:
                logger.warning(f"Could not parse message value '{message_value}': {e}")
                continue
        
        return dict(user_counts)


# Global message storage instance
message_storage = MessageStorage()

