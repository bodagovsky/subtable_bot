"""Breakdown topic command implementation."""
from .base import BaseCommand
from typing import Optional, List, Dict
from telegram import Bot
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from redis_client import redis_client
from chatgpt_client import ChatGPTClient
from config import COMMAND_PROBABILITY_HIGH_THRESHOLD, COMMAND_PROBABILITY_LOW_THRESHOLD

logger = logging.getLogger(__name__)


class BreakdownTopicCommand(BaseCommand):
    """Command to breakdown a specific topic."""
    
    def __init__(self):
        super().__init__(
            name="breakdown_topic",
            description="Разобрать подробно конкретную тему обсуждения"
        )
        self.chatgpt = ChatGPTClient()
    
    def validate_parameters(self, parameters: Dict = None) -> tuple[bool, str | None]:
        """Validate that topic query is provided.
        
        Note: This method allows missing topic_query - extraction will happen in execute() if user_message is provided.
        """
        params = parameters or {}
        topic_query = params.get("topic_query")
        
        # Allow missing topic_query - it will be extracted in execute() if user_message is provided
        # Only validate if topic_query is explicitly provided
        if topic_query is not None:
            topic_query = str(topic_query).strip()
            if not topic_query:
                return False, "Пожалуйста, укажите тему, которую вы хотите разобрать (например, 'загрязнение воздуха' или 'политика')."
        
        return True, None
    
    async def execute(
        self, 
        parameters: Dict = None, 
        bot: Optional[Bot] = None, 
        chat_id: Optional[int] = None,
        user_message: Optional[str] = None
    ) -> str:
        """
        Execute the breakdown_topic command.
        
        Args:
            parameters: Dictionary with 'topic_query' (str)
            bot: Telegram bot instance
            chat_id: Chat ID
            user_message: Original user message (for parameter extraction if needed)
            
        Returns:
            Response message with topic breakdown or topic selection
        """
        if not chat_id:
            return "Прошу прощения, сэр/мадам, но контекст чата недоступен для этой команды."
        
        params = parameters or {}
        topic_query = params.get("topic_query", "").strip()
        
        # Step 1: If topic_query is not provided, try to extract from user_message using OpenAI
        if not topic_query and user_message:
            logger.info(f"Attempting to extract topic_query from user message: {user_message}")
            extraction_result = self.chatgpt.extract_topic_query(user_message)
            
            if extraction_result.get("success") and extraction_result.get("topic_query"):
                # Topic query extracted successfully
                topic_query = extraction_result["topic_query"]
                params["topic_query"] = topic_query
                logger.info(f"Extracted topic_query: {topic_query}")
            else:
                # Extraction failed - ask user to provide explicitly
                reasoning = extraction_result.get("reasoning", "Не удалось определить тему")
                logger.info(f"Topic query extraction failed: {reasoning}")
                return (
                    "Прошу прощения, сэр/мадам. Я не смог определить тему из вашего сообщения.\n\n"
                    "Пожалуйста, укажите явно тему, которую вы хотите разобрать (например, 'загрязнение воздуха', 'политика', 'новости')."
                )
        
        if not topic_query:
            return "Прошу прощения, сэр/мадам, но вы не указали тему. Пожалуйста, укажите тему, которую вы хотите разобрать."
        
        try:
            # Get all topic keys for this channel
            topic_handles = redis_client.get_all_topic_keys(chat_id)
            
            if not topic_handles:
                return "Прошу прощения, сэр/мадам, но сегодня не было обсуждений, которые можно разобрать."
            
            # Load all topics from Redis
            topics = []
            for topic_handle in topic_handles:
                topic_data = redis_client.get_topic_summary(chat_id, topic_handle)
                if topic_data:
                    topics.append(topic_data)
            
            if not topics:
                return "Прошу прощения, сэр/мадам, но не удалось загрузить темы обсуждения."
            
            # Match user query to topics using OpenAI
            match_result = self.chatgpt.match_topic(topic_query, topics)
            matched_topics = match_result.get("topics", [])
            
            # Filter by probability thresholds
            high_prob_topics = [
                t for t in matched_topics 
                if t.get("probability", 0) >= COMMAND_PROBABILITY_HIGH_THRESHOLD
            ]
            low_prob_topics = [
                t for t in matched_topics 
                if COMMAND_PROBABILITY_LOW_THRESHOLD <= t.get("probability", 0) < COMMAND_PROBABILITY_HIGH_THRESHOLD
            ]
            
            # If single high probability topic, show breakdown
            if len(high_prob_topics) == 1:
                topic = high_prob_topics[0]
                return self._format_topic_breakdown(topic, chat_id)
            
            # If multiple high probability topics, ask user to choose
            if len(high_prob_topics) > 1:
                return self._format_topic_selection(high_prob_topics, chat_id)
            
            # If some low probability topics, ask user to choose
            if low_prob_topics:
                return self._format_topic_selection(low_prob_topics, chat_id)
            
            # No matching topics
            return "Прошу прощения, сэр/мадам, но сегодня не обсуждались темы, соответствующие вашему запросу."
            
        except Exception as e:
            logger.error(f"Error in BreakdownTopic command: {e}")
            return f"Прошу прощения, сэр/мадам, но произошла ошибка при выполнении команды: {str(e)}"
    
    def _format_topic_breakdown(self, topic: Dict, chat_id: int) -> str:
        """Format topic breakdown response."""
        description = topic.get("description", topic.get("topic_handle", "Тема"))
        summary = topic.get("summary", "")
        start_message_id = topic.get("start_message", {}).get("message_id", 0)
        
        # Build message link
        # Telegram links use channel ID without the -100 prefix for groups/channels
        # For example: -1001234567890 becomes 1234567890 in the link
        link_chat_id = str(abs(chat_id))
        if len(link_chat_id) > 10 and link_chat_id.startswith("100"):
            link_chat_id = link_chat_id[3:]  # Remove -100 prefix for groups/channels
        message_link = f"https://t.me/c/{link_chat_id}/{start_message_id}" if start_message_id else ""
        
        response = f"Конечно, сэр/мадам. Вот что обсуждалось по теме **{description}**:\n\n"
        
        if message_link:
            response += f"[Начало обсуждения]({message_link})\n\n"
        
        # Format summary points
        if summary:
            # Split summary by newlines or numbers
            points = summary.split("\n")
            formatted_points = []
            for point in points:
                point = point.strip()
                if point:
                    # Remove leading numbers if present
                    if point and point[0].isdigit():
                        point = point.split(".", 1)[-1].strip()
                    if point:
                        formatted_points.append(point)
            
            if formatted_points:
                for i, point in enumerate(formatted_points, 1):
                    response += f"{i}. {point}\n"
        
        return response
    
    def _format_topic_selection(self, topics: List[Dict], chat_id: int) -> str:
        """Format topic selection response when multiple topics match."""
        response = "Конечно, сэр/мадам. Найдено несколько тем, соответствующих вашему запросу:\n\n"
        
        for i, topic in enumerate(topics, 1):
            description = topic.get("description", topic.get("topic_handle", "Тема"))
            message_count = topic.get("message_count", 0)
            response += f"{i}. {description} ({message_count} сообщений)\n"
        
        response += "\nКакую тему вы хотите, чтобы я разобрал подробнее?"
        
        return response

