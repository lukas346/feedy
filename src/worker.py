"""Worker entry point that runs the article fetcher on a schedule."""

import logging
import signal
import sys
import time
from typing import NoReturn

from application.workers.fetch_articles import ArticleFetcher
from infrastructure.config import settings
from infrastructure.logging import setup_logging

setup_logging(name="worker")
logger = logging.getLogger(__name__)

shutdown_requested = False


def signal_handler(signum: int, frame: object) -> None:
    """Handle shutdown signals gracefully."""
    global shutdown_requested
    logger.info(f"Received signal {signum}, shutting down...")
    shutdown_requested = True


def run_worker() -> NoReturn:
    """Run the worker loop indefinitely."""
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    fetcher = ArticleFetcher()
    interval_seconds = settings.worker_interval_minutes * 60

    logger.info(
        f"Starting worker with interval of {settings.worker_interval_minutes} minutes"
    )

    while not shutdown_requested:
        try:
            logger.info("Running article fetch cycle...")
            new_articles = fetcher.run()
            logger.info(f"Fetch cycle complete. {new_articles} new articles fetched.")
        except Exception as e:
            logger.error(f"Error during fetch cycle: {e}")

        for _ in range(interval_seconds):
            if shutdown_requested:
                break
            time.sleep(1)

    logger.info("Worker shutdown complete.")
    sys.exit(0)


if __name__ == "__main__":
    run_worker()
