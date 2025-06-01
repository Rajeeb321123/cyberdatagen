# cyberdata/scripts/validate_small.py

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Import process_llm_request from your utility module
from cyberdata.utils.llm_invoke import process_llm_request
from cyberdata.utils.logger_config import setup_logger
from cyberdata.utils.prompt_loader import load_prompt

# Set up logger
logger = setup_logger("cyberdata.scripts.validate_small")

# Add parent directory to path for imports
CURRENT_DIR = Path(__file__).parent
PROJECT_ROOT = CURRENT_DIR.parent.parent.parent
sys.path.append(str(CURRENT_DIR.parent))  # Add cyberdata package to path
logger.debug(f"Added {CURRENT_DIR.parent} to sys.path")

# Load environment variables
load_dotenv()

# Constants
MODEL_NAME = "gpt-4.1-mini"  # Match with small_dataset.py
PROBLEMS_UPDATED_PATH = CURRENT_DIR.parent / 'config' / 'problems_updated.json'
PROBLEMS_PATH = CURRENT_DIR.parent / 'config' / 'problems.json'
SEEDS_DIR = PROJECT_ROOT / 'data' / 'seeds'
VALIDATION_DIR = PROJECT_ROOT / 'data' / 'validation_reports'

logger.info(f"Using model: {MODEL_NAME}")
logger.info(f"Problems updated path: {PROBLEMS_UPDATED_PATH}")
logger.info(f"Problems fallback path: {PROBLEMS_PATH}")
logger.info(f"Seeds directory: {SEEDS_DIR}")
logger.info(f"Validation directory: {VALIDATION_DIR}")

VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
logger.info(f"Created validation directory: {VALIDATION_DIR}")


def load_problems(file_path: Path = None) -> list:
    """
    Load problem definitions from config, prioritizing problems_updated.json
    
    Args:
        file_path (Path, optional): Specific file path to load. If None, will auto-select.
    
    Returns:
        list: List of problems loaded from the appropriate file
    """
    # If specific file_path is provided, use it
    if file_path:
        if not file_path.exists():
            logger.error(f"Specified problems config not found: {file_path}")
            raise FileNotFoundError(f"Specified problems config not found: {file_path}")
        data = json.loads(file_path.read_text(encoding='utf-8'))
        problems = data.get('problems', [])
        logger.info(f"Loaded {len(problems)} problems from {file_path}")
        return problems
    
    # Auto-select: prioritize problems_updated.json, fallback to problems.json
    if PROBLEMS_UPDATED_PATH.exists():
        logger.info(f"Using updated problems file: {PROBLEMS_UPDATED_PATH}")
        try:
            data = json.loads(PROBLEMS_UPDATED_PATH.read_text(encoding='utf-8'))
            problems = data.get('problems', [])
            logger.info(f"Loaded {len(problems)} problems from {PROBLEMS_UPDATED_PATH}")
            return problems
        except Exception as e:
            logger.warning(f"Error loading updated problems file: {str(e)}")
            logger.info("Falling back to original problems.json")
    
    # Fallback to original problems.json
    if PROBLEMS_PATH.exists():
        logger.info(f"Using original problems file: {PROBLEMS_PATH}")
        try:
            data = json.loads(PROBLEMS_PATH.read_text(encoding='utf-8'))
            problems = data.get('problems', [])
            logger.info(f"Loaded {len(problems)} problems from {PROBLEMS_PATH}")
            return problems
        except Exception as e:
            logger.error(f"Error loading original problems file: {str(e)}", exc_info=True)
            raise
    
    # If neither file exists, raise an error
    logger.error(f"No problems config found. Checked: {PROBLEMS_UPDATED_PATH}, {PROBLEMS_PATH}")
    raise FileNotFoundError(f"No problems config found. Checked: {PROBLEMS_UPDATED_PATH}, {PROBLEMS_PATH}")


