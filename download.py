#!/usr/bin/env python3
"""
Tanka HaikuBox Bird Data Downloader 

Usage:
    python download.py                         # Download yesterday's data for all enabled HaikuBoxes
    python download.py --date 2024-01-15       # Download data for specific date
    python download.py --box haiku-brbs        # Download for specific HaikuBox only
    python download.py --headless false        # Run browser in visible mode (for debugging)
"""

import argparse
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

from src.config import Config
from src.downloader import HaikuBoxDownloader
from src.logger import setup_logging


logger = logging.getLogger(__name__)


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Download HaikuBox bird detection CSV files"
    )

    parser.add_argument(
        '--date',
        type=str,
        help='Date to download (YYYY-MM-DD). Defaults to yesterday.'
    )

    parser.add_argument(
        '--dates',
        type=str,
        help='Dates to download (YYYY-MM-DD-YYYY-MM-DD). A range of dates'
    )

    parser.add_argument(
        '--box',
        type=str,
        help='Specific HaikuBox name to download. If not specified, downloads all enabled boxes.'
    )

    parser.add_argument(
        '--headless',
        type=str,
        choices=['true', 'false'],
        help='Run browser in headless mode (true/false). Overrides config setting.'
    )

    parser.add_argument(
        '--config',
        type=str,
        help='Path to config file. Defaults to config/haikuboxes.yaml'
    )

    return parser.parse_args()


def main():
    """Main entry point"""
    args = parse_args()

    # Load configuration
    try:
        config = Config(args.config)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Setup logging
    project_root = Path(__file__).parent
    log_dir = project_root / "logs"
    setup_logging(config.get_log_level(), log_dir)

    logger.info("=" * 60)
    logger.info("HaikuBox Bird Data Downloader - Starting")
    logger.info("=" * 60)

    # Determine date(s) to download
    dates_to_download = []

    if args.dates:
        # Parse date range: YYYY-MM-DD-YYYY-MM-DD
        try:
            parts = args.dates.split('-')
            if len(parts) == 6:  # YYYY-MM-DD-YYYY-MM-DD
                start_date = datetime.strptime(f"{parts[0]}-{parts[1]}-{parts[2]}", '%Y-%m-%d')
                end_date = datetime.strptime(f"{parts[3]}-{parts[4]}-{parts[5]}", '%Y-%m-%d')

                if start_date > end_date:
                    logger.error("Start date must be before or equal to end date")
                    sys.exit(1)

                # Generate list of dates in range
                current = start_date
                while current <= end_date:
                    dates_to_download.append(current)
                    current += timedelta(days=1)

                logger.info(f"Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')} ({len(dates_to_download)} days)")
            else:
                logger.error(f"Invalid date range format: {args.dates}. Use YYYY-MM-DD-YYYY-MM-DD")
                sys.exit(1)
        except (ValueError, IndexError) as e:
            logger.error(f"Invalid date range format: {args.dates}. Use YYYY-MM-DD-YYYY-MM-DD")
            sys.exit(1)
    elif args.date:
        # Single date
        try:
            target_date = datetime.strptime(args.date, '%Y-%m-%d')
            dates_to_download = [target_date]
            logger.info(f"Target date: {target_date.strftime('%Y-%m-%d')}")
        except ValueError:
            logger.error(f"Invalid date format: {args.date}. Use YYYY-MM-DD")
            sys.exit(1)
    else:
        # Default to yesterday and today
        target_date = datetime.now() - timedelta(days=1)
        dates_to_download = [target_date]
        dates_to_download.append(datetime.now() - timedelta(days=0))
        logger.info(f"Target date: {target_date.strftime('%Y-%m-%d')}")

    # Validate that no dates are in the future
    now = datetime.now()
    future_dates = [d for d in dates_to_download if d.date() > now.date()]
    if future_dates:
        logger.error("Cannot download data for future dates:")
        for d in future_dates:
            logger.error(f"  - {d.strftime('%Y-%m-%d')}")
        sys.exit(1)

    # Determine which HaikuBoxes to process
    if args.box:
        # Single HaikuBox specified
        haikuboxes = [{'name': args.box, 'enabled': True}]
        logger.info(f"Processing single HaikuBox: {args.box}")
    else:
        # All enabled HaikuBoxes
        haikuboxes = config.get_haikuboxes(enabled_only=True)
        logger.info(f"Processing {len(haikuboxes)} enabled HaikuBox(es)")

    if not haikuboxes:
        logger.warning("No HaikuBoxes to process")
        sys.exit(0)

    # Determine headless mode
    if args.headless:
        headless = args.headless == 'true'
    else:
        headless = config.is_headless()

    # Get authentication credentials
    auth_creds = config.get_auth_credentials()

    # Initialize downloader
    downloader = HaikuBoxDownloader(
        download_dir=config.get_download_dir(),
        headless=headless,
        timeout=config.get_download_timeout(),
        email=auth_creds.get('email'),
        password=auth_creds.get('password')
    )

    # Download for each HaikuBox and each date
    success_count = 0
    fail_count = 0

    for target_date in dates_to_download:
        for box in haikuboxes:
            box_name = box['name']
            logger.info(f"\nProcessing HaikuBox: {box_name} for {target_date.strftime('%Y-%m-%d')}")

            filepath = downloader.download_csv(box_name, target_date)

            if filepath:
                success_count += 1
                logger.info(f"✓ Successfully downloaded: {filepath}")
            else:
                fail_count += 1
                logger.error(f"✗ Failed to download for {box_name} on {target_date.strftime('%Y-%m-%d')}")

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("Download Summary")
    logger.info("=" * 60)
    logger.info(f"Successful: {success_count}")
    logger.info(f"Failed: {fail_count}")
    logger.info(f"Total: {success_count + fail_count}")
    logger.info("=" * 60)

    # Exit with appropriate code
    sys.exit(0 if fail_count == 0 else 1)


if __name__ == "__main__":
    main()
