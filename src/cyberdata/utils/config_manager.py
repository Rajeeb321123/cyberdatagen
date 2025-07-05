# cyberdata/utils/config_manager.py

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, Union
from functools import lru_cache

from cyberdata.utils.logger_config import setup_logger

# Set up logger
logger = setup_logger("cyberdata.utils.config_manager")


class ConfigManager:
    """
    Centralized configuration manager for the CyberData project.
    
    This class provides a single point of access for all configuration files,
    data directories, and project paths. It automatically handles path resolution
    and provides consistent access patterns across all modules.
    """
    
    def __init__(self, project_root: Optional[Path] = None):
        """
        Initialize the ConfigManager.
        
        Args:
            project_root (Optional[Path]): Override the auto-detected project root
        """
        # Auto-detect project root if not provided
        if project_root is None:
            # Start from this file and work upward to find pyproject.toml
            current = Path(__file__).parent
            while current.parent != current:  # Stop at filesystem root
                if (current / "pyproject.toml").exists():
                    project_root = current
                    break
                current = current.parent
            
            if project_root is None:
                # Fallback: assume standard structure
                project_root = Path(__file__).parent.parent.parent.parent
        
        self.project_root = Path(project_root).resolve()
        logger.info(f"ConfigManager initialized with project root: {self.project_root}")
        
        # Define all standard directories
        self._setup_directories()
        self._validate_structure()
    
    def _setup_directories(self):
        """Set up all standard project directories."""
        # Core directories
        self.config_dir = self.project_root / "config"
        self.data_dir = self.project_root / "data"
        self.logs_dir = self.project_root / "logs"
        self.src_dir = self.project_root / "src"
        
        # Config subdirectories
        self.prompts_dir = self.config_dir / "prompts"
        
        # Data subdirectories
        self.seeds_dir = self.data_dir / "seeds"
        self.large_samples_dir = self.data_dir / "large_samples"
        self.validation_reports_dir = self.data_dir / "validation_reports"
        self.quality_reports_dir = self.data_dir / "quality_reports"
        
        # Create directories if they don't exist
        for dir_path in [
            self.config_dir, self.data_dir, self.logs_dir,
            self.prompts_dir, self.seeds_dir, self.large_samples_dir,
            self.validation_reports_dir, self.quality_reports_dir
        ]:
            dir_path.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Ensured directory exists: {dir_path}")
    
    def _validate_structure(self):
        """Validate that the project structure looks correct."""
        required_files = [
            self.project_root / "pyproject.toml",
            self.project_root / "README.md"
        ]
        
        for file_path in required_files:
            if not file_path.exists():
                logger.warning(f"Expected file not found: {file_path}")
    
    # === Config File Methods ===
    
    @lru_cache(maxsize=32)
    def load_config_file(self, filename: str, required: bool = True) -> Dict[str, Any]:
        """
        Load a JSON configuration file.
        
        Args:
            filename (str): Name of the config file (with or without .json extension)
            required (bool): Whether the file is required to exist
            
        Returns:
            Dict[str, Any]: Parsed JSON content
            
        Raises:
            FileNotFoundError: If required file doesn't exist
        """
        if not filename.endswith('.json'):
            filename = f"{filename}.json"
        
        file_path = self.config_dir / filename
        
        if not file_path.exists():
            if required:
                logger.error(f"Required config file not found: {file_path}")
                raise FileNotFoundError(f"Required config file not found: {file_path}")
            else:
                logger.warning(f"Optional config file not found: {file_path}")
                return {}
        
        try:
            logger.debug(f"Loading config file: {file_path}")
            with file_path.open('r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in config file {file_path}: {str(e)}")
            raise
    
    def save_config_file(self, filename: str, data: Dict[str, Any]) -> Path:
        """
        Save data to a JSON configuration file.
        
        Args:
            filename (str): Name of the config file
            data (Dict[str, Any]): Data to save
            
        Returns:
            Path: Path to the saved file
        """
        if not filename.endswith('.json'):
            filename = f"{filename}.json"
        
        file_path = self.config_dir / filename
        
        try:
            with file_path.open('w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved config file: {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"Error saving config file {file_path}: {str(e)}")
            raise
    
    # === Problem Management ===
    
    def load_problems(self, prefer_updated: bool = True) -> list:
        """
        Load problem definitions, with automatic fallback logic.
        
        Args:
            prefer_updated (bool): Whether to prefer problems_updated.json over problems.json
            z
        Returns:
            list: List of problems
        """
        if prefer_updated:
            # Try updated problems first
            try:
                data = self.load_config_file("problems_updated", required=False)
                if data and 'problems' in data:
                    problems = data['problems']
                    logger.info(f"Loaded {len(problems)} problems from problems_updated.json")
                    return problems
            except Exception as e:
                logger.warning(f"Error loading problems_updated.json: {str(e)}")
        
        # Fallback to original problems
        try:
            data = self.load_config_file("problems", required=True)
            problems = data.get('problems', [])
            logger.info(f"Loaded {len(problems)} problems from problems.json")
            return problems
        except FileNotFoundError:
            # Try problems_init as final fallback
            logger.warning("problems.json not found, trying problems_init.json")
            data = self.load_config_file("problems_init", required=True)
            problems = data.get('problems', [])
            logger.info(f"Loaded {len(problems)} problems from problems_init.json")
            return problems
    
    def save_problems(self, problems: list, filename: str = "problems") -> Path:
        """
        Save problems to a configuration file.
        
        Args:
            problems (list): List of problems to save
            filename (str): Base filename (without .json extension)
            
        Returns:
            Path: Path to the saved file
        """
        data = {"problems": problems}
        return self.save_config_file(filename, data)
    
    # === Data File Helpers ===
    
    def get_seeds_file(self, area: str, nature: str) -> Path:
        """Get the path for a seeds file."""
        sanitized_area = self._sanitize_name(area)
        sanitized_nature = self._sanitize_name(nature)
        return self.seeds_dir / sanitized_area / f"{sanitized_nature}_examples.json"
    
    def get_large_samples_file(self, area: str, nature: str) -> Path:
        """Get the path for a large samples file."""
        sanitized_area = self._sanitize_name(area)
        sanitized_nature = self._sanitize_name(nature)
        return self.large_samples_dir / sanitized_area / f"{sanitized_nature}_large.json"
    
    def get_validation_report_file(self, area: str, nature: str) -> Path:
        """Get the path for a validation report file."""
        sanitized_area = self._sanitize_name(area)
        sanitized_nature = self._sanitize_name(nature)
        return self.validation_reports_dir / sanitized_area / f"{sanitized_nature}_validation.json"
    
    def get_quality_report_file(self, area: str, nature: str) -> Path:
        """Get the path for a quality report file."""
        sanitized_area = self._sanitize_name(area)
        sanitized_nature = self._sanitize_name(nature)
        return self.quality_reports_dir / sanitized_area / f"{sanitized_nature}_quality_report.json"
    
    def find_existing_file(self, base_dir: Path, nature: str, suffix: str = "") -> Optional[Path]:
        """
        Find an existing file by searching through area subdirectories.
        
        Args:
            base_dir (Path): Base directory to search in
            nature (str): Nature identifier to search for
            suffix (str): File suffix (e.g., "_examples.json")
            
        Returns:
            Optional[Path]: Path to the file if found, None otherwise
        """
        sanitized_nature = self._sanitize_name(nature)
        
        # Search through all subdirectories
        for area_dir in base_dir.glob('*'):
            if area_dir.is_dir():
                for file_path in area_dir.glob('*.json'):
                    if sanitized_nature.lower() in file_path.name.lower():
                        if not suffix or suffix in file_path.name:
                            logger.debug(f"Found existing file: {file_path}")
                            return file_path
        
        return None
    
    def _sanitize_name(self, name: str) -> str:
        """Sanitize a name for use in filenames and directory names."""
        return name.replace(' ', '_').replace('(', '').replace(')', '').replace('-', '_')
    
    # === Convenience Properties ===
    
    @property
    def problems_file(self) -> Path:
        """Path to the main problems.json file."""
        return self.config_dir / "problems.json"
    
    @property
    def problems_updated_file(self) -> Path:
        """Path to the problems_updated.json file."""
        return self.config_dir / "problems_updated.json"
    
    @property
    def problems_init_file(self) -> Path:
        """Path to the problems_init.json file."""
        return self.config_dir / "problems_init.json"
    
    @property
    def acronyms_file(self) -> Path:
        """Path to the acronyms.json file."""
        return self.config_dir / "acronyms.json"
    
    def clear_cache(self):
        """Clear the configuration cache."""
        self.load_config_file.cache_clear()
        logger.info("Configuration cache cleared")


# Global instance for convenience
_default_config_manager = None


def get_config_manager() -> ConfigManager:
    """
    Get the default ConfigManager instance.
    
    Returns:
        ConfigManager: The default config manager
    """
    global _default_config_manager
    if _default_config_manager is None:
        _default_config_manager = ConfigManager()
    return _default_config_manager


# Convenience functions
def get_project_root() -> Path:
    """Get the project root directory."""
    return get_config_manager().project_root


def get_config_dir() -> Path:
    """Get the config directory."""
    return get_config_manager().config_dir


def get_data_dir() -> Path:
    """Get the data directory."""
    return get_config_manager().data_dir


def load_problems(prefer_updated: bool = True) -> list:
    """Load problems using the default config manager."""
    return get_config_manager().load_problems(prefer_updated)


def save_problems(problems: list, filename: str = "problems") -> Path:
    """Save problems using the default config manager."""
    return get_config_manager().save_problems(problems, filename)