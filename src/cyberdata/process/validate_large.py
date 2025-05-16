# cyberdata/scripts/validate_large.py

import os
import json
import random
from pathlib import Path
from dotenv import load_dotenv
import sys

# Add parent directory to path for imports
CURRENT_DIR = Path(__file__).parent
PROJECT_ROOT = CURRENT_DIR.parent.parent.parent
sys.path.append(str(CURRENT_DIR.parent))  # Add cyberdata package to path

# Import process_llm_request from utility module
from cyberdata.utils.llm_invoke import process_llm_request
from cyberdata.utils.logger_config import setup_logger

# Set up logger
logger = setup_logger("cyberdata.scripts.validate_large")

# Load environment variables
load_dotenv()

# Constants and paths
MODEL_NAME = "gpt-4.1-mini"  # Match with other scripts
PROBLEMS_PATH = CURRENT_DIR.parent / 'config' / 'problems.json'
LARGE_SAMPLES_DIR = PROJECT_ROOT / 'data' / 'large_samples'
REPORTS_DIR = PROJECT_ROOT / 'data' / 'quality_reports'

logger.info(f"Using model: {MODEL_NAME}")
logger.info(f"Problems path: {PROBLEMS_PATH}")
logger.info(f"Large samples directory: {LARGE_SAMPLES_DIR}")
logger.info(f"Reports directory: {REPORTS_DIR}")

REPORTS_DIR.mkdir(parents=True, exist_ok=True)
logger.info(f"Created reports directory: {REPORTS_DIR}")


def load_problems():
    """Load problem definitions from config."""
    if not PROBLEMS_PATH.exists():
        logger.error(f"Missing problems config: {PROBLEMS_PATH}")
        raise FileNotFoundError(f"Missing problems config: {PROBLEMS_PATH}")
    
    data = json.loads(PROBLEMS_PATH.read_text(encoding='utf-8'))
    problems = data.get('problems', [])
    logger.info(f"Loaded {len(problems)} problems from {PROBLEMS_PATH}")
    return problems


def find_samples_file(problem):
    """
    Find the large samples file for a specific problem.
    """
    area = problem['area']
    nature = problem['nature']
    
    # Create a sanitized version of area and nature for filename matching
    sanitized_area = area.replace(' ', '_').replace('(', '').replace(')', '').replace('-', '_')
    sanitized_nature = nature.replace(' ', '_')
    
    logger.debug(f"Looking for large samples file for {sanitized_area}/{sanitized_nature}")
    
    # Check for the file in the area-specific directory
    area_dir = LARGE_SAMPLES_DIR / sanitized_area
    if area_dir.exists():
        filename = f"{sanitized_nature}_large.json"
        samples_file = area_dir / filename
        
        if samples_file.exists():
            logger.debug(f"Found samples file: {samples_file}")
            return samples_file
    
    # If not found, try looking for the file in other area directories
    logger.debug("Samples file not found in expected location, searching all areas")
    for dir_path in LARGE_SAMPLES_DIR.glob('*'):
        if dir_path.is_dir():
            for file_path in dir_path.glob('*.json'):
                if sanitized_nature.lower() in file_path.name.lower() and 'large' in file_path.name.lower():
                    logger.debug(f"Found samples file in alternative location: {file_path}")
                    return file_path
            
    logger.warning(f"No samples file found for {area}/{nature}")
    return None


def load_samples(problem):
    """
    Load large samples for a given problem.
    
    Args:
        problem (dict): The problem definition
        
    Returns:
        list: The samples for the given problem
    """
    samples_file = find_samples_file(problem)
    
    if not samples_file:
        logger.error(f"Large samples not found for {problem['area']}/{problem['nature']}")
        raise FileNotFoundError(f"Large samples not found for {problem['area']}/{problem['nature']}")
    
    data = json.loads(samples_file.read_text(encoding='utf-8'))
    samples = data.get('samples', [])
    logger.info(f"Loaded {len(samples)} samples from {samples_file}")
    return samples


def automated_metrics(samples):
    """
    Calculate automated metrics for the samples.
    
    Args:
        samples (list): The samples to analyze
        
    Returns:
        dict: Metrics about the samples
    """
    logger.info(f"Calculating automated metrics for {len(samples)} samples")
    
    total = len(samples)
    
    # Unique count by serialized sample
    unique_samples = {json.dumps(s, sort_keys=True) for s in samples}
    unique_count = len(unique_samples)
    
    logger.debug(f"Found {unique_count} unique samples out of {total} total samples")
    
    # Required keys from first sample
    req_keys = set(samples[0].keys()) if samples else set()
    missing_counts = sum(1 for s in samples if not req_keys.issubset(s.keys()))
    
    logger.debug(f"Found {missing_counts} samples with missing keys")
    
    metrics = {
        'total_samples': total,
        'unique_samples': unique_count,
        'uniqueness_ratio': unique_count / total if total else 0,
        'missing_keys_count': missing_counts
    }
    
    logger.info(f"Metrics calculated: uniqueness ratio = {metrics['uniqueness_ratio']:.2f}")
    return metrics


