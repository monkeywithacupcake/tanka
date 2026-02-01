#!/usr/bin/env python3
"""
HaikuBox Bird Data Analyzer - CLI

Analyzes downloaded CSV files and generates bird detection summaries.
Dates are in LOCAL time. Data is downloaded in UTC, so analyzing
a local date requires data from two UTC day files.

Usage:
    python analyze.py                         # Analyze 2 days ago (guaranteed complete)
    python analyze.py --date 2026-01-19       # Analyze specific local date
    python analyze.py --box haiku-brbs        # Analyze specific HaikuBox
    python analyze.py --all                   # Analyze all available CSVs (raw UTC data)
    python analyze.py --time                  # Include time-of-day analysis

Note: CSV files are downloaded by UTC date. A full local day (midnight to midnight
Pacific) spans two UTC files. For example, local Jan 20 requires UTC Jan 20 and
Jan 21 files. The default of 2 days ago ensures complete data is always available.
"""

import argparse
import json
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
        help='Local date to analyze (YYYY-MM-DD). Defaults to yesterday.'
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

    parser.add_argument(
        '--time',
        action='store_true',
        help='Include time-of-day analysis (hourly activity and species time ranges)'
    )

    parser.add_argument(
        '--save',
        action='store_true',
        help='Save analysis results to JSON file in analysis/ directory'
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


def save_analysis_json(analysis: dict, output_dir: Path, date_str: str) -> Path:
    """
    Save analysis results to JSON file

    Args:
        analysis: Analysis results dictionary
        output_dir: Directory to save JSON file
        date_str: Date string for filename (YYYY-MM-DD)

    Returns:
        Path to saved JSON file
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{date_str}.json"

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(analysis, f, indent=2)

    return output_path


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
    logger.info("HaikuBox Bird Data Analyzer - Starting")
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
        exclude_species=analysis_settings['exclude_species'],
        include_time_analysis=args.time
    )

    # Determine which files to analyze
    download_dir = config.get_download_dir()

    if args.all:
        # Analyze all available CSVs (raw UTC data, not filtered by local date)
        csv_files = find_csv_files(download_dir)
        logger.info(f"Analyzing all {len(csv_files)} CSV file(s) (raw UTC data)")

        if not csv_files:
            logger.warning("No CSV files found to analyze")
            print("\nNo CSV files found matching the criteria.")
            print(f"Download directory: {download_dir}")
            sys.exit(0)

        logger.info(f"Found {len(csv_files)} CSV file(s) to analyze")

        # Analyze files
        if len(csv_files) == 1:
            analysis = analyzer.analyze_csv(csv_files[0])
        else:
            logger.info("Combining analysis from multiple files")
            analysis = analyzer.analyze_multiple_csvs(csv_files)
    else:
        # Analyze for a specific LOCAL date
        # This requires loading two UTC files and filtering by local date
        if args.date:
            try:
                target_date = datetime.strptime(args.date, '%Y-%m-%d')
            except ValueError:
                logger.error(f"Invalid date format: {args.date}. Use YYYY-MM-DD")
                sys.exit(1)
        else:
            # Default to 2 days ago for guaranteed complete data
            # (yesterday's local data requires today's UTC file which may be incomplete)
            target_date = datetime.now() - timedelta(days=2)

        logger.info(f"Target local date: {target_date.strftime('%Y-%m-%d')}")

        # Get enabled boxes
        enabled_boxes = config.get_haikuboxes(enabled_only=True)
        if args.box:
            # Filter to specific box
            enabled_boxes = [b for b in enabled_boxes if b['name'] == args.box]
            if not enabled_boxes:
                logger.error(f"HaikuBox '{args.box}' not found or not enabled")
                sys.exit(1)

        if not enabled_boxes:
            logger.error("No HaikuBoxes enabled in configuration")
            sys.exit(1)

        # Analyze each box for the local date
        all_analyses = []
        for box in enabled_boxes:
            box_name = box['name']
            logger.info(f"Analyzing {box_name} for local date {target_date.strftime('%Y-%m-%d')}")
            analysis = analyzer.analyze_local_date(download_dir, box_name, target_date)
            if analysis:
                all_analyses.append(analysis)

        if not all_analyses:
            logger.warning("No data found for the specified date")
            print(f"\nNo data found for local date {target_date.strftime('%Y-%m-%d')}.")
            print(f"Download directory: {download_dir}")
            print("\nNote: Analyzing a local date requires two UTC files.")
            print(f"For {target_date.strftime('%Y-%m-%d')}, you need:")
            print(f"  - {target_date.strftime('%Y-%m-%d')}.csv (afternoon/evening UTC)")
            print(f"  - {(target_date + timedelta(days=1)).strftime('%Y-%m-%d')}.csv (morning UTC)")
            sys.exit(0)

        # Use first analysis if single box, otherwise would need to combine
        if len(all_analyses) == 1:
            analysis = all_analyses[0]
        else:
            # Multiple boxes - for now just use first one
            # TODO: Add support for combining multiple boxes
            logger.info(f"Multiple boxes analyzed, showing first: {all_analyses[0]['box_name']}")
            analysis = all_analyses[0]

    if not analysis:
        logger.error("Analysis failed")
        sys.exit(1)

    # Print summary
    summary = analyzer.format_summary(analysis)
    print("\n" + summary)

    # Save to JSON if requested
    if args.save:
        analysis_dir = project_root / "analysis"
        # Use target date for filename, or today if analyzing all
        if args.all:
            date_str = datetime.now().strftime('%Y-%m-%d')
        else:
            date_str = target_date.strftime('%Y-%m-%d')

        output_path = save_analysis_json(analysis, analysis_dir, date_str)
        logger.info(f"Analysis saved to: {output_path}")
        print(f"\nAnalysis saved to: {output_path}")

    logger.info("=" * 60)
    logger.info("Analysis Complete")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