def validate_example(problem: dict, example: dict) -> dict:
    """
    Call the LLM to validate a single example.
    """
    logger.info(f"Validating example for problem: {problem['nature']}")
    
    # Load prompts from YAML using the prompt loader
    system_content = load_prompt(
        "validation_prompts",
        "prompts.seed_validation.system.template",
        area=problem['area'],
        nature=problem['nature'],
        description=problem.get('description', ''),
        risk_reduction=', '.join(problem.get('risk_reduction', []))
    )
    
    # Serialize example to JSON string
    example_json = json.dumps(example, indent=2)
    
    user_content = load_prompt(
        "validation_prompts",
        "prompts.seed_validation.user.template",
        example_json=example_json
    )
    
    # Use process_llm_request instead of direct model call
    logger.info(f"Calling LLM for validation")
    response_content = process_llm_request(
        system_prompt=system_content,
        user_prompt=user_content,
        model_name=MODEL_NAME,
        temperature=0.0  # Use 0 for consistent validation
    )
    
    logger.debug(f"Response received, length: {len(response_content)} characters")
    
    # Parse and return the JSON response
    try:
        # Clean up content by removing markdown code blocks if present
        if response_content.startswith('```'):
            logger.debug("Response starts with code block, cleaning up")
            # Find the first and last backtick groups
            first_backticks_end = response_content.find('\n', 3)
            if first_backticks_end != -1:
                # Find the closing backticks
                last_backticks_start = response_content.rfind('```')
                if last_backticks_start > first_backticks_end:
                    # Extract the content between the backticks
                    response_content = response_content[first_backticks_end + 1:last_backticks_start].strip()
                    logger.debug("Extracted content between backticks")
                else:
                    # Just remove the first backticks line if no closing backticks found
                    response_content = response_content[first_backticks_end + 1:].strip()
                    logger.debug("Removed first backticks line")
                    
        result = json.loads(response_content)
        logger.debug(f"Successfully parsed JSON response: valid={result.get('valid', False)}")
        return result
    except json.JSONDecodeError as e:
        # If parsing fails, wrap raw content
        logger.error(f"Failed to parse JSON response: {str(e)}")
        logger.debug(f"Raw response: {response_content[:100]}...")
        return {"valid": False, "issues": ["Invalid JSON response"], "comments": response_content}


def find_examples_file(problem):
    """
    Find the examples file for a specific problem.
    """
    area = problem['area']
    nature = problem['nature']
    
    # Create a sanitized version of area and nature for filename matching
    sanitized_area = area.replace(' ', '_').replace('(', '').replace(')', '').replace('-', '_')
    sanitized_nature = nature.replace(' ', '_')
    
    logger.debug(f"Looking for examples file for {sanitized_area}/{sanitized_nature}")
    
    # Check for the file in the area-specific directory
    area_dir = SEEDS_DIR / sanitized_area
    if area_dir.exists():
        filename = f"{sanitized_nature}_examples.json"
        example_file = area_dir / filename
        
        if example_file.exists():
            logger.debug(f"Found examples file: {example_file}")
            return example_file
    
    # If not found, try looking for the file in other area directories
    logger.debug("Examples file not found in expected location, searching all areas")
    for dir_path in SEEDS_DIR.glob('*'):
        if dir_path.is_dir():
            for file_path in dir_path.glob('*.json'):
                if sanitized_nature.lower() in file_path.name.lower():
                    logger.debug(f"Found examples file in alternative location: {file_path}")
                    return file_path
    
    logger.warning(f"No examples file found for {area}/{nature}")
    return None


def main():
    # Load problem definitions (auto-selects the appropriate file)
    logger.info("Starting validation of seed examples")
    problems = load_problems()
    
    for problem in problems:
        area = problem['area']
        nature = problem['nature']
        logger.info(f"Validating samples for problem: {area}/{nature}")
        
        # Find the examples file for this problem
        example_file_path = find_examples_file(problem)
        
        if not example_file_path:
            logger.warning(f"Examples file not found for problem {nature}, skipping.")
            continue
        
        # Load examples
        try:
            with example_file_path.open('r', encoding='utf-8') as f:
                examples_data = json.load(f)
                examples = examples_data.get('examples', [])
            
            logger.info(f"Loaded {len(examples)} examples from {example_file_path}")
        except Exception as e:
            logger.error(f"Error loading examples from {example_file_path}: {str(e)}", exc_info=True)
            continue
        
        if not examples:
            logger.warning(f"No examples found in {example_file_path}, skipping.")
            continue
            
        report = []
        for idx, example in enumerate(examples):
            logger.info(f"  Validating example {idx+1}/{len(examples)}...")
            
            result = validate_example(problem, example)
            
            entry = {
                "index": idx,
                "problem": {
                    "area": problem['area'],
                    "nature": nature
                },
                "example": example,
                "validation": result
            }
            report.append(entry)
            logger.debug(f"Added validation result for example {idx+1} to report")
        
        # Create area-specific directory structure for validation reports
        sanitized_area = area.replace(' ', '_').replace('(', '').replace(')', '').replace('-', '_')
        sanitized_nature = nature.replace(' ', '_')
        
        # Create area directory in validation reports
        area_validation_dir = VALIDATION_DIR / sanitized_area
        area_validation_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Created validation directory for area: {area_validation_dir}")
        
        # Create filename for the report
        report_filename = f"{sanitized_nature}_validation.json"
        
        # Save validation report
        report_path = area_validation_dir / report_filename
        with report_path.open('w', encoding='utf-8') as f:
            json.dump({"report": report}, f, indent=2)
        
        logger.info(f"Saved validation report for {area}/{nature} to {report_path}")

    logger.info("Completed validation of seed examples")


if __name__ == '__main__':
    main()