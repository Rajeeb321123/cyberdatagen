# cyberdata/utils/prompt_loader.py

import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List
from functools import lru_cache
import logging

from cyberdata.utils.logger_config import setup_logger

# Set up logger
logger = setup_logger("cyberdata.utils.prompt_loader")

# Get the config directory path
CURRENT_DIR = Path(__file__).parent  # utils/
CYBERDATA_DIR = CURRENT_DIR.parent   # src/cyberdata/
PROMPTS_DIR = CYBERDATA_DIR / "config" / "prompts"

# Cache for loaded prompts
_prompt_cache: Dict[str, Dict[str, Any]] = {}


class PromptLoader:
    """
    Utility class for loading and managing YAML prompt files.
    
    This class provides functionality to:
    - Load prompts from YAML files
    - Cache loaded prompts for performance
    - Support variable substitution in prompts
    - Validate required variables
    - Handle missing files gracefully
    """
    
    def __init__(self, prompts_dir: Optional[Path] = None):
        """
        Initialize the PromptLoader.
        
        Args:
            prompts_dir (Optional[Path]): Directory containing prompt YAML files.
                                        Defaults to src/cyberdata/config/prompts/
        """
        self.prompts_dir = prompts_dir or PROMPTS_DIR
        logger.info(f"PromptLoader initialized with directory: {self.prompts_dir}")
        
        # Ensure prompts directory exists
        if not self.prompts_dir.exists():
            logger.warning(f"Prompts directory does not exist: {self.prompts_dir}")
            self.prompts_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created prompts directory: {self.prompts_dir}")
    
    @lru_cache(maxsize=32)
    def load_prompt_file(self, filename: str) -> Dict[str, Any]:
        """
        Load a YAML prompt file and cache the result.
        
        Args:
            filename (str): Name of the YAML file (with or without .yaml extension)
            
        Returns:
            Dict[str, Any]: Parsed YAML content
            
        Raises:
            FileNotFoundError: If the prompt file doesn't exist
            yaml.YAMLError: If the YAML file is invalid
        """
        # Add .yaml extension if not present
        if not filename.endswith('.yaml'):
            filename = f"{filename}.yaml"
        
        filepath = self.prompts_dir / filename
        
        # Check cache first
        cache_key = str(filepath)
        if cache_key in _prompt_cache:
            logger.debug(f"Loading cached prompts from: {filename}")
            return _prompt_cache[cache_key]
        
        # Load from file
        if not filepath.exists():
            logger.error(f"Prompt file not found: {filepath}")
            raise FileNotFoundError(f"Prompt file not found: {filepath}")
        
        try:
            logger.info(f"Loading prompts from: {filepath}")
            with filepath.open('r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            # Cache the loaded data
            _prompt_cache[cache_key] = data
            logger.debug(f"Successfully loaded and cached prompts from: {filename}")
            return data
            
        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML file {filepath}: {str(e)}")
            raise
    
    def get_prompt(self, 
                   filename: str, 
                   prompt_path: str, 
                   variables: Optional[Dict[str, Any]] = None) -> str:
        """
        Get a specific prompt from a YAML file and substitute variables.
        
        Args:
            filename (str): Name of the YAML file
            prompt_path (str): Dot-separated path to the prompt (e.g., "prompts.system.template")
            variables (Optional[Dict[str, Any]]): Variables to substitute in the prompt
            
        Returns:
            str: The prompt with variables substituted
            
        Raises:
            KeyError: If the prompt path doesn't exist
            ValueError: If required variables are missing
        """
        # Load the prompt file
        data = self.load_prompt_file(filename)
        
        # Navigate to the prompt using the path
        prompt = self._navigate_path(data, prompt_path)
        
        if not isinstance(prompt, str):
            raise ValueError(f"Prompt at path '{prompt_path}' is not a string")
        
        # Get variable requirements if specified
        variables_path = prompt_path.replace('.template', '.variables')
        required_vars = self._navigate_path(data, variables_path, default=[])
        
        # Validate and substitute variables
        if variables:
            prompt = self._substitute_variables(prompt, variables, required_vars)
        elif required_vars:
            logger.warning(f"Prompt requires variables but none provided: {required_vars}")
        
        return prompt
    
    def _navigate_path(self, data: Dict[str, Any], path: str, default: Any = None) -> Any:
        """
        Navigate a nested dictionary using dot notation.
        
        Args:
            data (Dict[str, Any]): The dictionary to navigate
            path (str): Dot-separated path (e.g., "prompts.system.template")
            default (Any): Default value if path doesn't exist
            
        Returns:
            Any: The value at the path or default
        """
        try:
            current = data
            for key in path.split('.'):
                current = current[key]
            return current
        except (KeyError, TypeError):
            if default is not None:
                return default
            raise KeyError(f"Path '{path}' not found in data")
    
    def _substitute_variables(self, 
                            template: str, 
                            variables: Dict[str, Any], 
                            required_vars: List[str]) -> str:
        """
        Substitute variables in a template string.
        
        Args:
            template (str): The template string with {variable} placeholders
            variables (Dict[str, Any]): Variables to substitute
            required_vars (List[str]): List of required variable names
            
        Returns:
            str: The template with variables substituted
            
        Raises:
            ValueError: If required variables are missing
        """
        # Check for required variables
        missing_vars = set(required_vars) - set(variables.keys())
        if missing_vars:
            raise ValueError(f"Missing required variables: {missing_vars}")
        
        # Perform substitution
        try:
            # Convert list values to comma-separated strings
            formatted_vars = {}
            for key, value in variables.items():
                if isinstance(value, list):
                    formatted_vars[key] = ', '.join(str(v) for v in value)
                else:
                    formatted_vars[key] = str(value)
            
            result = template.format(**formatted_vars)
            logger.debug(f"Successfully substituted {len(variables)} variables in template")
            return result
            
        except KeyError as e:
            logger.error(f"Variable substitution error: {str(e)}")
            raise ValueError(f"Template requires variable that wasn't provided: {str(e)}")
    
    def get_system_prompt(self, filename: str, prompt_name: str = None, **kwargs) -> str:
        """
        Convenience method to get a system prompt.
        
        Args:
            filename (str): Name of the YAML file
            prompt_name (str): Optional specific prompt name if file has multiple prompts
            **kwargs: Variables to substitute
            
        Returns:
            str: The system prompt
        """
        if prompt_name:
            path = f"prompts.{prompt_name}.system.template"
        else:
            path = "prompts.system.template"
        
        return self.get_prompt(filename, path, kwargs)
    
    def get_user_prompt(self, filename: str, prompt_name: str = None, **kwargs) -> str:
        """
        Convenience method to get a user prompt.
        
        Args:
            filename (str): Name of the YAML file
            prompt_name (str): Optional specific prompt name if file has multiple prompts
            **kwargs: Variables to substitute
            
        Returns:
            str: The user prompt
        """
        if prompt_name:
            path = f"prompts.{prompt_name}.user.template"
        else:
            path = "prompts.user.template"
        
        return self.get_prompt(filename, path, kwargs)
    
    def get_metadata(self, filename: str) -> Dict[str, Any]:
        """
        Get metadata from a prompt file.
        
        Args:
            filename (str): Name of the YAML file
            
        Returns:
            Dict[str, Any]: Metadata dictionary
        """
        data = self.load_prompt_file(filename)
        metadata = {}
        
        # Extract common metadata fields
        for field in ['version', 'description', 'author', 'last_updated', 'metadata']:
            if field in data:
                metadata[field] = data[field]
        
        return metadata
    
    def clear_cache(self):
        """Clear the prompt cache."""
        _prompt_cache.clear()
        self.load_prompt_file.cache_clear()
        logger.info("Prompt cache cleared")


# Global instance for convenience
_default_loader = None


def get_prompt_loader() -> PromptLoader:
    """
    Get the default PromptLoader instance.
    
    Returns:
        PromptLoader: The default prompt loader
    """
    global _default_loader
    if _default_loader is None:
        _default_loader = PromptLoader()
    return _default_loader


# Convenience functions using the default loader
def load_prompt(filename: str, prompt_path: str, **variables) -> str:
    """
    Load a prompt using the default loader.
    
    Args:
        filename (str): Name of the YAML file
        prompt_path (str): Dot-separated path to the prompt
        **variables: Variables to substitute
        
    Returns:
        str: The prompt with variables substituted
    """
    return get_prompt_loader().get_prompt(filename, prompt_path, variables)


def load_system_prompt(filename: str, prompt_name: str = None, **variables) -> str:
    """
    Load a system prompt using the default loader.
    
    Args:
        filename (str): Name of the YAML file
        prompt_name (str): Optional specific prompt name
        **variables: Variables to substitute
        
    Returns:
        str: The system prompt
    """
    return get_prompt_loader().get_system_prompt(filename, prompt_name, **variables)


def load_user_prompt(filename: str, prompt_name: str = None, **variables) -> str:
    """
    Load a user prompt using the default loader.
    
    Args:
        filename (str): Name of the YAML file
        prompt_name (str): Optional specific prompt name
        **variables: Variables to substitute
        
    Returns:
        str: The user prompt
    """
    return get_prompt_loader().get_user_prompt(filename, prompt_name, **variables)