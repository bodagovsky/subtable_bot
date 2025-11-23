"""ChatGPT/OpenAI API client for natural language processing."""
from openai import OpenAI
from config import OPENAI_API_KEY, OPENAI_MODEL, SYSTEM_PROMPT


class ChatGPTClient:
    """Client for interacting with ChatGPT API."""
    
    def __init__(self):
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY not set in environment variables")
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.model = OPENAI_MODEL
        self.system_prompt = SYSTEM_PROMPT
    
    def analyze_message(self, user_message: str, available_commands: list) -> dict:
        """
        Analyze user message and determine if it matches any commands.
        
        Args:
            user_message: The user's message
            available_commands: List of available command names and descriptions
            
        Returns:
            dict with 'command' (command name or None) and 'reasoning' (explanation)
        """
        commands_context = "\n".join([
            f"- {cmd['name']}: {cmd['description']}"
            for cmd in available_commands
        ])
        
        prompt = f"""Available commands:
{commands_context}

User message: "{user_message}"

Analyze the user's message and determine:
1. Does it match any of the available commands?
2. If yes, which command and what parameters are needed?
3. If no, set command to null.

IMPORTANT: Only return a command if you are CERTAIN it matches one of the available commands. 
If the user's request doesn't clearly match any command, return null for the command field.

Respond in JSON format:
{{
    "command": "command_name or null",
    "parameters": {{"param1": "value1"}},
    "reasoning": "brief explanation"
}}"""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.3
            )
            
            import json
            result = json.loads(response.choices[0].message.content)
            return result
            
        except Exception as e:
            return {
                "command": None,
                "parameters": {},
                "reasoning": f"Error analyzing message: {str(e)}"
            }
    
    def generate_clarification(self, user_message: str, available_commands: list) -> str:
        """Generate a clarification message when no command is matched."""
        commands_context = "\n".join([
            f"- {cmd['name']}: {cmd['description']}"
            for cmd in available_commands
        ])
        
        prompt = f"""The user sent this message: "{user_message}"

Available commands:
{commands_context}

I couldn't match the user's request to any of the available commands. 
Generate a helpful clarification message that:
1. Politely explains that you couldn't understand their request
2. Lists the available commands they can use
3. Asks them to rephrase their request or choose a specific command

Keep the message friendly and concise."""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"I couldn't understand your request. Please try rephrasing it or mention one of the available commands."
    
    def extract_time_window(self, user_message: str) -> dict:
        """
        Extract time window from user message.
        
        Args:
            user_message: The user's message containing time window information
            
        Returns:
            dict with 'time_window_hours' (float or None) and 'success' (bool)
        """
        prompt = f"""Extract the time window from this user message: "{user_message}"

The user is asking about activity within a specific time period. Extract the time window and convert it to hours.

Examples:
- "last day" or "past day" = 24 hours
- "last 2 days" = 48 hours
- "last week" = 168 hours
- "last 3 hours" = 3 hours
- "past 12 hours" = 12 hours
- "yesterday" = 24 hours
- "last 5 days" = 120 hours

IMPORTANT:
- Maximum allowed is 1 week (168 hours)
- Return null if you cannot extract a valid time window
- Return the time in hours as a number

Respond in JSON format:
{{
    "time_window_hours": <number in hours or null>,
    "success": <true or false>,
    "reasoning": "brief explanation"
}}"""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.3
            )
            
            import json
            result = json.loads(response.choices[0].message.content)
            
            # Validate the result
            time_window = result.get("time_window_hours")
            if time_window is not None:
                try:
                    time_window = float(time_window)
                    # Validate max 1 week
                    if time_window > 168:
                        return {
                            "time_window_hours": None,
                            "success": False,
                            "reasoning": "Time window exceeds 1 week maximum"
                        }
                    if time_window <= 0:
                        return {
                            "time_window_hours": None,
                            "success": False,
                            "reasoning": "Time window must be positive"
                        }
                    result["time_window_hours"] = time_window
                    result["success"] = True
                except (ValueError, TypeError):
                    result["success"] = False
                    result["time_window_hours"] = None
            else:
                result["success"] = False
            
            return result
            
        except Exception as e:
            return {
                "time_window_hours": None,
                "success": False,
                "reasoning": f"Error extracting time window: {str(e)}"
            }
    
    def generate_response(self, user_message: str) -> str:
        """Generate a conversational response when no command is matched."""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.7
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Sorry, I encountered an error: {str(e)}"

