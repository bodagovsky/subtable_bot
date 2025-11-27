"""Base command class for all bot commands."""
from abc import ABC, abstractmethod
from typing import Optional, Tuple


class BaseCommand(ABC):
    """Base class for all bot commands."""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
    
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
    def execute(self, parameters: dict = None) -> str:
        """
        Execute the command.
        
        Args:
            parameters: Dictionary of parameters for the command
            
        Returns:
            Response message to send to user
        """
        pass
    
    def get_info(self) -> dict:
        """Get command information."""
        return {
            "name": self.name,
            "description": self.description
        }

