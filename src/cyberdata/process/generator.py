# cyberdata/scripts/generator.py

import json
import os
import sys
import re
from pathlib import Path

from dotenv import load_dotenv

# Add parent directory to path for imports
CURRENT_DIR = Path(__file__).parent
PROJECT_ROOT = CURRENT_DIR.parent.parent.parent
sys.path.append(str(CURRENT_DIR.parent))  # Add cyberdata package to path

# Import process_llm_request from utility module
from cyberdata.utils.llm_invoke import process_llm_request
from cyberdata.utils.logger_config import setup_logger
from cyberdata.utils.prompt_loader import load_prompt

# Set up logger
logger = setup_logger("cyberdata.scripts.generator")

# Load environment variables
load_dotenv()

# Constants and paths
MODEL_NAME = "gpt-4.1-mini"  # Match with small_dataset.py
PROBLEMS_UPDATED_PATH = CURRENT_DIR.parent / 'config' / 'problems_updated.json'
PROBLEMS_PATH = CURRENT_DIR.parent / 'config' / 'problems.json'
SEEDS_DIR = PROJECT_ROOT / 'data' / 'seeds'
OUTPUT_DIR = PROJECT_ROOT / 'data' / 'large_samples'

logger.info(f"Using model: {MODEL_NAME}")
logger.info(f"Problems updated path: {PROBLEMS_UPDATED_PATH}")
logger.info(f"Problems fallback path: {PROBLEMS_PATH}")
logger.info(f"Seeds directory: {SEEDS_DIR}")
logger.info(f"Output directory: {OUTPUT_DIR}")

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
logger.info(f"Created output directory: {OUTPUT_DIR}")


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


def load_examples(problem: dict) -> list:
    """
    Load few-shot examples for a given problem.
    
    Args:
        problem (dict): The problem dictionary containing 'area' and 'nature'
    
    Returns:
        list: The examples for the given problem
    """
    example_file = find_examples_file(problem)
    
    if not example_file or not example_file.exists():
        logger.error(f"Examples file not found for {problem['area']}/{problem['nature']}")
        raise FileNotFoundError(f"Examples file not found for {problem['area']}/{problem['nature']}")
    
    data = json.loads(example_file.read_text(encoding='utf-8'))
    examples = data.get('examples', [])
    logger.info(f"Loaded {len(examples)} examples from {example_file}")
    return examples


def extract_json_from_response(response_content: str) -> dict:
    """
    Extract valid JSON from LLM response that might contain markdown or other content.
    """
    logger.debug("Extracting JSON from LLM response")
    
    # Clean up content by removing markdown code blocks if present
    if '```' in response_content:
        logger.debug("Response contains code blocks, cleaning up")
        # Find the first and last backtick groups
        pattern = r'```(?:json)?\s*([\s\S]*?)```'
        matches = re.findall(pattern, response_content)
        if matches:
            response_content = matches[0]
            logger.debug("Extracted content from code block")
    
    # Try direct JSON parsing
    try:
        result = json.loads(response_content)
        logger.debug("Successfully parsed JSON directly")
        return result
    except json.JSONDecodeError as e:
        logger.warning(f"Direct JSON parsing failed: {str(e)}")
        # Try fixing common JSON issues
        try:
            logger.debug("Attempting to fix common JSON issues")
            # Replace single quotes with double quotes
            fixed_content = response_content.replace("'", '"')
            # Fix missing commas after closing braces in arrays
            fixed_content = re.sub(r'}\s*{', '},{', fixed_content)
            # Fix trailing commas in arrays/objects
            fixed_content = re.sub(r',\s*}', '}', fixed_content)
            fixed_content = re.sub(r',\s*]', ']', fixed_content)
            
            result = json.loads(fixed_content)
            logger.debug("Successfully parsed JSON after fixing common issues")
            return result
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parsing after fixes failed: {str(e)}")
            # Try to find any JSON object in the response
            try:
                logger.debug("Attempting to extract JSON object from response")
                start_idx = response_content.find('{')
                end_idx = response_content.rfind('}')
                if start_idx != -1 and end_idx != -1:
                    potential_json = response_content[start_idx:end_idx+1]
                    result = json.loads(potential_json)
                    logger.debug("Successfully extracted JSON object from response")
                    return result
            except Exception as e:
                logger.warning(f"JSON extraction from response failed: {str(e)}")
                pass
            
            logger.error(f"Failed to extract JSON from response")
            return {"samples": []}


def generate_in_batches(problem: dict, examples: list, total_count: int = 10, batch_size: int = 5) -> list:
    """
    Generate samples in multiple batches to handle larger numbers of samples.
    """
    logger.info(f"Generating {total_count} samples in batches of {batch_size} for {problem['nature']}")
    all_samples = []
    remaining = total_count
    
    # Only use the first two examples to avoid token limit issues
    examples_to_show = examples[:2]
    examples_json = json.dumps(examples_to_show, indent=2)
    
    while remaining > 0:
        current_batch_size = min(batch_size, remaining)
        logger.info(f"Generating batch of {current_batch_size} samples for {problem['nature']} ({len(all_samples)}/{total_count} so far)...")
        
        # Load prompts from YAML
        system_content = load_prompt(
            "large_generation_prompts",
            "prompts.generation.system.template"
        )
        
        user_content = load_prompt(
            "large_generation_prompts",
            "prompts.generation.user.template",
            nature=problem['nature'],
            area=problem['area'],
            description=problem.get('description', ''),
            examples_json=examples_json,
            count=current_batch_size
        )
        
        # Use process_llm_request to generate samples
        logger.info(f"Calling LLM for batch generation")
        response_content = process_llm_request(
            system_prompt=system_content,
            user_prompt=user_content,
            model_name=MODEL_NAME,
            temperature=0.7
        )
        
        logger.debug(f"Response received, length: {len(response_content)} characters")
        
        # Extract samples from response
        parsed = extract_json_from_response(response_content)
        samples = parsed.get('samples', [])
        
        if samples:
            all_samples.extend(samples)
            remaining -= len(samples)
            logger.info(f"Generated {len(samples)} samples in this batch, total now: {len(all_samples)}")
        else:
            logger.warning(f"Failed to generate samples in this batch, continuing...")
            # Try a slightly different approach for the next batch
            remaining -= current_batch_size  # Still count this as an attempt
        
        # If we have enough samples, stop
        if len(all_samples) >= total_count:
            logger.info(f"Reached target sample count of {total_count}")
            break
    
    logger.info(f"Completed batch generation with {len(all_samples)} total samples")
    return all_samples[:total_count]  # Return at most the requested number of samples


