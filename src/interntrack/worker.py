"""
Background worker for scheduled tasks.
"""

import asyncio
import signal
import sys

from interntrack.scheduler.setup import setup_scheduler
from interntrack.utils.logger import get_logger, setup_logging

logger = get_logger(__name__)


async def main():
    """Main worker loop."""
    setup_logging()
    logger.info("Starting InternTrack worker...")

    # Setup scheduler
    scheduler_instance = setup_scheduler()
    scheduler_instance.start()

    logger.info("Worker started. Press Ctrl+C to stop.")

    # Handle shutdown
    def shutdown_handler(signum, frame):
        logger.info("Shutting down worker...")
        scheduler_instance.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    # Keep running
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        scheduler_instance.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
