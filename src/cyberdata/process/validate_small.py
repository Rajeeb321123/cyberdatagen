# cyberdata/scripts/validate_small.py

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Add parent directory to path for imports
CURRENT_DIR = Path(__file__).parent
sys.path.append(str(CURRENT_DIR.parent))  # Add cyberdata package to path

# Import utilities
from cyberdata.utils.llm_invoke import process_llm_request
from cyberdata.utils.logger_config import setup_logger
from cyberdata.utils.prompt_loader import load_prompt
from cyberdata.utils.config_manager import get_config_manager

# Set up logger
logger = setup_logger("cyberdata.scripts.validate_small")

# Load environment variables
load_dotenv()

# Constants
MODEL_NAME = "gpt-4.1-mini"

# Get config manager instance
config_manager = get_config_manager()

logger.info(f"Using model: {MODEL_NAME}")
logger.info(f"Project root: {config_manager.project_root}")
logger.info(f"Seeds directory: {config_manager.seeds_dir}")
logger.info(f"Validation directory: {config_manager.validation_reports_dir}")


def load_problems() -> list:
    """Load problem definitions using config manager"""
    return config_manager.load_problems()


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
    Find the examples file for a specific problem using config manager.
    """
    area = problem['area']
    nature = problem['nature']
    
    # First try the standard path
    expected_file = config_manager.get_seeds_file(area, nature)
    if expected_file.exists():
        logger.debug(f"Found examples file: {expected_file}")
        return expected_file
    
    # If not found, use the config manager's search function
    found_file = config_manager.find_existing_file(
        config_manager.seeds_dir, 
        nature, 
        "_examples.json"
    )
    
    if found_file:
        logger.debug(f"Found examples file in alternative location: {found_file}")
        return found_file
    
    logger.warning(f"No examples file found for {area}/{nature}")
    return None


def main():
    """Main function to validate seed examples"""
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
        
        # Get the validation report file path using config manager
        report_path = config_manager.get_validation_report_file(area, nature)
        
        # Ensure the directory exists
        report_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save validation report
        with report_path.open('w', encoding='utf-8') as f:
            json.dump({"report": report}, f, indent=2)
        
        logger.info(f"Saved validation report for {area}/{nature} to {report_path}")

    logger.info("Completed validation of seed examples")


if __name__ == '__main__':
    main()