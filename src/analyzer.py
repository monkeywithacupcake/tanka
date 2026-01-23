"""Tanka HaikuBox CSV data analyzer"""

import csv
import logging
from pathlib import Path
from typing import List, Dict, Tuple, Set
from collections import defaultdict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class BirdDataAnalyzer:
    """Analyzes HaikuBox bird detection CSV data"""

    def __init__(self, score_threshold: float = 0.5, top_n: int = 10,
                 exclude_species: List[str] = None, lookback_days: int = 7):
        """
        Initialize analyzer

        Args:
            score_threshold: Minimum confidence score to include (0.0 to 1.0)
            top_n: Number of top species to return
            exclude_species: List of species names to exclude from analysis
            lookback_days: Number of days to look back for detecting new/rare birds
        """
        self.score_threshold = score_threshold
        self.top_n = top_n
        self.exclude_species = exclude_species or []
        self.lookback_days = lookback_days

    def analyze_csv(self, csv_path: Path) -> Dict:
        """
        Analyze a single CSV file

        Args:
            csv_path: Path to CSV file

        Returns:
            Dictionary with analysis results
        """
        if not csv_path.exists():
            logger.error(f"CSV file not found: {csv_path}")
            return None

        logger.info(f"Analyzing CSV: {csv_path}")

        # Read and filter data
        detections = self._read_csv(csv_path)
        filtered = self._filter_by_score(detections)

        # Group and count by species
        species_counts = self._count_by_species(filtered)

        # Get top N
        top_species = self._get_top_species(species_counts)

        # Calculate statistics
        total_detections = len(detections)
        filtered_detections = len(filtered)
        unique_species = len(species_counts)

        # Detect new/rare birds
        new_birds = self._detect_new_birds(csv_path, set(species_counts.keys()))

        result = {
            'file': str(csv_path.name),
            'total_detections': total_detections,
            'filtered_detections': filtered_detections,
            'unique_species': unique_species,
            'top_species': top_species,
            'score_threshold': self.score_threshold,
            'new_birds': new_birds
        }

        logger.info(f"Analysis complete: {unique_species} species, "
                   f"{filtered_detections}/{total_detections} detections above threshold")

        return result

    def _read_csv(self, csv_path: Path) -> List[Dict]:
        """Read CSV file and return list of detection records"""
        detections = []

        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    detections.append(row)
        except Exception as e:
            logger.error(f"Error reading CSV: {e}")
            return []

        return detections

    def _filter_by_score(self, detections: List[Dict]) -> List[Dict]:
        """Filter detections by confidence score threshold"""
        filtered = []

        for detection in detections:
            try:
                score = float(detection.get('Score', 0))
                species = detection.get('Species', '')

                # Apply score threshold
                if score < self.score_threshold:
                    continue

                # Apply species exclusion
                if species in self.exclude_species:
                    continue

                filtered.append(detection)
            except (ValueError, TypeError):
                # Skip rows with invalid score values
                continue

        return filtered

    def _count_by_species(self, detections: List[Dict]) -> Dict[str, int]:
        """Count detections by species"""
        counts = defaultdict(int)

        for detection in detections:
            species = detection.get('Species', 'Unknown')
            count = int(detection.get('Count', 1))
            counts[species] += count

        return dict(counts)

    def _get_top_species(self, species_counts: Dict[str, int]) -> List[Tuple[str, int]]:
        """Get top N species by count"""
        # Sort by count (descending)
        sorted_species = sorted(
            species_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )

        # Return top N
        return sorted_species[:self.top_n]

    def _extract_date_from_filename(self, csv_path: Path) -> datetime:
        """
        Extract date from CSV filename (format: boxname_YYYY-MM-DD.csv)

        Args:
            csv_path: Path to CSV file

        Returns:
            datetime object or None if parsing fails
        """
        try:
            # Expected format: boxname_YYYY-MM-DD.csv
            filename = csv_path.stem  # Remove .csv extension
            date_str = filename.split('_')[-1]  # Get the date part
            return datetime.strptime(date_str, '%Y-%m-%d')
        except (ValueError, IndexError):
            logger.warning(f"Could not extract date from filename: {csv_path.name}")
            return None

    def _find_historical_files(self, csv_path: Path) -> List[Path]:
        """
        Find CSV files for the lookback period before the given file's date

        Args:
            csv_path: Path to the CSV file being analyzed

        Returns:
            List of historical CSV file paths
        """
        current_date = self._extract_date_from_filename(csv_path)
        if not current_date:
            return []

        # Extract box name from filename (everything before the date)
        filename = csv_path.stem
        parts = filename.rsplit('_', 1)
        if len(parts) != 2:
            logger.warning(f"Could not extract box name from filename: {csv_path.name}")
            return []

        box_name = parts[0]
        download_dir = csv_path.parent

        # Find files for the lookback period
        historical_files = []
        for days_back in range(1, self.lookback_days + 1):
            historical_date = current_date - timedelta(days=days_back)
            historical_filename = f"{box_name}_{historical_date.strftime('%Y-%m-%d')}.csv"
            historical_path = download_dir / historical_filename

            if historical_path.exists():
                historical_files.append(historical_path)

        logger.info(f"Found {len(historical_files)} historical files in last {self.lookback_days} days")
        return historical_files

    def _get_historical_species(self, csv_paths: List[Path]) -> Set[str]:
        """
        Get set of all species seen in historical CSV files

        Args:
            csv_paths: List of historical CSV file paths

        Returns:
            Set of species names
        """
        species_set = set()

        for csv_path in csv_paths:
            detections = self._read_csv(csv_path)
            filtered = self._filter_by_score(detections)

            for detection in filtered:
                species = detection.get('Species', '')
                if species:
                    species_set.add(species)

        return species_set

    def _detect_new_birds(self, csv_path: Path, current_species: Set[str]) -> List[str]:
        """
        Detect birds that are new or haven't been seen in the lookback period

        Args:
            csv_path: Path to the current CSV file being analyzed
            current_species: Set of species detected in current file

        Returns:
            List of new/rare bird species names
        """
        if not current_species:
            return []

        # Find historical files
        historical_files = self._find_historical_files(csv_path)

        if not historical_files:
            logger.info("No historical data found - all birds marked as new")
            return sorted(list(current_species))

        # Get species from historical period
        historical_species = self._get_historical_species(historical_files)

        # Find species in current but not in historical
        new_species = current_species - historical_species

        if new_species:
            logger.info(f"Found {len(new_species)} new/rare bird(s): {', '.join(sorted(new_species))}")

        return sorted(list(new_species))

    def format_summary(self, analysis: Dict) -> str:
        """
        Format analysis results as a readable summary

        Args:
            analysis: Analysis results dictionary

        Returns:
            Formatted summary string
        """
        if not analysis:
            return "No analysis results available"

        lines = []
        # Handle both single file and multiple files
        if 'file' in analysis:
            title = f"Bird Detection Summary: {analysis['file']}"
        elif 'files' in analysis:
            title = f"Bird Detection Summary: {len(analysis['files'])} files"
        else:
            title = "Bird Detection Summary"

        lines.append(title)
        lines.append("=" * 60)
        lines.append(f"Total detections: {analysis['total_detections']}")
        lines.append(f"Above threshold ({analysis['score_threshold']}): {analysis['filtered_detections']}")
        lines.append(f"Unique species: {analysis['unique_species']}")

        # Show new/rare birds if any
        if 'new_birds' in analysis and analysis['new_birds']:
            lines.append("")
            lines.append("New/Rare Birds (not seen in last 7 days):")
            lines.append("-" * 60)
            for bird in analysis['new_birds']:
                lines.append(f"  * {bird}")

        lines.append("")
        lines.append(f"Top {len(analysis['top_species'])} Species:")
        lines.append("-" * 60)

        for i, (species, count) in enumerate(analysis['top_species'], 1):
            lines.append(f"{i:2d}. {species:30s} {count:4d} detections")

        return "\n".join(lines)

    def analyze_multiple_csvs(self, csv_paths: List[Path]) -> Dict:
        """
        Analyze multiple CSV files and combine results

        Args:
            csv_paths: List of paths to CSV files

        Returns:
            Combined analysis results
        """
        all_species_counts = defaultdict(int)
        all_new_birds = set()
        total_detections = 0
        total_filtered = 0

        for csv_path in csv_paths:
            analysis = self.analyze_csv(csv_path)
            if analysis:
                total_detections += analysis['total_detections']
                total_filtered += analysis['filtered_detections']

                for species, count in analysis['top_species']:
                    all_species_counts[species] += count

                # Collect new birds from each file
                if 'new_birds' in analysis and analysis['new_birds']:
                    all_new_birds.update(analysis['new_birds'])

        # Get top N from combined data
        top_species = self._get_top_species(dict(all_species_counts))

        return {
            'files': [str(p.name) for p in csv_paths],
            'total_detections': total_detections,
            'filtered_detections': total_filtered,
            'unique_species': len(all_species_counts),
            'top_species': top_species,
            'score_threshold': self.score_threshold,
            'new_birds': sorted(list(all_new_birds))
        }