def make_quality_system_prompt():
    """
    System prompt for the LLM to evaluate sample quality.
    
    Returns:
        str: The system prompt
    """
    logger.debug("Creating quality system prompt")
    return (
        "You are a synthetic data quality evaluator specializing in cybersecurity datasets. "
        "Assess the quality of generated samples in terms of realism, consistency, and adherence to schema."
    )


def make_quality_user_prompt(problem: dict, sample_snippet: list):
    """
    User prompt for the LLM to evaluate sample quality.
    
    Args:
        problem (dict): The problem definition
        sample_snippet (list): A subset of samples to evaluate
        
    Returns:
        str: The user prompt
    """
    logger.debug(f"Creating quality user prompt for problem: {problem['nature']} with {len(sample_snippet)} samples")
    snippet_json = json.dumps(sample_snippet, indent=2)
    return (
        f"Problem Nature: {problem['nature']} (Area: {problem['area']})\n"
        f"Description: {problem.get('description')}\n"
        "Here are a few sample entries:"
        f"\n{snippet_json}\n"
        "Please provide a JSON object with keys:\n"
        "- 'realism': comment on how realistic the samples are.\n"
        "- 'consistency': comment on uniformity and schema adherence.\n"
        "- 'suggestions': list of improvement suggestions.\n"
        "Return only valid JSON."
    )


def evaluate_with_llm(problem, samples, snippet_size=5):
    """
    Use the LLM to evaluate sample quality.
    
    Args:
        problem (dict): The problem definition
        samples (list): The samples to evaluate
        snippet_size (int): Number of samples to include in the evaluation
        
    Returns:
        dict: The evaluation results
    """
    # Random sample of samples to evaluate (to avoid token limits)
    snippet = random.sample(samples, min(snippet_size, len(samples)))
    logger.info(f"Evaluating {len(snippet)} samples with LLM for problem: {problem['nature']}")
    
    system_prompt = make_quality_system_prompt()
    user_prompt = make_quality_user_prompt(problem, snippet)
    
    # Use process_llm_request for LLM call
    logger.info("Calling LLM for quality evaluation")
    response_content = process_llm_request(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model_name=MODEL_NAME,
        temperature=0.0  # Use 0 for consistent evaluation
    )
    
    logger.debug(f"Response received, length: {len(response_content)} characters")
    
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
        logger.info("Successfully parsed JSON evaluation response")
        return result
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON response: {str(e)}")
        logger.debug(f"Raw response: {response_content[:100]}...")
        return {'realism': None, 'consistency': None, 'suggestions': [response_content]}


def main():
    """Main function to evaluate quality of samples for all problems."""
    logger.info("Starting quality evaluation of large samples")
    problems = load_problems()
    
    for problem in problems:
        area = problem['area']
        nature = problem['nature']
        logger.info(f"Evaluating quality for {area}/{nature}...")
        
        try:
            samples = load_samples(problem)
            
            # Skip if no samples
            if not samples:
                logger.warning(f"No samples found for {area}/{nature}, skipping.")
                continue
                
            metrics = automated_metrics(samples)
            llm_eval = evaluate_with_llm(problem, samples)
            
            report = {
                'problem': {'area': area, 'nature': nature},
                'metrics': metrics,
                'llm_evaluation': llm_eval
            }
            
            # Create a sanitized version of area and nature for directory and filename
            sanitized_area = area.replace(' ', '_').replace('(', '').replace(')', '').replace('-', '_')
            sanitized_nature = nature.replace(' ', '_')
            
            # Create area directory
            area_report_dir = REPORTS_DIR / sanitized_area
            area_report_dir.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Created report directory for area: {area_report_dir}")
            
            # Create filename
            report_filename = f"{sanitized_nature}_quality_report.json"
            
            report_path = area_report_dir / report_filename
            with report_path.open('w', encoding='utf-8') as f:
                json.dump(report, f, indent=2)
                
            logger.info(f"Saved quality report to {report_path}")
            
        except FileNotFoundError as e:
            logger.error(f"Error: {e}")
            continue
        except Exception as e:
            logger.error(f"Unexpected error evaluating {area}/{nature}: {e}", exc_info=True)
            continue

    logger.info("Completed quality evaluation of large samples")


if __name__ == '__main__':
    main()