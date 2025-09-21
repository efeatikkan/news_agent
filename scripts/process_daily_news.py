#!/usr/bin/env python3
"""
Daily news processing script
Can be run as a cron job or scheduled task
"""

import asyncio
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv
from src.services.news_processor import news_processor

load_dotenv()

async def main():
    """Process daily news"""
    try:
        print("Starting daily news processing...")
        await news_processor.run_daily_processing_task()
        print("Daily news processing completed successfully!")
    except Exception as e:
        print(f"Error in daily news processing: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())