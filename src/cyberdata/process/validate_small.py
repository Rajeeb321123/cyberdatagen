import json
import os
import sys
from pathlib import Path
import csv
import re

from dotenv import load_dotenv

# Add parent directory to path for imports
CURRENT_DIR = Path(__file__).parent
if str(CURRENT_DIR.parent) not in sys.path:
    sys.path.append(str(CURRENT_DIR.parent))

# Import utilities
from cyberdata.utils.llm_invoke import process_llm_request
from cyberdata.utils.logger_config import setup_logger
from cyberdata.utils.prompt_loader import load_prompt
from cyberdata.utils.config_manager import get_config_manager

# # --- Mock implementations for standalone execution ---
# def process_llm_request(system_prompt, user_prompt, model_name, temperature):
#     logger.info(f"Mock LLM call for model {model_name} with temp {temperature}")
#     return """
#     ```json
#     {
#       "valid": true,
#       "issues": [],
#       "comments": "The example is well-formed, relevant to the problem description, and the answer is correct."
#     }
#     ```
#     """

# def setup_logger(name):
#     import logging
#     logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
#     return logging.getLogger(name)

# def load_prompt(name, template_path, **kwargs):
#     return f"Prompt from {name}/{template_path} with context: {kwargs}"
# # --- End of Mock implementations ---

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


def extract_json_from_response(response_content: str) -> dict:
    """Extract valid JSON from LLM response."""
    logger.debug("Extracting JSON from LLM response")
    
    pattern = r'```(?:json)?\s*([\s\S]*?)```'
    match = re.search(pattern, response_content)
    if match:
        content_to_parse = match.group(1)
    else:
        content_to_parse = response_content

    try:
        return json.loads(content_to_parse)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON: {e}")
        return {"valid": False, "issues": ["Invalid JSON response"], "comments": response_content}


from typing import Tuple

def validate_example(problem: dict, example: dict) -> Tuple[dict, str, str]:
    """
    Call the LLM to validate a single example and return the result and prompts.
    """
    logger.info(f"Validating example for problem: {problem['nature']}")
    
    system_prompt = load_prompt(
        "validation_prompts",
        "prompts.seed_validation.system.template",
        area=problem['area'],
        nature=problem['nature'],
        description=problem.get('description', ''),
        risk_reduction=', '.join(problem.get('risk_reduction', []))
    )
    
    example_json = json.dumps(example, indent=2)
    user_prompt = load_prompt(
        "validation_prompts",
        "prompts.seed_validation.user.template",
        example_json=example_json
    )
    
    logger.info(f"Calling LLM for validation")
    response_content = process_llm_request(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model_name=MODEL_NAME,
        temperature=0.0
    )
    
    result = extract_json_from_response(response_content)
    logger.debug(f"Successfully parsed JSON response: valid={result.get('valid', False)}")
    return result, system_prompt, user_prompt


def find_examples_file(problem):
    """Find the examples file for a specific problem."""
    expected_file = config_manager.get_seeds_file(problem['area'], problem['nature'])
    if expected_file.exists():
        return expected_file
    
    found_file = config_manager.find_existing_file(
        config_manager.seeds_dir, problem['nature'], "_examples.json"
    )
    if found_file:
        return found_file
    
    logger.warning(f"No examples file found for {problem['area']}/{problem['nature']}")
    return None


def save_validation_to_csv(system_prompt: str, user_prompt: str, validation_result: dict):
    """Save the prompts and validation result of a single call to a CSV log."""
    file_path = config_manager.data_dir / "validation.csv"
    file_exists = file_path.exists()

    try:
        with open(file_path, 'a', newline='', encoding='utf-8') as csvfile:
            headers = ["system", "user", "assistant"]
            writer = csv.DictWriter(csvfile, fieldnames=headers)

            if not file_exists:
                writer.writeheader()

            row = {
                "system": system_prompt,
                "user": user_prompt,
                "assistant": json.dumps(validation_result)
            }
            writer.writerow(row)
        logger.info(f"Appended validation log to {file_path}")
    except IOError as e:
        logger.error(f"Failed to write to validation CSV file: {e}")


def main():
    """Main function to validate seed examples"""
    logger.info("Starting validation of seed examples")
    problems = load_problems()
    
    for problem in problems:
        area = problem['area']
        nature = problem['nature']
        logger.info(f"--- Validating: {area}/{nature} ---")
        
        example_file_path = find_examples_file(problem)
        if not example_file_path:
            logger.warning(f"Examples file not found for {nature}, skipping.")
            continue
        
        try:
            examples_data = json.loads(example_file_path.read_text(encoding='utf-8'))
            examples = examples_data.get('examples', [])
            logger.info(f"Loaded {len(examples)} examples from {example_file_path}")
        except Exception as e:
            logger.error(f"Error loading examples from {example_file_path}: {e}", exc_info=True)
            continue
        
        if not examples:
            logger.warning(f"No examples found in {example_file_path}, skipping.")
            continue
            
        report = []
        for idx, example in enumerate(examples):
            logger.info(f"  Validating example {idx+1}/{len(examples)}...")
            
            try:
                result, system_prompt, user_prompt = validate_example(problem, example)
                
                # Save the interaction to the main CSV log
                save_validation_to_csv(system_prompt, user_prompt, result)
                
                # Append to the JSON report for this specific problem
                entry = {
                    "index": idx,
                    "problem": {"area": area, "nature": nature},
                    "example": example,
                    "validation": result
                }
                report.append(entry)
            except Exception as e:
                logger.error(f"An error occurred during validation for example {idx+1}: {e}", exc_info=True)

        # Save the detailed JSON report for this problem
        report_path = config_manager.get_validation_report_file(area, nature)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with report_path.open('w', encoding='utf-8') as f:
            json.dump({"report": report}, f, indent=2)
        
        logger.info(f"Saved JSON validation report for {area}/{nature} to {report_path}")

    logger.info("Completed validation of all seed examples.")


if __name__ == '__main__':
    main()
