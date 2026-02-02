"""HaikuBox CSV data analyzer"""

import csv
import logging
from pathlib import Path
from typing import List, Dict, Tuple, Set, Optional
from collections import defaultdict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# UTC offset for local time (Pacific = -8)
LOCAL_UTC_OFFSET = -8


class BirdDataAnalyzer:
    """Analyzes HaikuBox bird detection CSV data"""

    def __init__(self, score_threshold: float = 0.5, top_n: int = 10,
                 exclude_species: List[str] = None, lookback_days: int = 7,
                 include_time_analysis: bool = False):
        """
        Initialize analyzer

        Args:
            score_threshold: Minimum confidence score to include (0.0 to 1.0)
            top_n: Number of top species to return
            exclude_species: List of species names to exclude from analysis
            lookback_days: Number of days to look back for detecting new/rare birds
            include_time_analysis: Whether to include time-of-day analysis
        """
        self.score_threshold = score_threshold
        self.top_n = top_n
        self.exclude_species = exclude_species or []
        self.lookback_days = lookback_days
        self.include_time_analysis = include_time_analysis

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

        # Add time-based analysis if requested
        if self.include_time_analysis:
            hour_counts = self._count_by_hour(filtered)
            species_time_ranges = self._get_species_time_ranges(filtered)
            time_summary = self._get_time_summary(hour_counts, species_time_ranges)
            result['hour_counts'] = hour_counts
            result['species_time_ranges'] = species_time_ranges
            result['time_summary'] = time_summary

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

    def _filter_by_local_date(self, detections: List[Dict], target_date: datetime) -> List[Dict]:
        """
        Filter detections to only include those matching the target local date.

        Args:
            detections: List of detection records
            target_date: Target date to filter for (local time)

        Returns:
            Filtered list of detections
        """
        filtered = []
        # CSV Local Date format: "20-Jan-2026"
        target_str = target_date.strftime('%d-%b-%Y')

        for detection in detections:
            local_date = detection.get('Local Date', '')
            if local_date == target_str:
                filtered.append(detection)

        return filtered

    def _count_by_species(self, detections: List[Dict]) -> Dict[str, int]:
        """Count detections by species"""
        counts = defaultdict(int)

        for detection in detections:
            species = detection.get('Species', 'Unknown')
            count = int(detection.get('Count', 1))
            counts[species] += count

        return dict(counts)

    def _count_by_hour(self, detections: List[Dict]) -> Dict[int, int]:
        """
        Count detections by hour of day (0-23)

        Args:
            detections: List of detection records

        Returns:
            Dictionary mapping hour (0-23) to detection count
        """
        hour_counts = defaultdict(int)

        for detection in detections:
            try:
                # Parse Local Time field (format: HH:MM:SS)
                local_time = detection.get('Local Time', '')
                if not local_time:
                    continue

                # Extract hour (floor to hour)
                hour = int(local_time.split(':')[0])
                count = int(detection.get('Count', 1))
                hour_counts[hour] += count
            except (ValueError, IndexError):
                # Skip rows with invalid time values
                continue

        return dict(hour_counts)

    def _get_species_time_ranges(self, detections: List[Dict]) -> Dict[str, Dict]:
        """
        Get time range information for each species

        Args:
            detections: List of detection records

        Returns:
            Dictionary mapping species name to time range info:
            {
                'species_name': {
                    'hours': set of hours when detected,
                    'first_seen': earliest hour,
                    'last_seen': latest hour,
                    'count': total detections
                }
            }
        """
        species_times = defaultdict(lambda: {
            'hours': set(),
            'count': 0
        })

        for detection in detections:
            try:
                species = detection.get('Species', 'Unknown')
                local_time = detection.get('Local Time', '')
                if not local_time or species == 'Unknown':
                    continue

                # Extract hour
                hour = int(local_time.split(':')[0])
                count = int(detection.get('Count', 1))

                species_times[species]['hours'].add(hour)
                species_times[species]['count'] += count
            except (ValueError, IndexError):
                continue

        # Calculate first/last seen for each species
        result = {}
        for species, data in species_times.items():
            if data['hours']:
                sorted_hours = sorted(data['hours'])
                result[species] = {
                    'hours': sorted_hours,  # Convert set to sorted list for JSON
                    'first_seen': sorted_hours[0],
                    'last_seen': sorted_hours[-1],
                    'count': data['count']
                }

        return result

    def _get_time_summary(self, hour_counts: Dict[int, int],
                          species_time_ranges: Dict[str, Dict]) -> Dict:
        """
        Generate a summary of time-based activity patterns

        Args:
            hour_counts: Detection counts by hour
            species_time_ranges: Time range data for each species

        Returns:
            Dictionary with time summary info
        """
        if not hour_counts or not species_time_ranges:
            return {}

        # Find peak hours (hours with above-average activity)
        total_detections = sum(hour_counts.values())
        active_hours = [h for h, c in hour_counts.items() if c > 0]

        if not active_hours:
            return {}

        avg_per_active_hour = total_detections / len(active_hours)
        peak_hours = sorted([h for h, c in hour_counts.items() if c >= avg_per_active_hour])

        # Find the main activity window (continuous range with most activity)
        first_active = min(active_hours)
        last_active = max(active_hours)

        # Find busiest hour
        busiest_hour = max(hour_counts.items(), key=lambda x: x[1])

        # Check for early birds (active before 7am) or night owls (active after 7pm)
        early_birds = []
        night_owls = []

        for species, data in species_time_ranges.items():
            hours = data['hours']
            if any(h < 7 for h in hours):
                early_birds.append(species)
            if any(h >= 19 for h in hours):
                night_owls.append(species)

        # Species active across the widest time range
        widest_range = None
        widest_species = None
        for species, data in species_time_ranges.items():
            span = data['last_seen'] - data['first_seen']
            if widest_range is None or span > widest_range:
                widest_range = span
                widest_species = species

        return {
            'first_detection': first_active,
            'last_detection': last_active,
            'busiest_hour': busiest_hour[0],
            'busiest_hour_count': busiest_hour[1],
            'peak_hours': peak_hours,
            'early_birds': early_birds,  # Species active before 7am
            'night_owls': night_owls,    # Species active after 7pm
            'most_active_species': widest_species,
            'most_active_span': widest_range
        }

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
        # Handle local date, single file, and multiple files
        if 'local_date' in analysis:
            box_name = analysis.get('box_name', 'Unknown')
            title = f"Bird Detection Summary: {analysis['local_date']} (Local Time)"
            lines.append(title)
            lines.append("=" * 60)
            lines.append(f"HaikuBox: {box_name}")
            lines.append(f"UTC files used: {', '.join(analysis.get('utc_files', []))}")
            lines.append("")
        elif 'file' in analysis:
            title = f"Bird Detection Summary: {analysis['file']}"
            lines.append(title)
            lines.append("=" * 60)
        elif 'files' in analysis:
            title = f"Bird Detection Summary: {len(analysis['files'])} files"
            lines.append(title)
            lines.append("=" * 60)
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

        # Add time-based analysis if present
        if 'hour_counts' in analysis:
            lines.append("")
            lines.append(self._format_hourly_activity(analysis['hour_counts']))

        if 'species_time_ranges' in analysis:
            lines.append("")
            lines.append(self._format_species_time_ranges(
                analysis['species_time_ranges'],
                analysis.get('top_species', [])
            ))

        if 'time_summary' in analysis:
            lines.append("")
            lines.append(self._format_time_summary(analysis['time_summary']))

        return "\n".join(lines)

    def _format_time_summary(self, time_summary: Dict) -> str:
        """Format time summary for display"""
        if not time_summary:
            return ""

        lines = []
        lines.append("Activity Summary:")
        lines.append("-" * 60)

        first = time_summary.get('first_detection', 0)
        last = time_summary.get('last_detection', 0)
        busiest = time_summary.get('busiest_hour', 0)
        busiest_count = time_summary.get('busiest_hour_count', 0)

        lines.append(f"Active window: {first:02d}:00 - {last:02d}:59")
        lines.append(f"Busiest hour: {busiest:02d}:00 ({busiest_count} detections)")

        peak_hours = time_summary.get('peak_hours', [])
        if peak_hours:
            peak_str = ", ".join(f"{h:02d}:00" for h in peak_hours)
            lines.append(f"Peak activity: {peak_str}")

        most_active = time_summary.get('most_active_species')
        span = time_summary.get('most_active_span', 0)
        if most_active:
            lines.append(f"Longest active: {most_active} ({span}+ hours)")

        early_birds = time_summary.get('early_birds', [])
        if early_birds:
            lines.append(f"Early birds (before 7am): {', '.join(early_birds)}")

        night_owls = time_summary.get('night_owls', [])
        if night_owls:
            lines.append(f"Night owls (after 7pm): {', '.join(night_owls)}")

        return "\n".join(lines)

    def _format_hourly_activity(self, hour_counts: Dict[int, int]) -> str:
        """
        Format hourly activity counts

        Args:
            hour_counts: Dictionary mapping hour (0-23) to count

        Returns:
            Formatted string
        """
        lines = []
        lines.append("Detections by Hour of Day:")
        lines.append("-" * 60)

        # Show all 24 hours, even if no detections
        for hour in range(24):
            count = hour_counts.get(hour, 0)
            # Create simple bar chart
            bar_length = min(count, 50)  # Cap at 50 chars
            bar = '█' * bar_length if count > 0 else ''
            lines.append(f"{hour:2d}:00  {count:4d}  {bar}")

        return "\n".join(lines)

    def _format_species_time_ranges(self, species_time_ranges: Dict[str, Dict],
                                   top_species: List[Tuple[str, int]] = None) -> str:
        """
        Format species time ranges

        Args:
            species_time_ranges: Dictionary with species time range info
            top_species: Optional list of (species, count) to show only top species

        Returns:
            Formatted string
        """
        lines = []
        lines.append("Species Activity Time Ranges:")
        lines.append("-" * 60)

        # If top_species provided, show only those species
        if top_species:
            species_to_show = [species for species, _ in top_species]
        else:
            # Sort by count
            species_to_show = sorted(
                species_time_ranges.keys(),
                key=lambda s: species_time_ranges[s]['count'],
                reverse=True
            )

        for species in species_to_show:
            if species not in species_time_ranges:
                continue

            data = species_time_ranges[species]
            first = data['first_seen']
            last = data['last_seen']
            num_hours = len(data['hours'])

            # Format time range
            time_range = f"{first:02d}:00-{last:02d}:59"

            # Create visual timeline (24 hour)
            timeline = ['·'] * 24
            for hour in data['hours']:
                timeline[hour] = '█'
            timeline_str = ''.join(timeline)

            lines.append(f"{species[:30]:30s} {time_range:13s} ({num_hours:2d}h)")
            lines.append(f"  0    4    8   12   16   20   24")
            lines.append(f"  {timeline_str}")

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

    def analyze_local_date(self, download_dir: Path, box_name: str,
                           local_date: datetime, 
                           box_location: str) -> Optional[Dict]:
        """
        Analyze bird detections for a specific local date.

        Since CSV files are organized by UTC date, a single local day spans
        two UTC day files. This method loads both files and filters to only
        include detections from the target local date.

        For Pacific time (UTC-8):
        - Local date Jan 20 = Jan 20 00:00 to Jan 20 23:59 Pacific
        - In UTC: Jan 20 08:00 to Jan 21 07:59 UTC
        - Requires: Jan 20 UTC file (afternoon portion) + Jan 21 UTC file (morning portion)

        Args:
            download_dir: Directory containing CSV files
            box_name: HaikuBox name (e.g., "haiku-brbs")
            local_date: Target local date to analyze

        Returns:
            Analysis results dictionary, or None if insufficient data
        """
        # For a local date, we need:
        # - The UTC file for that date (contains afternoon/evening local time)
        # - The UTC file for the next date (contains morning local time)
        utc_date1 = local_date  # Same date UTC file
        utc_date2 = local_date + timedelta(days=1)  # Next date UTC file

        file1 = download_dir / f"{box_name}_{utc_date1.strftime('%Y-%m-%d')}.csv"
        file2 = download_dir / f"{box_name}_{utc_date2.strftime('%Y-%m-%d')}.csv"

        logger.info(f"Analyzing local date {local_date.strftime('%Y-%m-%d')} "
                   f"(requires UTC files: {file1.name}, {file2.name})")
        logger.info(f"---- blarge {box_location}")
        # Load detections from both files
        all_detections = []

        if file1.exists():
            detections1 = self._read_csv(file1)
            all_detections.extend(detections1)
            logger.info(f"Loaded {len(detections1)} records from {file1.name}")
        else:
            logger.warning(f"UTC file not found: {file1.name}")

        if file2.exists():
            detections2 = self._read_csv(file2)
            all_detections.extend(detections2)
            logger.info(f"Loaded {len(detections2)} records from {file2.name}")
        else:
            logger.warning(f"UTC file not found: {file2.name} - "
                          "local date may be incomplete")

        if not all_detections:
            logger.error("No data found for the specified date")
            return None

        # Filter to only include the target local date
        local_filtered = self._filter_by_local_date(all_detections, local_date)
        logger.info(f"Filtered to {len(local_filtered)} records for local date "
                   f"{local_date.strftime('%Y-%m-%d')}")

        if not local_filtered:
            logger.warning("No detections found for the target local date")
            return None

        # Apply score threshold filtering
        score_filtered = self._filter_by_score(local_filtered)

        # Group and count by species
        species_counts = self._count_by_species(score_filtered)

        # Get top N
        top_species = self._get_top_species(species_counts)

        # Detect new/rare birds (use file1 as reference for historical lookup)
        new_birds = []
        if file1.exists():
            new_birds = self._detect_new_birds(file1, set(species_counts.keys()))

        result = {
            'local_date': local_date.strftime('%Y-%m-%d'),
            'box_name': box_name,
            'box_location': box_location,
            'utc_files': [f.name for f in [file1, file2] if f.exists()],
            'total_detections': len(local_filtered),
            'filtered_detections': len(score_filtered),
            'unique_species': len(species_counts),
            'top_species': top_species,
            'score_threshold': self.score_threshold,
            'new_birds': new_birds
        }

        # Add time-based analysis if requested
        if self.include_time_analysis:
            hour_counts = self._count_by_hour(score_filtered)
            species_time_ranges = self._get_species_time_ranges(score_filtered)
            time_summary = self._get_time_summary(hour_counts, species_time_ranges)
            result['hour_counts'] = hour_counts
            result['species_time_ranges'] = species_time_ranges
            result['time_summary'] = time_summary

        logger.info(f"Local date analysis complete: {len(species_counts)} species, "
                   f"{len(score_filtered)}/{len(local_filtered)} detections above threshold")

        return result
