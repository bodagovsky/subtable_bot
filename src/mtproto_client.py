"""MTProto client for Telegram API using Telethon."""
import os
import logging
from typing import List, Optional
from telethon import TelegramClient
from telethon.tl.types import Message
from telethon.errors import MessageIdInvalidError, ChannelInvalidError, ChatInvalidError
from config import TELEGRAM_BOT_TOKEN

logger = logging.getLogger(__name__)


class MTProtoClient:
    """MTProto client wrapper using Telethon for Telegram API calls."""
    
    def __init__(self):
        """Initialize MTProto client with credentials from environment variables."""
        # Get Telethon credentials from environment variables
        api_id = os.getenv("TELEGRAM_API_ID", "")
        api_hash = os.getenv("TELEGRAM_API_HASH", "")
        
        if not api_id or not api_hash:
            raise ValueError(
                "TELEGRAM_API_ID and TELEGRAM_API_HASH must be set in environment variables. "
                "Get them from https://my.telegram.org/apps"
            )
        
        try:
            api_id = int(api_id)
        except (ValueError, TypeError):
            raise ValueError("TELEGRAM_API_ID must be a valid integer")
        
        # Use bot token if available, otherwise will need phone number for user account
        # For bot accounts, we can use the bot token
        session_name = "bot_session"
        
        # Initialize Telethon client
        # For bot accounts, we can use bot token authentication
        self.client = TelegramClient(session_name, api_id, api_hash)
        
        # Store bot token for bot authentication
        self.bot_token = TELEGRAM_BOT_TOKEN if TELEGRAM_BOT_TOKEN else None
        
        logger.info("MTProto client initialized")
    
    async def start(self):
        """Start the Telethon client."""
        try:
            await self.client.start(bot_token=self.bot_token)
            logger.info("MTProto client started successfully")
        except Exception as e:
            logger.error(f"Failed to start MTProto client: {e}")
            raise
    
    async def stop(self):
        """Stop the Telethon client."""
        try:
            await self.client.disconnect()
            logger.info("MTProto client stopped")
        except Exception as e:
            logger.error(f"Error stopping MTProto client: {e}")
    
    async def get_messages(
        self, 
        chat_id: int, 
        message_ids: List[int]
    ) -> List[Optional[Message]]:
        """
        Get messages by their IDs from a chat.
        
        Args:
            chat_id: Chat/channel ID (can be negative for groups/channels)
            message_ids: List of message IDs to retrieve
            
        Returns:
            List of Message objects (None for messages that couldn't be retrieved)
        """
        if not message_ids:
            return []
        
        try:
            # Ensure client is connected
            if not self.client.is_connected():
                await self.start()
            
            # Get messages using get_messages
            # Telethon's get_messages can handle multiple message IDs at once
            messages = await self.client.get_messages(chat_id, ids=message_ids)
            
            # Telethon returns a list when multiple IDs are provided, or a single Message for one ID
            # Normalize to list
            if not isinstance(messages, list):
                messages = [messages] if messages else []
            
            # Create a dictionary mapping message ID to Message object
            # This preserves the order of requested message IDs
            message_dict = {}
            for msg in messages:
                if msg is not None and hasattr(msg, 'id'):
                    message_dict[msg.id] = msg
            
            # Build result list maintaining the order of requested message IDs
            result = []
            for msg_id in message_ids:
                result.append(message_dict.get(msg_id))
            
            logger.debug(f"Retrieved {len([m for m in result if m is not None])} out of {len(message_ids)} messages from chat {chat_id}")
            return result
            
        except (MessageIdInvalidError, ChannelInvalidError, ChatInvalidError) as e:
            logger.warning(f"Error getting messages: {e}")
            # Return list of None values for all requested message IDs
            return [None] * len(message_ids)
        except Exception as e:
            logger.error(f"Unexpected error getting messages: {e}")
            # Return list of None values for all requested message IDs
            return [None] * len(message_ids)
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop()


# Global MTProto client instance (lazy initialization)
_mtproto_client: Optional[MTProtoClient] = None


def get_mtproto_client() -> MTProtoClient:
    """
    Get or create the global MTProto client instance.
    
    Returns:
        MTProtoClient instance
    """
    global _mtproto_client
    if _mtproto_client is None:
        _mtproto_client = MTProtoClient()
    return _mtproto_client

