"""MostActiveUser command implementation."""
from .base import BaseCommand
from datetime import datetime, timedelta
from typing import Optional
from telegram import Bot
from collections import Counter
import logging
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from message_storage import message_storage

logger = logging.getLogger(__name__)


class MostActiveUserCommand(BaseCommand):
    """Command to find the most active users in a chat within a time window."""
    
    def __init__(self):
        super().__init__(
            name="most_active_user",
            description="Find the top 3 most active users in the chat within a specified time window (max 1 week)"
        )
    
    def execute(self, parameters: dict = None, bot: Optional[Bot] = None, chat_id: Optional[int] = None) -> str:
        """
        Execute the command.
        
        Args:
            parameters: Dictionary containing 'time_window_hours' (in hours)
            bot: Telegram bot instance for fetching messages
            chat_id: Chat ID to fetch messages from
            
        Returns:
            Response message with top 3 users
        """
        if not bot or not chat_id:
            return "Error: Bot context not available for this command."
        
        params = parameters or {}
        time_window_hours = params.get("time_window_hours")
        
        if not time_window_hours:
            return "Error: Time window not specified."
        
        try:
            time_window_hours = float(time_window_hours)
        except (ValueError, TypeError):
            return "Error: Invalid time window format."
        
        # Validate time window (max 1 week = 168 hours)
        if time_window_hours > 168:
            return "Error: Time window cannot exceed 1 week (168 hours)."
        
        if time_window_hours <= 0:
            return "Error: Time window must be positive."
        
        try:
            # Get user counts from message storage
            user_counts = message_storage.get_user_counts(chat_id, time_window_hours)
            
            if not user_counts:
                return f"No messages found in the last {time_window_hours} hours."
            
            # Get top 3 users
            top_users = Counter(user_counts).most_common(3)
            
            # Format response
            response = f"**Top 3 most active users in the last {time_window_hours} hours:**\n\n"
            
            for i, (user_id, count) in enumerate(top_users, 1):
                try:
                    # Get user info using bot API
                    # Note: This is a synchronous call in python-telegram-bot
                    chat_member = bot.get_chat_member(chat_id, user_id)
                    user = chat_member.user
                    user_name = user.first_name or "Unknown"
                    if user.last_name:
                        user_name += f" {user.last_name}"
                    if user.username:
                        user_name += f" (@{user.username})"
                    response += f"{i}. {user_name}: {count} messages\n"
                except Exception as e:
                    logger.warning(f"Could not get user info for {user_id}: {e}")
                    # If we can't get user info, use user ID
                    response += f"{i}. User {user_id}: {count} messages\n"
            
            return response
            
        except Exception as e:
            logger.error(f"Error in MostActiveUser command: {e}")
            return f"Error executing command: {str(e)}"

