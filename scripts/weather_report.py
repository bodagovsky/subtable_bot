#!/usr/bin/env python3
"""Script to fetch air quality data and send weather reports to Telegram channels."""
import sys
import os

# Add src directory to path for imports (must be before local imports)
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)
src_dir = os.path.join(parent_dir, 'src')
sys.path.insert(0, src_dir)

import asyncio
import logging
from typing import Optional, Dict, Any
from dotenv import load_dotenv
import requests

from config import IQAIR_API_KEY
from mtproto_client import get_mtproto_client
from chatgpt_client import ChatGPTClient
from redis_client import RedisClient

# Load environment variables first
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class IQAirClient:
    """Client for interacting with IQAir API to fetch air quality data."""
    
    BASE_URL = "http://api.airvisual.com/v2/city"
    
    def __init__(
        self,
        city: str = "Yerevan",
        state: str = "Yerevan",
        country: str = "Armenia",
        api_key: Optional[str] = None
    ) -> None:
        """
        Initialize IQAir client.
        
        Args:
            city: City name (default: "Yerevan")
            state: State/region name (default: "Yerevan")
            country: Country name (default: "Armenia")
            api_key: IQAir API key (defaults to IQAIR_API_KEY from config)
        """
        if not api_key:
            api_key = IQAIR_API_KEY
        
        if not api_key:
            raise ValueError("IQAir API key is required. Set IQAIR_API_KEY environment variable.")
        
        self.city = city
        self.state = state
        self.country = country
        self.api_key = api_key
        self._build_url()
    
    def _build_url(self) -> None:
        """Build the API URL with query parameters."""
        self.url = (
            f"{self.BASE_URL}?"
            f"city={self.city}&"
            f"state={self.state}&"
            f"country={self.country}&"
            f"key={self.api_key}"
        )
    
    def get_raw_report(self) -> Dict[str, Any]:
        """
        Fetch raw air quality report from IQAir API.
        
        Returns:
            Dictionary containing the API response
            
        Raises:
            requests.RequestException: If the API request fails
            ValueError: If the API response is invalid
        """
        try:
            logger.info(f"Fetching air quality data for {self.city}, {self.state}, {self.country}")
            response = requests.get(self.url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            # Validate response structure
            if data.get("status") != "success":
                error_msg = data.get("data", {}).get("message", "Unknown error")
                raise ValueError(f"IQAir API returned error: {error_msg}")
            
            logger.info("Successfully fetched air quality data")
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch air quality data: {e}")
            raise
        except (KeyError, ValueError) as e:
            logger.error(f"Invalid API response: {e}")
            raise


async def send_weather_report() -> bool:
    """
    Main function to fetch air quality data and send reports to configured channels.
    
    Handles the complete workflow:
    1. Fetch air quality data from IQAir
    2. Generate formatted report using ChatGPT
    3. Send report to all configured Telegram channels
    
    Returns:
        True if the script completed successfully, False otherwise
    """
    client = None
    try:
        # Initialize clients
        logger.info("Initializing clients...")
        client = get_mtproto_client()
        air_client = IQAirClient()
        chat_client = ChatGPTClient()
        redis_client = RedisClient()
        
        # Start Telegram client
        await client.start()
        logger.info("Telegram client started")
        
        # Fetch air quality data
        try:
            raw_report = air_client.get_raw_report()
        except Exception as e:
            logger.error(f"Failed to fetch air quality data: {e}")
            return False
        
        # Generate formatted report
        try:
            message = chat_client.prepare_weather_report(raw_report)
            if not message or not message.strip():
                logger.error("Generated message is empty, aborting send")
                return False
            logger.info("Weather report generated successfully")
        except Exception as e:
            logger.error(f"Failed to generate weather report: {e}")
            return False
        
        # Get list of channels to send to
        channel_ids = redis_client.get_air_report_channels()
        if not channel_ids:
            logger.warning("No channels configured for air quality reports")
            # This is not a failure - just no channels to send to
            return True
        
        logger.info(f"Sending weather report to {len(channel_ids)} channel(s)")
        
        # Send report to each channel
        success_count = 0
        for channel_id in channel_ids:
            try:
                await client.send_message(channel_id, message)
                logger.info(f"Successfully sent report to channel {channel_id}")
                success_count += 1
            except Exception as e:
                logger.error(f"Failed to send message to channel {channel_id}: {e}")
        
        logger.info(f"Report sent to {success_count}/{len(channel_ids)} channel(s)")
        
        # Consider it successful if at least one message was sent
        return success_count > 0
        
    except Exception as e:
        logger.error(f"Unexpected error in weather report script: {e}", exc_info=True)
        return False
    finally:
        # Clean up: stop the Telegram client
        if client:
            try:
                await client.stop()
                logger.info("Telegram client stopped")
            except Exception as e:
                logger.warning(f"Error stopping Telegram client: {e}")


async def main_async() -> bool:
    """
    Entry point for the async script.
    
    Returns:
        True if successful, False otherwise
    """
    return await send_weather_report()


if __name__ == '__main__':
    exit_code = 0
    try:
        # Run the async main function
        success = asyncio.run(main_async())
        
        if success:
            logger.info("Weather report script completed successfully")
            exit_code = 0
        else:
            logger.error("Weather report script completed with errors")
            exit_code = 1
            
    except KeyboardInterrupt:
        logger.info("Script interrupted by user")
        exit_code = 130  # Standard exit code for SIGINT
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        exit_code = 1
    finally:
        # Ensure all async tasks are cleaned up
        # asyncio.run() handles this, but we log completion for Heroku
        logger.info("Script execution finished, exiting gracefully")
        sys.exit(exit_code)