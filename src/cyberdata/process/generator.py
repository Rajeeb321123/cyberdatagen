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
from cyberdata.utils.prompt_loader import load_prompt
from cyberdata.utils.config_manager import get_config_manager

# # --- Mock implementations for standalone execution ---
# def process_llm_request(system_prompt, user_prompt, model_name, temperature):
#     logger.info(f"Mock LLM call for model {model_name} with temp {temperature}")
#     return """
#     ```json
#     {
#       "samples": [
#         {
#           "scenario": "An employee finds a USB drive labeled 'Q3 Financials' in the office parking lot and plugs it into their corporate laptop, unknowingly installing malware.",
#           "question": "This attack vector is a classic example of what?",
#           "options": {
#             "A": "Baiting",
#             "B": "Tailgating",
#             "C": "Watering Hole Attack",
#             "D": "Denial of Service"
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

# def load_prompt(name, template_path, **kwargs):
#     return f"Prompt from {name}/{template_path} with context: {kwargs}"
# # --- End of Mock implementations ---

# Set up logger
logger = setup_logger("cyberdata.scripts.generator")

# Load environment variables
load_dotenv()

# Constants
MODEL_NAME = "gpt-4.1-mini"

# Get config manager instance
config_manager = get_config_manager()

logger.info(f"Using model: {MODEL_NAME}")
logger.info(f"Project root: {config_manager.project_root}")
logger.info(f"Seeds directory: {config_manager.seeds_dir}")
logger.info(f"Output directory: {config_manager.large_samples_dir}")


def load_problems() -> list:
    """Load problem definitions using config manager"""
    return config_manager.load_problems()


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


def load_examples(problem: dict) -> list:
    """Load few-shot examples for a given problem."""
    example_file = find_examples_file(problem)
    if not example_file:
        raise FileNotFoundError(f"Examples file not found for {problem['area']}/{problem['nature']}")
    
    data = json.loads(example_file.read_text(encoding='utf-8'))
    examples = data.get('examples', [])
    logger.info(f"Loaded {len(examples)} examples from {example_file}")
    return examples


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
        logger.debug(f"Content that failed parsing: {content_to_parse[:200]}...")
        return {"samples": []} # Return empty structure on failure


def save_generation_log_to_csv(system_prompt: str, user_prompt: str, samples: list):
    """Save the prompts and generated samples of a single LLM call to a CSV log."""
    if not samples:
        logger.warning("No samples generated in this batch, skipping CSV log.")
        return

    file_path = config_manager.data_dir / "generator.csv"
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
                "assistant": json.dumps(samples)
            }
            writer.writerow(row)
        logger.info(f"Appended generation log to {file_path}")
    except IOError as e:
        logger.error(f"Failed to write to generator CSV file: {e}")


# def generate_in_batches(problem: dict, examples: list, total_count: int = 10, batch_size: int = 2) -> list:
def generate_in_batches(problem: dict, examples: list, total_count: int = 4, batch_size: int = 2) -> list:
    """Generate samples in multiple batches."""
    logger.info(f"Generating {total_count} samples in batches of {batch_size} for {problem['nature']}")
    all_samples = []
    remaining = total_count
    
    # examples_json = json.dumps(examples[:2], indent=2)
    examples_json = json.dumps(examples[:1], indent=2)
    
    while remaining > 0:
        current_batch_size = min(batch_size, remaining)
        logger.info(f"Generating batch of {current_batch_size} samples...")
        
        system_content = load_prompt("large_generation_prompts", "prompts.generation.system.template")
        user_content = load_prompt(
            "large_generation_prompts",
            "prompts.generation.user.template",
            nature=problem['nature'],
            area=problem['area'],
            description=problem.get('description', ''),
            examples_json=examples_json,
            count=current_batch_size
        )
        
        response_content = process_llm_request(
            system_prompt=system_content,
            user_prompt=user_content,
            model_name=MODEL_NAME,
            temperature=0.7
        )
        
        parsed = extract_json_from_response(response_content)
        samples = parsed.get('samples', [])
        
        if samples:
            save_generation_log_to_csv(system_content, user_content, samples)
            all_samples.extend(samples)
            logger.info(f"Generated {len(samples)} samples, total now: {len(all_samples)}")
        else:
            logger.warning("Failed to generate samples in this batch.")
        
        remaining -= current_batch_size
        if len(all_samples) >= total_count:
            break
    
    return all_samples[:total_count]


# def generate_for_problem(problem: dict, n: int = 10) -> list:
def generate_for_problem(problem: dict, n: int = 4) -> list:
    """Generate n synthetic samples for the given problem."""
    try:
        examples = load_examples(problem)
        if not examples:
            logger.warning(f"No seed examples found for {problem['area']}/{problem['nature']}")
            return []
        
        # return generate_in_batches(problem, examples, n, batch_size=5)
        return generate_in_batches(problem, examples, n, batch_size=2)
    except Exception as e:
        logger.error(f"Error generating samples for {problem['nature']}: {e}", exc_info=True)
        return []


def save_samples(problem: dict, samples: list):
    """Save generated samples to a JSON file, appending to existing ones."""
    if not samples:
        logger.warning(f"No samples to save for {problem['nature']}")
        return
    
    out_file = config_manager.get_large_samples_file(problem['area'], problem['nature'])
    out_file.parent.mkdir(parents=True, exist_ok=True)
    
    existing_samples = []
    if out_file.exists():
        try:
            existing_data = json.loads(out_file.read_text(encoding='utf-8'))
            existing_samples = existing_data.get('samples', [])
        except json.JSONDecodeError:
            logger.error(f"Could not parse existing samples file: {out_file}")

    all_samples = existing_samples + samples
    with out_file.open('w', encoding='utf-8') as f:
        json.dump({'samples': all_samples}, f, indent=2)
    
    logger.info(f"Saved {len(samples)} new samples (total: {len(all_samples)}) to {out_file}")


# def main(count: int = 10, problem_filter: list = None):
def main(count: int = 4, problem_filter: list = None):
    """Main function to generate samples for all problems."""
    logger.info(f"Starting sample generation with count={count}")
    problems = load_problems()
    
    if problem_filter:
        problems = [p for p in problems if p['nature'] in problem_filter]
        if not problems:
            logger.error(f"No matching problems found for filter: {problem_filter}")
            return
    
    for problem in problems:
        logger.info(f"\n--- Processing: {problem['area']}/{problem['nature']} ---")
        try:
            samples = generate_for_problem(problem, count)
            if samples:
                save_samples(problem, samples)
            else:
                logger.warning(f"No samples were generated for {problem['nature']}.")
        except Exception as e:
            logger.error(f"An unhandled error occurred while processing {problem['nature']}: {e}", exc_info=True)
    
    logger.info("Sample generation process completed!")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate synthetic cybersecurity data samples")
    # parser.add_argument('--count', type=int, default=10, help='Number of samples to generate per problem')
    parser.add_argument('--count', type=int, default=4, help='Number of samples to generate per problem')
    parser.add_argument('--problems', nargs='+', help='Specific problem natures to generate for')
    
    args = parser.parse_args()
    
    main(args.count, args.problems)
