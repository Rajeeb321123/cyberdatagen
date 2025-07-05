import json
import os
import sys
import re
from pathlib import Path
import csv

from dotenv import load_dotenv

# Add parent directory to path for imports
CURRENT_DIR = Path(__file__).parent
if str(CURRENT_DIR.parent) not in sys.path:
    sys.path.append(str(CURRENT_DIR.parent))

# Import utilities
from cyberdata.utils.llm_invoke import process_llm_request
from cyberdata.utils.logger_config import setup_logger
from cyberdata.utils.prompt_loader import load_system_prompt, load_user_prompt
from cyberdata.utils.config_manager import get_config_manager

# # --- Mock implementations for standalone execution ---
# def process_llm_request(system_prompt, user_prompt, model_name, temperature):
#     logger.info(f"Mock LLM call for model {model_name} with temp {temperature}")
#     return """
#     ```json
#     {
#       "examples": [
#         {
#           "scenario": "A hospital's network of infusion pumps, running on outdated firmware, is targeted by an attacker who alters medication dosages, putting patient lives at risk.",
#           "question": "What security controls could have prevented the unauthorized modification of the infusion pump settings?",
#           "options": {
#             "A": "Implementing network segmentation to isolate critical medical devices.",
#             "B": "Regularly updating firmware and patching known vulnerabilities.",
#             "C": "Using strong, unique credentials for device access instead of defaults.",
#             "D": "All of the above."
#           },
#           "answer": "D"
#         },
#         {
#           "scenario": "A smart home's thermostat is hacked, allowing an attacker to crank up the heat remotely, causing discomfort and high energy bills.",
#           "question": "Which of the following is the most likely vector for this attack?",
#           "options": {
#             "A": "A weak or default Wi-Fi password.",
#             "B": "A phishing email sent to the homeowner.",
#             "C": "Lack of physical security on the thermostat.",
#             "D": "A software vulnerability in the thermostat's cloud service."
#           },
#           "answer": "A"
#         }
#       ]
#     }
#     ```
#     """

# def setup_logger(name):
#     import logging
#     logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
#     return logging.getLogger(name)

# def load_system_prompt(name, **kwargs):
#     return f"System prompt for {name} with context: {kwargs}"

# def load_user_prompt(name, **kwargs):
#     return f"User prompt for {name} with context: {kwargs}"
# # --- End of Mock implementations ---

# Set up logger
logger = setup_logger("cyberdata.scripts.small_dataset")

# Load environment variables
load_dotenv()

# Get config manager instance
config_manager = get_config_manager()

# Model configuration
MODEL_NAME = "gpt-4.1-mini"

logger.info(f"Using model: {MODEL_NAME}")
logger.info(f"Project root: {config_manager.project_root}")
logger.info(f"Seeds directory: {config_manager.seeds_dir}")


def load_problems() -> list:
    """Load problem definitions using config manager"""
    return config_manager.load_problems()


def extract_json_from_response(response_content: str) -> list:
    """
    Extract a list of examples from an LLM response string.
    """
    logger.debug("Extracting JSON from LLM response")
    
    # First, try to find a markdown code block
    pattern = r'```(?:json)?\s*([\s\S]*?)```'
    match = re.search(pattern, response_content)
    if match:
        content_to_parse = match.group(1)
        logger.debug("Found content in markdown block.")
    else:
        content_to_parse = response_content
        logger.debug("No markdown block found, attempting to parse whole response.")

    try:
        # Try parsing the content
        data = json.loads(content_to_parse)
        # The response might be a dict with an 'examples' key, or just the list itself
        if isinstance(data, dict) and 'examples' in data:
            return data['examples']
        elif isinstance(data, list):
            return data
        else:
            logger.warning("Parsed JSON is not a list or a dict with an 'examples' key.")
            return []
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON from response: {e}")
        logger.debug(f"Content that failed parsing: {content_to_parse[:200]}...")
        raise ValueError("Could not extract valid JSON from model response")


def generate_examples_for_problem(problem: dict) -> tuple[list, str, str]:
    """Generate examples for a problem and return them along with the prompts used."""
    logger.info(f"Generating examples for problem: {problem['area']}/{problem['nature']}")
    
    system_prompt = load_system_prompt(
        "seed_generation_prompts",
        area=problem['area'],
        nature=problem['nature'],
        description=problem.get('description', ''),
        risk_reduction=', '.join(problem.get('risk_reduction', []))
    )
    
    user_prompt = load_user_prompt("seed_generation_prompts")
    
    logger.info(f"Calling LLM for problem: {problem['nature']}")
    response_content = process_llm_request(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model_name=MODEL_NAME,
        temperature=0.7
    )
    
    logger.info(f"Response received for {problem['nature']}, length: {len(response_content)} characters")
    
    try:
        examples = extract_json_from_response(response_content)
        logger.info(f"Successfully extracted {len(examples)} examples for {problem['nature']}")
        return examples, system_prompt, user_prompt
    except Exception as e:
        logger.error(f"JSON parse error for {problem['nature']}: {str(e)}")
        return [], system_prompt, user_prompt


def save_examples_to_json(problem: dict, examples: list):
    """Save examples to a JSON file."""
    if not examples:
        logger.warning(f"No valid examples to save to JSON for {problem['nature']}")
        return
    
    file_path = config_manager.get_seeds_file(problem['area'], problem['nature'])
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    with file_path.open('w', encoding='utf-8') as f:
        json.dump({'examples': examples}, f, indent=2)
    logger.info(f"Saved {len(examples)} examples to JSON: {file_path}")


def save_examples_to_csv(problem: dict, examples: list, system_prompt: str, user_prompt: str):
    """Save the problem, prompts, and generated examples to a single CSV file."""
    if not examples:
        logger.warning(f"No valid examples to save to CSV for {problem['nature']}")
        return

    file_path = config_manager.data_dir / "small_dataset.csv"
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
                # "problem": json.dumps(problem),
                "assistant": json.dumps(examples)
            }
            writer.writerow(row)
        logger.info(f"Appended examples for {problem['nature']} to CSV: {file_path}")
    except IOError as e:
        logger.error(f"Failed to write to CSV file {file_path}: {e}")


def main():
    """Main function to generate examples for all problems"""
    logger.info("Starting seed examples generation")
    problems = load_problems()
    
    logger.info(f"Found {len(problems)} problems to process.")
    
    for problem in problems:
        try:
            logger.info(f"Processing problem: {problem['area']}/{problem['nature']}")
            examples, system_prompt, user_prompt = generate_examples_for_problem(problem)
            
            # Save to individual JSON file (original functionality)
            save_examples_to_json(problem, examples)
            
            # Save to the main CSV file (new functionality)
            save_examples_to_csv(problem, examples, system_prompt, user_prompt)

        except Exception as e:
            logger.error(f"Error processing {problem.get('area')}/{problem.get('nature')}: {e}", exc_info=True)
            continue

    logger.info(f"All detailed examples have been generated and saved.")
    logger.info(f"Individual JSON files are in '{config_manager.seeds_dir}'.")
    logger.info(f"Aggregated CSV is at '{config_manager.data_dir / 'small_dataset.csv'}'.")


if __name__ == '__main__':
    main()
