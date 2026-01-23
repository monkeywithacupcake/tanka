#!/usr/bin/env python3
"""
Tanka HaikuBox Bird Data Analyzer - CLI

Analyzes downloaded CSV files and generates bird detection summaries.

Usage:
    python analyze.py                         # Analyze yesterday's data
    python analyze.py --date 2026-01-19       # Analyze specific date
    python analyze.py --box my-name-brbs      # Analyze specific HaikuBox
    python analyze.py --all                   # Analyze all available CSVs
"""

import argparse
import sys
import logging
from datetime import datetime, timedelta
from pathlib import Path

from src.config import Config
from src.analyzer import BirdDataAnalyzer
from src.logger import setup_logging


logger = logging.getLogger(__name__)


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Analyze HaikuBox bird detection CSV files"
    )

    parser.add_argument(
        '--date',
        type=str,
        help='Date to analyze (YYYY-MM-DD). Defaults to yesterday.'
    )

    parser.add_argument(
        '--box',
        type=str,
        help='Specific HaikuBox name to analyze. If not specified, analyzes all enabled boxes.'
    )

    parser.add_argument(
        '--all',
        action='store_true',
        help='Analyze all available CSV files in download directory'
    )

    parser.add_argument(
        '--config',
        type=str,
        help='Path to config file. Defaults to config/haikuboxes.yaml'
    )

    parser.add_argument(
        '--threshold',
        type=float,
        help='Override score threshold (0.0 to 1.0)'
    )

    parser.add_argument(
        '--top',
        type=int,
        help='Override number of top species to show'
    )

    return parser.parse_args()


def find_csv_files(download_dir: Path, haikubox_name: str = None,
                  date: datetime = None) -> list[Path]:
    """
    Find CSV files to analyze

    Args:
        download_dir: Directory containing CSV files
        haikubox_name: Optional HaikuBox name filter
        date: Optional date filter

    Returns:
        List of CSV file paths
    """
    csv_files = []

    if haikubox_name and date:
        # Specific box and date
        filename = f"{haikubox_name}_{date.strftime('%Y-%m-%d')}.csv"
        filepath = download_dir / filename
        if filepath.exists():
            csv_files.append(filepath)
    elif haikubox_name:
        # All files for specific box
        pattern = f"{haikubox_name}_*.csv"
        csv_files = list(download_dir.glob(pattern))
    elif date:
        # All boxes for specific date
        pattern = f"*_{date.strftime('%Y-%m-%d')}.csv"
        csv_files = list(download_dir.glob(pattern))
    else:
        # All CSV files
        csv_files = list(download_dir.glob("*.csv"))

    return sorted(csv_files)


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
    logger.info("Tanka HaikuBox Bird Data Analyzer - Starting")
    logger.info("=" * 60)

    # Get analysis settings
    analysis_settings = config.get_analysis_settings()

    # Override with command line args if provided
    if args.threshold is not None:
        analysis_settings['score_threshold'] = args.threshold
    if args.top is not None:
        analysis_settings['top_n'] = args.top

    # Initialize analyzer
    analyzer = BirdDataAnalyzer(
        score_threshold=analysis_settings['score_threshold'],
        top_n=analysis_settings['top_n'],
        exclude_species=analysis_settings['exclude_species']
    )

    # Determine which files to analyze
    download_dir = config.get_download_dir()

    if args.all:
        # Analyze all available CSVs
        csv_files = find_csv_files(download_dir)
        logger.info(f"Analyzing all {len(csv_files)} CSV file(s)")
    else:
        # Determine date
        if args.date:
            try:
                target_date = datetime.strptime(args.date, '%Y-%m-%d')
            except ValueError:
                logger.error(f"Invalid date format: {args.date}. Use YYYY-MM-DD")
                sys.exit(1)
        else:
            # Default to yesterday
            target_date = datetime.now() - timedelta(days=1)

        logger.info(f"Target date: {target_date.strftime('%Y-%m-%d')}")

        # Find CSV files
        csv_files = find_csv_files(download_dir, args.box, target_date)

    if not csv_files:
        logger.warning("No CSV files found to analyze")
        print("\nNo CSV files found matching the criteria.")
        print(f"Download directory: {download_dir}")
        sys.exit(0)

    logger.info(f"Found {len(csv_files)} CSV file(s) to analyze")

    # Analyze files
    if len(csv_files) == 1:
        # Single file analysis
        analysis = analyzer.analyze_csv(csv_files[0])
        if analysis:
            summary = analyzer.format_summary(analysis)
            print("\n" + summary)
    else:
        # Multiple files - combine analysis
        logger.info("Combining analysis from multiple files")
        analysis = analyzer.analyze_multiple_csvs(csv_files)
        if analysis:
            summary = analyzer.format_summary(analysis)
            print("\n" + summary)

    logger.info("=" * 60)
    logger.info("Analysis Complete")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