def generate_for_problem(problem: dict, n: int = 10) -> list:
    """
    Generate n synthetic samples for the given problem.
    """
    nature = problem['nature']
    area = problem['area']
    logger.info(f"Generating {n} samples for problem: {area}/{nature}")
    
    try:
        # Load examples from appropriate area subdirectory
        examples = load_examples(problem)
        
        if not examples:
            logger.warning(f"No seed examples found for {area}/{nature}")
            return []
        
        # Generate samples in batches
        samples = generate_in_batches(problem, examples, n, batch_size=5)
        
        # If batched generation failed completely, try one more direct approach
        if not samples:
            logger.info(f"Trying backup approach for {nature}")
            
            # Load backup prompts from YAML
            system_prompt = load_prompt(
                "large_generation_prompts",
                "prompts.backup_generation.system.template",
                nature=nature,
                area=area
            )
            
            user_prompt = load_prompt(
                "large_generation_prompts",
                "prompts.backup_generation.user.template",
                count=min(n, 5),
                nature=nature,
                description=problem.get('description', '')
            )
            
            logger.info("Calling LLM with backup approach")
            response_content = process_llm_request(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model_name=MODEL_NAME,
                temperature=0.7
            )
            
            parsed = extract_json_from_response(response_content)
            if parsed:
                samples = parsed.get('samples', [])
                logger.info(f"Generated {len(samples)} samples with backup approach")
        
        return samples
            
    except FileNotFoundError as e:
        logger.error(f"Error: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error generating samples for {nature}: {e}", exc_info=True)
        return []


def save_samples(problem: dict, samples: list):
    """
    Save generated samples to a JSON file.
    """
    if not samples:
        logger.warning(f"No samples to save for {problem['nature']}")
        return
    
    area = problem['area']
    nature = problem['nature']
    
    # Create a sanitized version of area and nature for directory and filename
    sanitized_area = area.replace(' ', '_').replace('(', '').replace(')', '').replace('-', '_')
    sanitized_nature = nature.replace(' ', '_')
    
    # Create area directory
    area_dir = OUTPUT_DIR / sanitized_area
    area_dir.mkdir(parents=True, exist_ok=True)
    logger.debug(f"Created area directory: {area_dir}")
    
    # Create filename
    filename = f"{sanitized_nature}_large.json"
    
    # Create output file path
    out_file = area_dir / filename
    
    # Check if there are existing samples
    existing_samples = []
    if out_file.exists():
        try:
            existing_data = json.loads(out_file.read_text(encoding='utf-8'))
            existing_samples = existing_data.get('samples', [])
            logger.info(f"Found {len(existing_samples)} existing samples in {out_file}")
        except Exception as e:
            logger.error(f"Error reading existing file: {e}", exc_info=True)
    
    # Combine existing and new samples
    all_samples = existing_samples + samples
    
    # Save samples
    with out_file.open('w', encoding='utf-8') as f:
        json.dump({'samples': all_samples}, f, indent=2)
    
    logger.info(f"Saved {len(samples)} new samples (total: {len(all_samples)}) to {out_file}")


def main(count: int = 10, problem_filter: list = None):
    """
    Main function to generate samples for all problems.
    """
    logger.info(f"Starting sample generation with count={count}")
    
    # Load problem definitions (auto-selects the appropriate file)
    problems = load_problems()
    
    # Filter problems if specified
    if problem_filter:
        logger.info(f"Filtering problems to: {problem_filter}")
        problems = [p for p in problems if p['nature'] in problem_filter]
        if not problems:
            logger.error(f"No matching problems found for {problem_filter}")
            return
    
    # Group problems by area for better organization in output
    areas = set(problem['area'] for problem in problems)
    logger.info(f"Found {len(problems)} problems across {len(areas)} areas: {', '.join(areas)}")
    
    for problem in problems:
        area = problem['area']
        nature = problem['nature']
        logger.info(f"\nGenerating {count} samples for {area}/{nature}...")
        
        try:
            # Generate samples
            samples = generate_for_problem(problem, count)
            
            if not samples:
                logger.warning(f"No samples generated for {nature}, skipping to next problem")
                continue
            
            # Save samples
            save_samples(problem, samples)
            
        except Exception as e:
            logger.error(f"Error processing {nature}: {e}", exc_info=True)
            continue  # Continue with the next problem
    
    logger.info("Sample generation completed!")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate synthetic cybersecurity data samples")
    parser.add_argument('--count', type=int, default=10, help='Number of samples to generate per problem (default: 10)')
    parser.add_argument('--problems', nargs='+', help='Specific problem natures to generate samples for (optional)')
    
    args = parser.parse_args()
    
    logger.info(f"Starting generator.py with args: count={args.count}, problems={args.problems}")
    main(args.count, args.problems)