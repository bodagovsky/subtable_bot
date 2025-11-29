#!/usr/bin/env python3
"""Standalone script to load historical messages from Telegram into Redis."""
import sys
import os
import asyncio
import logging
import argparse
from datetime import datetime
from dotenv import load_dotenv
import pytz

# Add parent directory to path to allow imports when running as module
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mtproto_client import get_mtproto_client
from message_storage import message_storage

load_dotenv()

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

utc = pytz.UTC


async def load_historical_messages(channel_id: int, start_message_id: int, end_message_id: int):
    """Load historical messages from Telegram into Redis.
    
    Args:
        channel_id: Channel/chat ID
        start_message_id: Starting message ID (inclusive)
        end_message_id: Ending message ID (inclusive)
    """
    try:
        logger.info(f"Loading historical messages: IDs {start_message_id} to {end_message_id} from channel {channel_id}")
        
        # Generate message ID range
        message_ids = list(range(start_message_id, end_message_id + 1))
        
        # Get MTProto client
        mtproto = get_mtproto_client()
        
        try:
            # Start MTProto client
            await mtproto.start()
            logger.info("MTProto client started for historical message loading")
            
            # Get messages from Telegram
            # Try with positive channel ID first
            telegram_messages = await mtproto.get_messages(channel_id, message_ids)
            
            # Check if we got any valid messages
            valid_messages = [m for m in telegram_messages if m is not None]
            
            # If no messages found, try with negative channel ID (for groups/channels)
            if not valid_messages:
                logger.info(f"No messages found with positive channel ID, trying negative: {-abs(channel_id)}")
                telegram_messages = await mtproto.get_messages(-abs(channel_id), message_ids)
                valid_messages = [m for m in telegram_messages if m is not None]
            
            if not valid_messages:
                logger.warning("No valid messages retrieved from Telegram for historical loading")
                return
            
            logger.info(f"Retrieved {len(valid_messages)} valid messages out of {len(message_ids)} requested")
            
            # Process and store messages
            stored_count = 0
            skipped_count = 0
            
            for tg_msg in telegram_messages:
                if tg_msg is None:
                    skipped_count += 1
                    continue
                
                try:
                    # Extract message ID
                    message_id = tg_msg.id
                    
                    # Extract user ID
                    user_id = None
                    
                    # Check from_id attribute
                    if hasattr(tg_msg, 'from_id') and tg_msg.from_id:
                        from_id = tg_msg.from_id
                        # Check if it's a User
                        if hasattr(from_id, 'user_id'):
                            user_id = from_id.user_id
                        # If it's a Channel, skip (channel messages don't have user_id)
                        elif hasattr(from_id, 'channel_id'):
                            skipped_count += 1
                            continue
                        # Check if it's a Chat (group chat)
                        elif hasattr(from_id, 'chat_id'):
                            # Try to get sender info
                            if hasattr(tg_msg, 'sender_id') and tg_msg.sender_id:
                                sender_id = tg_msg.sender_id
                                if hasattr(sender_id, 'user_id'):
                                    user_id = sender_id.user_id
                    
                    # If still no user_id, try sender_id directly
                    if user_id is None and hasattr(tg_msg, 'sender_id') and tg_msg.sender_id:
                        sender_id = tg_msg.sender_id
                        if hasattr(sender_id, 'user_id'):
                            user_id = sender_id.user_id
                    
                    # If still no user_id, try peer_id (for forwarded messages or replies)
                    if user_id is None and hasattr(tg_msg, 'peer_id') and tg_msg.peer_id:
                        peer_id = tg_msg.peer_id
                        if hasattr(peer_id, 'user_id'):
                            user_id = peer_id.user_id
                    
                    # If still no user_id, skip this message
                    if user_id is None:
                        skipped_count += 1
                        continue
                    
                    # Extract timestamp
                    # Telethon messages have date attribute
                    if hasattr(tg_msg, 'date') and tg_msg.date:
                        message_timestamp = tg_msg.date
                        # Ensure timezone-aware
                        if message_timestamp.tzinfo is None:
                            message_timestamp = utc.localize(message_timestamp)
                    else:
                        # Use current time as fallback (shouldn't happen normally)
                        message_timestamp = datetime.now(utc)
                    
                    # Store message in Redis (same format as Alfred)
                    message_storage.add_message(
                        chat_id=channel_id,
                        user_id=user_id,
                        message_id=message_id,
                        timestamp=message_timestamp
                    )
                    
                    stored_count += 1
                    
                    if stored_count % 50 == 0:
                        logger.info(f"Stored {stored_count} historical messages so far...")
                    
                except Exception as e:
                    logger.error(f"Error processing historical message {tg_msg.id if tg_msg else 'unknown'}: {e}")
                    skipped_count += 1
                    continue
            
            logger.info("Completed loading historical messages:")
            logger.info(f"  - Stored: {stored_count}")
            logger.info(f"  - Skipped: {skipped_count}")
            logger.info(f"  - Total processed: {len(telegram_messages)}")
            
        except Exception as e:
            logger.error(f"Error loading historical messages: {e}")
            raise
        finally:
            # Stop MTProto client
            await mtproto.stop()
            logger.info("MTProto client stopped after historical message loading")
            
    except Exception as e:
        logger.error(f"Failed to load historical messages: {e}")
        raise


async def main_async():
    """Main async function."""
    parser = argparse.ArgumentParser(
        description="Load historical messages from Telegram into Redis"
    )
    parser.add_argument(
        "--channel-id",
        type=int,
        required=True,
        help="Channel/chat ID"
    )
    parser.add_argument(
        "--start-id",
        type=int,
        required=True,
        help="Starting message ID (inclusive)"
    )
    parser.add_argument(
        "--end-id",
        type=int,
        required=True,
        help="Ending message ID (inclusive)"
    )
    
    args = parser.parse_args()
    
    await load_historical_messages(
        channel_id=args.channel_id,
        start_message_id=args.start_id,
        end_message_id=args.end_id
    )


def main():
    """Main entry point."""
    asyncio.run(main_async())


if __name__ == "__main__":
    main()


