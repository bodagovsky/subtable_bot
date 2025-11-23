"""Command handler for managing and executing bot commands."""
from typing import Dict, List
from commands.base import BaseCommand
from commands.example_commands import (
    TimeCommand,
    RandomNumberCommand,
    EchoCommand
)


class CommandHandler:
    """Manages bot commands and their execution."""
    
    def __init__(self):
        self.commands: Dict[str, BaseCommand] = {}
        self._register_default_commands()
    
    def _register_default_commands(self):
        """Register default commands."""
        default_commands = [
            TimeCommand(),
            RandomNumberCommand(),
            EchoCommand()
        ]
        for cmd in default_commands:
            self.register_command(cmd)
    
    def register_command(self, command: BaseCommand):
        """Register a new command."""
        self.commands[command.name] = command
    
    def get_available_commands(self) -> List[dict]:
        """Get list of available commands with descriptions."""
        return [cmd.get_info() for cmd in self.commands.values()]
    
    def execute_command(self, command_name: str, parameters: dict = None) -> str:
        """
        Execute a command by name.
        
        Args:
            command_name: Name of the command to execute
            parameters: Parameters for the command
            
        Returns:
            Response message
        """
        if command_name not in self.commands:
            return f"Command '{command_name}' not found."
        
        try:
            return self.commands[command_name].execute(parameters)
        except Exception as e:
            return f"Error executing command: {str(e)}"

