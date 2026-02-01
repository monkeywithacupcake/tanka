#!/usr/bin/env python3
"""
Tanka Bsky Post

Posts bird analysis results to Bluesky. Reads from JSON files
created by analyze.py --save.

Usage:
    python bsky_post.py                    # Post yesterday's analysis
    python bsky_post.py --date 2026-01-20  # Post specific date
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

from src.config import Config
from src.logger import setup_logging
from src.poster import TankaPoster


logger = logging.getLogger(__name__)


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Post bird analysis to Bluesky"
    )

    parser.add_argument(
        '--date',
        type=str,
        help='Date to post (YYYY-MM-DD). Defaults to yesterday.'
    )

    parser.add_argument(
        '--config',
        type=str,
        help='Path to config file. Defaults to config/haikuboxes.yaml'
    )

    parser.add_argument(
        '--dryrun',
        action='store_true',
        help='Show what would be posted without actually posting'
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

    logger.info("Tanka - Posting to Bluesky")

    # Determine date
    if args.date:
        try:
            target_date = datetime.strptime(args.date, '%Y-%m-%d')
        except ValueError:
            logger.error(f"Invalid date format: {args.date}. Use YYYY-MM-DD")
            sys.exit(1)
    else:
        target_date = datetime.now() - timedelta(days=1) # yesterday

    date_str = target_date.strftime('%Y-%m-%d')

    # Find analysis JSON file
    analysis_dir = project_root / "analysis"
    json_path = analysis_dir / f"{date_str}.json"

    if not json_path.exists():
        logger.error(f"Analysis file not found: {json_path}")
        print(f"\nNo analysis found for {date_str}.")
        print(f"Run: python analyze.py --date {date_str} --save")
        print(f"or if you want time data")
        print(f"Run: python analyze.py --date {date_str} --time --save")
        sys.exit(1)

    # Load analysis from JSON
    logger.info(f"Loading analysis from: {json_path}")
    with open(json_path, 'r', encoding='utf-8') as f:
        analysis = json.load(f)

    if args.dryrun:
        # Preview posts without logging in or posting
        poster = object.__new__(TankaPoster)  # Create without __init__

        posts = [
            poster.format_summary_post(analysis),
            poster.format_top_species_post(analysis) 
        ]
        new_birds = poster.format_new_birds_post(analysis)
        if new_birds:
            posts.append(new_birds)
        time_summary_post = poster.format_time_summary_post(analysis)
        if time_summary_post:
            posts.append(time_summary_post)

        print(f"\n=== DRY RUN: {len(posts)} posts would be created ===\n")
        for i, post in enumerate(posts, 1):
            print(f"--- Post {i} ---")
            print(post)
            print()
        return

    # Get bsky credentials and post
    bsky_creds = config.get_bsky_credentials()

    poster = TankaPoster(
        user_name=bsky_creds.get('user_name'),
        app_pword=bsky_creds.get('app_pword')
    )

    poster.post_analysis(analysis)
    logger.info("Posted to Bluesky successfully")


if __name__ == "__main__":
    main()
