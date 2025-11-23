"""Base command class for all bot commands."""
from abc import ABC, abstractmethod


class BaseCommand(ABC):
    """Base class for all bot commands."""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
    
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

