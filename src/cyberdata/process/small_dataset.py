# cyberdata/scripts/small_dataset.py

import json
import os
import sys
import re
from pathlib import Path

from dotenv import load_dotenv

# Add parent directory to path for imports
CURRENT_DIR = Path(__file__).parent
sys.path.append(str(CURRENT_DIR.parent))  # Add cyberdata package to path

# Import utilities
from cyberdata.utils.llm_invoke import process_llm_request
from cyberdata.utils.logger_config import setup_logger
from cyberdata.utils.prompt_loader import load_system_prompt, load_user_prompt
from cyberdata.utils.config_manager import get_config_manager

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


def extract_json_from_response(response_content: str) -> dict:
    """
    Extract valid JSON from LLM response that might contain markdown or other content.
    """
    logger.debug("Extracting JSON from LLM response")
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
                logger.debug(f"Extracted content between backticks: {response_content[:100]}...")
            else:
                # Just remove the first backticks line if no closing backticks found
                response_content = response_content[first_backticks_end + 1:].strip()
                logger.debug(f"Removed first backticks line: {response_content[:100]}...")
    
    # Try direct JSON parsing
    try:
        examples = json.loads(response_content)
        # Check if we have 'examples' key in the response
        if 'examples' in examples:
            logger.debug(f"Found 'examples' key in response with {len(examples['examples'])} examples")
            return examples['examples']
        else:
            logger.debug("No 'examples' key in response, assuming direct examples array")
            return examples  # Assume the response is the examples array directly
    except json.JSONDecodeError as e:
        logger.warning(f"JSON parsing failed: {str(e)}")
        # Try alternative extraction methods
        
        # Try extracting JSON with regex
        json_pattern = r'\{[\s\S]*\}'
        match = re.search(json_pattern, response_content)
        if match:
            logger.debug("Found JSON pattern with regex")
            try:
                potential_json = match.group(0)
                examples = json.loads(potential_json)
                if 'examples' in examples:
                    logger.debug(f"Found 'examples' key in regex match with {len(examples['examples'])} examples")
                    return examples['examples']
                else:
                    logger.debug("No 'examples' key in regex match, assuming direct examples array")
                    return examples
            except json.JSONDecodeError as e:
                logger.warning(f"JSON parsing of regex match failed: {str(e)}")
                pass
        
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
            
            examples = json.loads(fixed_content)
            if 'examples' in examples:
                logger.debug(f"Found 'examples' key in fixed content with {len(examples['examples'])} examples")
                return examples['examples']
            else:
                logger.debug("No 'examples' key in fixed content, assuming direct examples array")
                return examples
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parsing of fixed content failed: {str(e)}")
            pass
        
        # If all extraction methods fail, raise exception
        logger.error(f"Failed to extract JSON from: {response_content[:100]}...")
        raise ValueError("Could not extract valid JSON from model response")


def generate_examples_for_problem(problem: dict) -> list:
    """Generate examples for a problem using process_llm_request function"""
    logger.info(f"Generating examples for problem: {problem['area']}/{problem['nature']}")
    
    # Load prompts from YAML using the prompt loader
    system_content = load_system_prompt(
        "seed_generation_prompts",
        area=problem['area'],
        nature=problem['nature'],
        description=problem.get('description', ''),
        risk_reduction=', '.join(problem.get('risk_reduction', []))
    )
    
    user_content = load_user_prompt("seed_generation_prompts")
    
    # Use process_llm_request instead of direct OpenAI call
    logger.info(f"Calling LLM for problem: {problem['nature']}")
    response_content = process_llm_request(
        system_prompt=system_content,
        user_prompt=user_content,
        model_name=MODEL_NAME,
        temperature=0.7
    )
    
    # Debug: Print response content before parsing
    logger.info(f"Response received for {problem['nature']}, length: {len(response_content)} characters")
    logger.debug(f"Response for {problem['nature']}: {response_content[:100]}...")
    
    try:
        # Use the enhanced JSON extraction
        examples = extract_json_from_response(response_content)
        logger.info(f"Successfully extracted {len(examples)} examples for {problem['nature']}")
        return examples
    except Exception as e:
        logger.error(f"JSON parse error for {problem['nature']}: {str(e)}")
        logger.debug(f"Response content: {response_content}")
        # If JSON extraction fails completely, return empty list
        # This allows the script to continue with other problems
        return []


def save_examples(problem: dict, examples: list):
    """
    Save examples to JSON files using config manager
    
    Args:
        problem (dict): Problem dictionary containing 'area' and 'nature'
        examples (list): List of examples to save
    """
    # Skip if no valid examples
    if not examples:
        logger.warning(f"No valid examples to save for {problem['nature']}")
        return
    
    area = problem['area']
    nature = problem['nature']
    
    # Get the file path using config manager
    file_path = config_manager.get_seeds_file(area, nature)
    
    # Ensure the directory exists
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Save JSON file
    with file_path.open('w', encoding='utf-8') as f:
        json.dump({'examples': examples}, f, indent=2)
    logger.info(f"Saved {len(examples)} examples for {area}/{nature} to {file_path}")


def main():
    """Main function to generate examples for all problems"""
    logger.info("Starting seed examples generation")
    problems = load_problems()
    
    # Group problems by area for better organization in output
    areas = set(problem['area'] for problem in problems)
    logger.info(f"Found {len(problems)} problems across {len(areas)} areas: {', '.join(areas)}")
    
    for problem in problems:
        try:
            area = problem['area']
            nature = problem['nature']
            logger.info(f"Processing problem: {area}/{nature}")
            examples = generate_examples_for_problem(problem)
            save_examples(problem, examples)
        except Exception as e:
            logger.error(f"Error generating for {problem['area']}/{problem['nature']}: {e}", exc_info=True)
            continue  # Continue with the next problem

    logger.info(f"All detailed examples have been generated in '{config_manager.seeds_dir}'.")


if __name__ == '__main__':
    main()