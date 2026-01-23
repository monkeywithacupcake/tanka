"""Configuration management for Tanka"""

import os
import yaml
from pathlib import Path
from typing import Dict, List, Any


class Config:
    """Handles loading and accessing configuration"""

    def __init__(self, config_path: str = None):
        """
        Initialize configuration

        Args:
            config_path: Path to YAML config file. Defaults to config/haikuboxes.yaml
        """
        if config_path is None:
            # Default to config/haikuboxes.yaml relative to project root
            project_root = Path(__file__).parent.parent
            config_path = project_root / "config" / "haikuboxes.yaml"

        self.config_path = Path(config_path)
        self.config_data = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")

        with open(self.config_path, 'r') as f:
            return yaml.safe_load(f)

    def get_haikuboxes(self, enabled_only: bool = True) -> List[Dict[str, Any]]:
        """
        Get list of configured HaikuBoxes

        Args:
            enabled_only: If True, only return enabled HaikuBoxes

        Returns:
            List of HaikuBox configurations
        """
        boxes = self.config_data.get('haikuboxes', [])
        if enabled_only:
            return [box for box in boxes if box.get('enabled', False)]
        return boxes

    def get_setting(self, key: str, default: Any = None) -> Any:
        """
        Get a setting value

        Args:
            key: Setting key
            default: Default value if key not found

        Returns:
            Setting value
        """
        return self.config_data.get('settings', {}).get(key, default)

    def get_download_dir(self) -> Path:
        """Get download directory as Path object"""
        project_root = Path(__file__).parent.parent
        download_dir = self.get_setting('download_dir', './downloads')

        # Convert to absolute path
        if not Path(download_dir).is_absolute():
            download_dir = project_root / download_dir

        # Create directory if it doesn't exist
        Path(download_dir).mkdir(parents=True, exist_ok=True)

        return Path(download_dir)

    def is_headless(self) -> bool:
        """Check if browser should run in headless mode"""
        return self.get_setting('headless', True)

    def get_download_timeout(self) -> int:
        """Get download timeout in seconds"""
        return self.get_setting('download_timeout', 60)

    def get_log_level(self) -> str:
        """Get logging level"""
        return self.get_setting('log_level', 'INFO')

    def get_auth_credentials(self) -> Dict[str, str]:
        """
        Get authentication credentials

        Returns:
            Dictionary with 'email' and 'password' keys
        """
        auth = self.get_setting('auth', {})
        return {
            'email': auth.get('email', ''),
            'password': auth.get('password', '')
        }

    def get_analysis_settings(self) -> Dict[str, Any]:
        """
        Get analysis settings

        Returns:
            Dictionary with analysis configuration
        """
        analysis = self.get_setting('analysis', {})
        return {
            'score_threshold': analysis.get('score_threshold', 0.5),
            'top_n': analysis.get('top_n', 10),
            'exclude_species': analysis.get('exclude_species', [])
        }
