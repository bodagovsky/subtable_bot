"""Silence state management for the bot."""
from typing import Dict, Set
import logging

logger = logging.getLogger(__name__)


class SilenceState:
    """Manages silence state per chat."""
    
    def __init__(self):
        # Set of chat IDs where bot is silenced
        self.silenced_chats: Set[int] = set()
    
    def is_silenced(self, chat_id: int) -> bool:
        """Check if bot is silenced in a chat."""
        return chat_id in self.silenced_chats
    
    def set_silenced(self, chat_id: int, silenced: bool):
        """Set silence state for a chat."""
        if silenced:
            self.silenced_chats.add(chat_id)
            logger.info(f"Bot silenced in chat {chat_id}")
        else:
            self.silenced_chats.discard(chat_id)
            logger.info(f"Bot unsilenced in chat {chat_id}")
    
    def toggle_silence(self, chat_id: int) -> bool:
        """Toggle silence state and return new state (True = silenced, False = unsilenced)."""
        if self.is_silenced(chat_id):
            self.set_silenced(chat_id, False)
            return False
        else:
            self.set_silenced(chat_id, True)
            return True


# Global silence state instance
silence_state = SilenceState()

