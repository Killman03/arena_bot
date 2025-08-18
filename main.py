#!/usr/bin/env python3
"""
Main entry point for the Gladiator Arena Life Bot
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add the app directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "app"))

from bot import main


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.getLogger(__name__).info("Bot stopped")
    except Exception as e:
        logging.error(f"Bot crashed with error: {e}")
        sys.exit(1)
