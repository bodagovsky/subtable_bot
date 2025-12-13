"""Base command class for all bot commands."""
from abc import ABC, abstractmethod
from typing import Optional, Tuple
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.state_machine import Event


class BaseCommand(ABC):
    """Base class for all bot commands."""
    
    def __init__(self, name: str, description: str):
        """
        Wether the command requires the user to provide parameters for execution
        """
        self.require_parameters = False
        self.name = name
        self.description = description
        self.parameters = ""

    def requires_parameters(self) -> bool:
        return self.require_parameters

    def human_readable_parameters(self) -> str:
        return self.parameters
    
    def validate_parameters(self, parameters: dict = None) -> Tuple[bool, Optional[str]]:
        """
        Validate command parameters before execution.
        
        Args:
            parameters: Dictionary of parameters to validate
            
        Returns:
            Tuple of (is_valid, error_message)
            - is_valid: True if parameters are valid, False otherwise
            - error_message: Error message if invalid, None if valid
        """
        # Default implementation: all parameters are valid
        # Override in subclasses to add validation
        return True, None
    
    @abstractmethod
    async def execute(
        self, 
        parameters: dict = None, 
        update=None, 
        context=None, 
        chatgpt_client=None
    ) -> Event:
        """
        Execute the command.
        
        Args:
            parameters: Dictionary of parameters for the command
            update: Telegram Update object (for sending messages)
            context: Bot context
            chatgpt_client: ChatGPT client instance
            
        Returns:
            Event enum indicating what happened
        """
        pass
    
    def get_info(self) -> dict:
        """Get command information."""
        return {
            "name": self.name,
            "description": self.description
        }

