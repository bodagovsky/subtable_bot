"""Redis client for message storage and other data."""
import os
import redis
from typing import Set, Optional, List, Tuple
from enum import Enum
from datetime import datetime, timedelta
import logging
import json
import secrets
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class RedisType(Enum):
    """Redis data type enumeration."""
    STRING = "string"
    LIST = "list"
    SET = "set"
    ZSET = "zset"  # sorted set
    HASH = "hash"
    STREAM = "stream"


class RedisClient:
    """Redis client wrapper for bot operations."""
    
    def __init__(self):
        """Initialize Redis connection."""
        # Get Redis credentials from environment variables
        redis_url = os.getenv("REDISCLOUD_URL", "")
        redis_password = os.getenv("REDIS_PASSWORD", "")
        redis_port = os.getenv("REDIS_PORT", "")
        redis_username = os.getenv("REDIS_USERNAME", "")
    
        
        # Build connection parameters
        connection_params = {
            "host": redis_url,
            "port": redis_port,
            "decode_responses": True  # Automatically decode responses to strings
        }
        
        if redis_password:
            connection_params["password"] = redis_password
        
        if redis_username:
            connection_params["username"] = redis_username
        
        try:
            self.client = redis.Redis(**connection_params)
            # Test connection
            self.client.ping()
            logger.info(f"Connected to Redis at {redis_url}:{redis_port}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    def build_channel_messages_key(self, channel_id: int) -> str:
        """
        Build Redis key for channel messages.
        
        Args:
            channel_id: Channel/chat ID
            
        Returns:
            Redis key string: "channel:messages:{channel_id}"
        """
        return f"channel:messages:{channel_id}"
    
    def build_topic_key(self, channel_id: int, topic_handle: str) -> str:
        """
        Build Redis key for topic summary.
        
        Args:
            channel_id: Channel/chat ID
            topic_handle: Topic handle (e.g., "air_pollution")
            
        Returns:
            Redis key string: "summarry:channel:{channel_id}:{topic_handle}"
        """
        return f"summarry:channel:{channel_id}:{topic_handle}"

    def build_message_metadata_key(self, chat_id: int, message_id: int) -> str:
        return f"telegram:message:{chat_id}:{message_id}"

    def build_agent_session_key(self, chat_id: int, user_id: int, thread_id: Optional[int]) -> str:
        return f"telegram:agent-session:{chat_id}:{user_id}:{thread_id or 0}"

    def build_agents_api_session_key(self, chat_id: int, thread_id: Optional[int]) -> str:
        """One managed Agents API conversation per Telegram chat topic."""
        return f"telegram:agents-api-session:{chat_id}:{thread_id or 0}"

    def build_agent_delivery_key(self, delivery_id: str) -> str:
        """Key for a short-lived, single-use reply capability."""
        return f"telegram:agent-delivery:{delivery_id}"

    def create_agent_delivery(
        self,
        chat_id: int,
        message_id: int,
        thread_id: Optional[int],
        ttl_seconds: int = 15 * 60,
    ) -> str:
        """Store webhook-derived reply routing data and return an opaque ID.

        The ID is supplied to the agent, while the actual Telegram chat and
        message IDs stay in Redis.  It expires quickly and is consumed by the
        reply tool, so it cannot be used to target another chat or replay a
        completed reply.
        """
        delivery_id = secrets.token_urlsafe(24)
        payload = {
            "chat_id": chat_id,
            "message_id": message_id,
            "thread_id": thread_id,
        }
        self.client.setex(
            self.build_agent_delivery_key(delivery_id),
            ttl_seconds,
            json.dumps(payload, ensure_ascii=False),
        )
        return delivery_id

    def get_agent_delivery(self, delivery_id: str) -> Optional[dict]:
        payload = self.client.get(self.build_agent_delivery_key(delivery_id))
        return json.loads(payload) if payload else None

    def consume_agent_delivery(self, delivery_id: str) -> Optional[dict]:
        """Atomically consume a delivery capability before its side effect."""
        payload = self.client.getdel(self.build_agent_delivery_key(delivery_id))
        return json.loads(payload) if payload else None
    
    def append_message(self, channel_id: int, user_id: int, message_id: int, message_timestamp: datetime) -> bool:
        """
        Append a message to Redis sorted set.
        
        Args:
            channel_id: Channel/chat ID
            user_id: User ID
            message_id: Message ID
            message_timestamp: Message timestamp (datetime object)
            
        Returns:
            True if message is new (successfully added), False if message already exists
        """
        try:
            key = self.build_channel_messages_key(channel_id)
            
            # Convert timestamp to Unix timestamp (score for sorted set)
            unix_timestamp = message_timestamp.timestamp()
            
            # Build message value as "{user_id}:{message_id}"
            message_value = f"{user_id}:{message_id}"
            
            # Add message to sorted set with timestamp as score
            # ZADD returns the number of elements added (1 if new, 0 if already exists)
            # Note: redis-py zadd accepts dict mapping member to score
            # Using nx=True to only add if not exists (idempotency)
            result = self.client.zadd(key, {message_value: unix_timestamp}, nx=True)
            
            # result is 1 if message was added (new), 0 if already exists
            is_new_message = result > 0
            
            if is_new_message:
                logger.debug(f"Stored new message {message_id} from user {user_id} in channel {channel_id}")
            else:
                logger.debug(f"Message {message_id} from user {user_id} in channel {channel_id} already exists")
            
            # Remove messages older than 7 days
            # Calculate cutoff timestamp (7 days ago)
            cutoff_timestamp = (datetime.now() - timedelta(days=7)).timestamp()
            
            # Remove old messages using ZREMRANGEBYSCORE
            # -inf to cutoff_timestamp removes all messages with score <= cutoff_timestamp
            removed_count = self.client.zremrangebyscore(key, "-inf", cutoff_timestamp)
            
            if removed_count > 0:
                logger.debug(f"Removed {removed_count} old messages from channel {channel_id}")
            
            # Return True if message is new, False if already exists
            return is_new_message
            
        except Exception as e:
            logger.error(f"Error appending message to Redis: {e}")
            return False

    def store_message_index(
        self,
        chat_id: int,
        user_id: int,
        message_id: int,
        timestamp: datetime,
        thread_id: Optional[int] = None,
    ) -> bool:
        """Store a compact, expiring message index without copying its text."""
        is_new = self.append_message(chat_id, user_id, message_id, timestamp)
        try:
            key = self.build_message_metadata_key(chat_id, message_id)
            self.client.hset(
                key,
                mapping={
                    "user_id": user_id,
                    "timestamp": timestamp.timestamp(),
                    "thread_id": thread_id or 0,
                },
            )
            self.client.expire(key, 7 * 24 * 60 * 60)
        except Exception as exc:
            logger.error(f"Error storing message metadata: {exc}")
        return is_new

    def get_indexed_messages_by_time_range(
        self,
        chat_id: int,
        start_time: datetime,
        end_time: Optional[datetime] = None,
    ) -> List[Tuple[int, int, float]]:
        """Return (author_id, message_id, timestamp) ordered oldest first."""
        records = self.get_messages_by_time_range(chat_id, start_time, end_time)
        result: List[Tuple[int, int, float]] = []
        for value, timestamp in records:
            try:
                user_id, message_id = (int(part) for part in value.split(":", 1))
                result.append((user_id, message_id, timestamp))
            except (TypeError, ValueError):
                logger.warning(f"Could not parse indexed message {value!r}")
        return result

    def store_reaction_count(self, chat_id: int, message_id: int, total_count: int) -> None:
        """Keep the latest aggregate reaction total for one indexed message."""
        try:
            key = self.build_message_metadata_key(chat_id, message_id)
            if not self.client.exists(key):
                return
            self.client.hset(key, "reaction_count", total_count)
            self.client.expire(key, 7 * 24 * 60 * 60)
        except Exception as exc:
            logger.error(f"Error storing reaction count: {exc}")

    def adjust_reaction_count(self, chat_id: int, message_id: int, delta: int) -> None:
        """Apply a non-anonymous user's reaction change to the local aggregate."""
        try:
            key = self.build_message_metadata_key(chat_id, message_id)
            if not self.client.exists(key):
                return
            current = int(self.client.hget(key, "reaction_count") or 0)
            self.client.hset(key, "reaction_count", max(0, current + delta))
            self.client.expire(key, 7 * 24 * 60 * 60)
        except Exception as exc:
            logger.error(f"Error adjusting reaction count: {exc}")

    def get_top_speakers_by_reactions(
        self,
        chat_id: int,
        start_time: datetime,
        end_time: Optional[datetime] = None,
        limit: int = 3,
    ) -> List[dict]:
        """Rank message authors by reactions received on messages in a period."""
        totals: dict[int, int] = {}
        try:
            for user_id, message_id, _ in self.get_indexed_messages_by_time_range(chat_id, start_time, end_time):
                metadata = self.client.hgetall(self.build_message_metadata_key(chat_id, message_id))
                reactions = int(metadata.get("reaction_count", 0)) if metadata else 0
                totals[user_id] = totals.get(user_id, 0) + reactions
            return [
                {"user_id": user_id, "reaction_count": reactions}
                for user_id, reactions in sorted(totals.items(), key=lambda item: item[1], reverse=True)[:limit]
            ]
        except Exception as exc:
            logger.error(f"Error calculating reaction leaderboard: {exc}")
            return []

    def enqueue_agent_job(self, job: dict) -> None:
        self.client.lpush("telegram:agent-jobs", json.dumps(job, ensure_ascii=False))

    def dequeue_agent_job(self, timeout_seconds: int = 5) -> Optional[dict]:
        item = self.client.brpop("telegram:agent-jobs", timeout=timeout_seconds)
        if not item:
            return None
        _, payload = item
        return json.loads(payload)

    def claim_update(self, update_id: int) -> bool:
        """Return true only on first delivery of a Telegram update."""
        return bool(self.client.set(f"telegram:update:{update_id}", "1", nx=True, ex=24 * 60 * 60))

    def release_update_claim(self, update_id: int) -> None:
        self.client.delete(f"telegram:update:{update_id}")

    def get_agent_response_id(self, chat_id: int, user_id: int, thread_id: Optional[int]) -> Optional[str]:
        return self.client.get(self.build_agent_session_key(chat_id, user_id, thread_id))

    def set_agent_response_id(self, chat_id: int, user_id: int, thread_id: Optional[int], response_id: str) -> None:
        self.client.setex(self.build_agent_session_key(chat_id, user_id, thread_id), 7 * 24 * 60 * 60, response_id)

    def get_agents_api_session_id(self, chat_id: int, thread_id: Optional[int]) -> Optional[str]:
        return self.client.get(self.build_agents_api_session_key(chat_id, thread_id))

    def set_agents_api_session_id(self, chat_id: int, thread_id: Optional[int], session_id: str) -> None:
        self.client.setex(self.build_agents_api_session_key(chat_id, thread_id), 7 * 24 * 60 * 60, session_id)
    
    def get_messages_by_time_range(
        self, 
        channel_id: int, 
        start_time: datetime, 
        end_time: Optional[datetime] = None
    ) -> List[Tuple[str, float]]:
        """
        Get messages from Redis sorted set within a time range using ZRANGE BYSCORE.
        
        Args:
            channel_id: Channel/chat ID
            start_time: Start time (inclusive)
            end_time: End time (inclusive). If None, uses current time.
            
        Returns:
            List of tuples (message_value, score) where message_value is "{user_id}:{message_id}"
            and score is the Unix timestamp
        """
        try:
            key = self.build_channel_messages_key(channel_id)
            
            # Convert timestamps to Unix timestamps
            start_timestamp = start_time.timestamp()
            end_timestamp = end_time.timestamp() if end_time else datetime.now().timestamp()
            
            # Use ZRANGEBYSCORE to get messages in time range
            # WITHSCORES returns both values and scores
            messages = self.client.zrangebyscore(key, start_timestamp, end_timestamp, withscores=True)
            
            # Convert to list of tuples (value, score)
            # messages is a list of tuples from Redis: [(value, score), ...]
            return [(msg[0], msg[1]) for msg in messages]
            
        except Exception as e:
            logger.error(f"Error getting messages from Redis: {e}")
            return []
    
    def get_messages_by_count(
        self, 
        channel_id: int, 
        count: int
    ) -> List[Tuple[str, float]]:
        """
        Get last N messages from Redis sorted set using ZRANGE with REV.
        
        Args:
            channel_id: Channel/chat ID
            count: Number of messages to retrieve
            
        Returns:
            List of tuples (message_value, score) where message_value is "{user_id}:{message_id}"
            and score is the Unix timestamp, ordered from newest to oldest
        """
        try:
            key = self.build_channel_messages_key(channel_id)
            
            # Use ZRANGE with REV to get last N messages (newest first)
            # REV reverses the order, so we get the highest scores (newest) first
            # WITHSCORES returns both values and scores
            messages = self.client.zrange(key, 0, count - 1, desc=True, withscores=True)
            
            # Convert to list of tuples (value, score)
            return [(msg[0], msg[1]) for msg in messages]
            
        except Exception as e:
            logger.error(f"Error getting messages by count from Redis: {e}")
            return []
    
    def cache_topic_summary(self, channel_id: int, topic_handle: str, topic_data: dict) -> bool:
        """
        Cache topic summary in Redis.
        
        Args:
            channel_id: Channel/chat ID
            topic_handle: Topic handle (e.g., "air_pollution")
            topic_data: Dictionary containing topic summary data
            
        Returns:
            True if successful, False otherwise
        """
        try:
            key = self.build_topic_key(channel_id, topic_handle)
            
            # Store topic data as JSON string
            import json
            topic_json = json.dumps(topic_data, ensure_ascii=False)
            
            # Use SET to store the topic summary
            self.client.set(key, topic_json)
            
            logger.debug(f"Cached topic summary: {key}")
            return True
            
        except Exception as e:
            logger.error(f"Error caching topic summary: {e}")
            return False
    
    def get_topic_summary(self, channel_id: int, topic_handle: str) -> Optional[dict]:
        """
        Get topic summary from Redis cache.
        
        Args:
            channel_id: Channel/chat ID
            topic_handle: Topic handle (e.g., "air_pollution")
            
        Returns:
            Dictionary with topic summary data, or None if not found
        """
        try:
            key = self.build_topic_key(channel_id, topic_handle)
            
            # Get topic data from Redis
            topic_json = self.client.get(key)
            
            if topic_json is None:
                return None
            
            # Parse JSON
            import json
            return json.loads(topic_json)
            
        except Exception as e:
            logger.error(f"Error getting topic summary: {e}")
            return None
    
    def get_all_topic_keys(self, channel_id: int) -> List[str]:
        """
        Get all topic keys for a channel.
        
        Args:
            channel_id: Channel/chat ID
            
        Returns:
            List of topic handles (without full key prefix)
        """
        try:
            # Use SCAN to find all topic keys for this channel
            namespace = f"summarry:channel:{channel_id}:*"
            keys = self.get_all_keys(namespace)
            
            # Extract topic handles from keys
            prefix = f"summarry:channel:{channel_id}:"
            topic_handles = [key.replace(prefix, "") for key in keys if key.startswith(prefix)]
            
            return topic_handles
            
        except Exception as e:
            logger.error(f"Error getting topic keys: {e}")
            return []
    
    def get_all_keys(
        self, 
        namespace: str, 
        redis_type: Optional[RedisType] = None
    ) -> Set[str]:
        """
        Get all keys matching a namespace pattern using SCAN.
        
        Args:
            namespace: Namespace pattern (e.g., "channel:messages:*")
            redis_type: Optional Redis type filter (RedisType enum)
            
        Returns:
            Set of matching keys
        """
        try:
            keys = set()
            cursor = 0
            
            # Use SCAN to iterate through all matching keys
            while True:
                # SCAN with MATCH pattern
                cursor, batch = self.client.scan(cursor, match=namespace, count=100)
                
                # If type filter is specified, filter by type
                if redis_type:
                    filtered_batch = []
                    for key in batch:
                        # Get key type and compare
                        key_type = self.client.type(key)
                        # Handle both string and bytes responses
                        if isinstance(key_type, bytes):
                            key_type = key_type.decode('utf-8')
                        if key_type == redis_type.value:
                            filtered_batch.append(key)
                    batch = filtered_batch
                
                keys.update(batch)
                
                if cursor == 0:
                    break
            
            return keys
            
        except Exception as e:
            logger.error(f"Error getting keys from Redis: {e}")
            return set()
    
    def set_bot_silenced(self, channel_id: int, user_id: int) -> bool:
        """
        Set bot as silenced for a channel. Only the user who silenced can unsilence.
        
        Args:
            channel_id: Channel/chat ID
            user_id: User ID who silenced the bot
            
        Returns:
            True if successful, False otherwise
        """
        try:
            key = f"bot:silenced:{channel_id}"
            # Store user_id who silenced the bot, with 1 hour TTL
            self.client.setex(key, 3600, str(user_id))  # 3600 seconds = 1 hour
            logger.info(f"Bot silenced in channel {channel_id} by user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Error setting bot silenced: {e}")
            return False
    
    def is_bot_silenced(self, channel_id: int) -> bool:
        """
        Check if bot is silenced for a channel.
        
        Args:
            channel_id: Channel/chat ID
            
        Returns:
            True if silenced, False otherwise
        """
        try:
            key = f"bot:silenced:{channel_id}"
            return self.client.exists(key) > 0
        except Exception as e:
            logger.error(f"Error checking bot silenced: {e}")
            return False
    
    def get_silence_user_id(self, channel_id: int) -> Optional[int]:
        """
        Get the user ID who silenced the bot for a channel.
        
        Args:
            channel_id: Channel/chat ID
            
        Returns:
            User ID if silenced, None otherwise
        """
        try:
            key = f"bot:silenced:{channel_id}"
            user_id_str = self.client.get(key)
            if user_id_str:
                return int(user_id_str)
            return None
        except Exception as e:
            logger.error(f"Error getting silence user ID: {e}")
            return None
    
    def unsilence_bot(self, channel_id: int) -> bool:
        """
        Unsilence the bot for a channel.
        
        Args:
            channel_id: Channel/chat ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            key = f"bot:silenced:{channel_id}"
            result = self.client.delete(key)
            logger.info(f"Bot unsilenced in channel {channel_id}")
            return result > 0
        except Exception as e:
            logger.error(f"Error unsilencing bot: {e}")
            return False
    
    def get_air_report_channels(self) -> List[int]:
        """
        Retrieve channel ids to report about the air quality

        Returns:
            List of channels ids
        """

        try:
            key = "channel:air_report"
            return [int(result) for result in self.client.sscan_iter(key)]
        except Exception as e:
            logger.error(e)
            return []

# Global Redis client instance
redis_client = RedisClient()
