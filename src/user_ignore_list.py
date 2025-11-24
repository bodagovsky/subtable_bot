"""User ignore list management."""
from typing import Set
import logging

logger = logging.getLogger(__name__)


class UserIgnoreList:
    """Manages list of users to ignore."""
    
    def __init__(self):
        # Set of user IDs to ignore
        self.ignored_users: Set[int] = set()
    
    def is_ignored(self, user_id: int) -> bool:
        """Check if a user is in the ignore list."""
        return user_id in self.ignored_users
    
    def add_user(self, user_id: int):
        """Add a user to the ignore list."""
        self.ignored_users.add(user_id)
        logger.info(f"User {user_id} added to ignore list")
    
    def remove_user(self, user_id: int):
        """Remove a user from the ignore list."""
        self.ignored_users.discard(user_id)
        logger.info(f"User {user_id} removed from ignore list")
    
    def toggle_user(self, user_id: int) -> bool:
        """Toggle ignore state for a user. Returns True if now ignored, False if not."""
        if self.is_ignored(user_id):
            self.remove_user(user_id)
            return False
        else:
            self.add_user(user_id)
            return True


# Global ignore list instance
user_ignore_list = UserIgnoreList()

