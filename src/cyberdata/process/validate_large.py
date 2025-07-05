import os
import json
import random
from pathlib import Path
from dotenv import load_dotenv
import sys
import time
from typing import Dict, List, Any, Tuple
import statistics
import re
import csv

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
#     if "individual_sample_validation" in system_prompt:
#         return """
#         ```json
#         {
#           "is_valid": true,
#           "scores": {
#             "relevance": 1.0,
#             "consistency": 0.9,
#             "correctness": 1.0,
#             "completeness": 0.8,
#             "realism": 0.9
#           },
#           "overall_score": 0.92,
#           "issues": [],
#           "strengths": ["Clear scenario", "Plausible options"]
#         }
#         ```
#         """
#     else: # quality_assessment
#         return """
#         ```json
#         {
#           "realism": 0.9,
#           "consistency": 0.85,
#           "diversity": 0.7,
#           "suggestions": ["Include more scenarios involving social engineering.", "Vary the difficulty of the questions more."]
#         }
#         ```
#         """

# def setup_logger(name):
#     import logging
#     logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
#     return logging.getLogger(name)

# def load_prompt(name, template_path, **kwargs):
#     return f"Prompt from {name}/{template_path} with context: {kwargs}"
# # --- End of Mock implementations ---


# Set up logger
logger = setup_logger("cyberdata.scripts.validate_large")

# Load environment variables
load_dotenv()

# Constants
MODEL_NAME = "gpt-4.1-mini"

# Get config manager instance
config_manager = get_config_manager()

# Validation configuration
SAMPLE_VALIDATION_BATCH_SIZE = 10
VALIDATION_SAMPLE_PERCENTAGE = 0.2

logger.info(f"Using model: {MODEL_NAME}")
logger.info(f"Project root: {config_manager.project_root}")
logger.info(f"Large samples directory: {config_manager.large_samples_dir}")
logger.info(f"Reports directory: {config_manager.quality_reports_dir}")


def load_problems() -> list:
    """Load problem definitions using config manager"""
    return config_manager.load_problems()


def find_samples_file(problem):
    """Find the large samples file for a specific problem."""
    expected_file = config_manager.get_large_samples_file(problem['area'], problem['nature'])
    if expected_file.exists():
        return expected_file
    
    found_file = config_manager.find_existing_file(
        config_manager.large_samples_dir, problem['nature'], "_large.json"
    )
    if found_file:
        return found_file
    
    logger.warning(f"No samples file found for {problem['area']}/{problem['nature']}")
    return None


def load_samples(problem):
    """Load large samples for a given problem."""
    samples_file = find_samples_file(problem)
    if not samples_file:
        raise FileNotFoundError(f"Large samples not found for {problem['area']}/{problem['nature']}")
    
    data = json.loads(samples_file.read_text(encoding='utf-8'))
    samples = data.get('samples', [])
    logger.info(f"Loaded {len(samples)} samples from {samples_file}")
    return samples


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
        return {"error": "Invalid JSON response", "raw_content": response_content}


def automated_metrics(samples):
    """Calculate automated metrics for the samples."""
    logger.info(f"Calculating automated metrics for {len(samples)} samples")
    total = len(samples)
    if not total:
        return {'total_samples': 0, 'unique_samples': 0, 'uniqueness_ratio': 0, 'missing_keys_count': 0, 'completeness_ratio': 0}
    
    unique_samples = {json.dumps(s, sort_keys=True) for s in samples}
    unique_count = len(unique_samples)
    
    req_keys = set(samples[0].keys())
    missing_counts = sum(1 for s in samples if not req_keys.issubset(s.keys()))
    
    metrics = {
        'total_samples': total,
        'unique_samples': unique_count,
        'uniqueness_ratio': unique_count / total,
        'missing_keys_count': missing_counts,
        'completeness_ratio': (total - missing_counts) / total
    }
    logger.info(f"Metrics calculated: uniqueness ratio = {metrics['uniqueness_ratio']:.2f}")
    return metrics


def save_validation_log_to_csv(system_prompt: str, user_prompt: str, validation_result: dict):
    """Save the prompts and validation result of a single call to a CSV log."""
    file_path = config_manager.data_dir / "large_validation.csv"
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


def validate_individual_sample(problem: dict, sample: dict, sample_index: int) -> dict:
    """Validate an individual sample using LLM."""
    logger.debug(f"Validating individual sample {sample_index} for problem: {problem['nature']}")
    
    sample_json = json.dumps(sample, indent=2)
    system_prompt = load_prompt(
        "validation_prompts",
        "prompts.individual_sample_validation.system.template",
        area=problem['area'],
        nature=problem['nature'],
        description=problem.get('description', '')
    )
    user_prompt = load_prompt(
        "validation_prompts",
        "prompts.individual_sample_validation.user.template",
        sample_json=sample_json
    )
    
    response_content = process_llm_request(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model_name=MODEL_NAME,
        temperature=0.0
    )
    
    result = extract_json_from_response(response_content)
    result['sample_index'] = sample_index
    
    save_validation_log_to_csv(system_prompt, user_prompt, result)
    
    logger.debug(f"Sample {sample_index} validation: valid={result.get('is_valid', False)}, score={result.get('overall_score', 0):.2f}")
    return result


def validate_sample_batch(problem: dict, samples: List[dict], max_samples: int = None) -> List[dict]:
    """Validate a batch of samples individually."""
    total_samples = len(samples)
    samples_to_validate = max(SAMPLE_VALIDATION_BATCH_SIZE, int(total_samples * VALIDATION_SAMPLE_PERCENTAGE))
    if max_samples:
        samples_to_validate = min(samples_to_validate, max_samples)
    samples_to_validate = min(samples_to_validate, total_samples)
    
    logger.info(f"Validating {samples_to_validate} out of {total_samples} samples individually")
    selected_indices = random.sample(range(total_samples), samples_to_validate)
    validation_results = []
    
    for i, idx in enumerate(selected_indices):
        logger.info(f"Validating sample {i+1}/{samples_to_validate} (index: {idx})...")
        try:
            result = validate_individual_sample(problem, samples[idx], idx)
            validation_results.append(result)
            if i < len(selected_indices) - 1:
                time.sleep(0.5)
        except Exception as e:
            logger.error(f"Error validating sample {idx}: {str(e)}")
            validation_results.append({'sample_index': idx, 'is_valid': False, 'overall_score': 0.0, 'error': str(e)})
    
    return validation_results


def aggregate_validation_results(validation_results: List[dict]) -> dict:
    """Aggregate individual validation results into summary statistics."""
    if not validation_results:
        return {}
    
    valid_count = sum(1 for r in validation_results if r.get('is_valid', False))
    overall_scores = [r.get('overall_score', 0.0) for r in validation_results]
    
    return {
        'samples_validated': len(validation_results),
        'valid_samples': valid_count,
        'validity_rate': valid_count / len(validation_results),
        'overall_score_mean': statistics.mean(overall_scores),
        'overall_score_std': statistics.stdev(overall_scores) if len(overall_scores) > 1 else 0.0,
    }


def evaluate_with_llm(problem, samples, snippet_size=5):
    """Use the LLM to evaluate overall sample quality."""
    snippet = random.sample(samples, min(snippet_size, len(samples)))
    logger.info(f"Evaluating {len(snippet)} samples with LLM for overall quality assessment")
    
    snippet_json = json.dumps(snippet, indent=2)
    system_prompt = load_prompt("validation_prompts", "prompts.quality_assessment.system.template")
    user_prompt = load_prompt(
        "validation_prompts",
        "prompts.quality_assessment.user.template",
        nature=problem['nature'],
        area=problem['area'],
        description=problem.get('description', ''),
        snippet_json=snippet_json
    )
    
    logger.info("Calling LLM for overall quality evaluation")
    response_content = process_llm_request(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model_name=MODEL_NAME,
        temperature=0.0
    )
    
    result = extract_json_from_response(response_content)
    save_validation_log_to_csv(system_prompt, user_prompt, result)
    
    logger.info("Successfully parsed JSON evaluation response")
    return result


def main():
    """Main function to evaluate quality of samples for all problems."""
    logger.info("Starting quality evaluation of large samples")
    problems = load_problems()
    
    for problem in problems:
        area = problem['area']
        nature = problem['nature']
        logger.info(f"\n--- Evaluating quality for {area}/{nature} ---")
        
        try:
            samples = load_samples(problem)
            if not samples:
                logger.warning(f"No samples found for {area}/{nature}, skipping.")
                continue
            
            # Perform all validation steps
            metrics = automated_metrics(samples)
            individual_validations = validate_sample_batch(problem, samples)
            validation_summary = aggregate_validation_results(individual_validations)
            overall_assessment = evaluate_with_llm(problem, samples)
            
            # Compile the full JSON report
            report = {
                'problem': {
                    'area': area,
                    'nature': nature,
                    'description': problem.get('description', '')
                },
                'automated_metrics': metrics,
                'individual_validations': {
                    'summary': validation_summary,
                    'detailed_results': individual_validations
                },
                'overall_assessment': overall_assessment,
                'report_metadata': {
                    'total_samples': len(samples),
                    'samples_validated_individually': len(individual_validations),
                    'validation_percentage': len(individual_validations) / len(samples) * 100 if samples else 0
                }
            }
            
            # Save the full JSON report
            report_path = config_manager.get_quality_report_file(area, nature)
            report_path.parent.mkdir(parents=True, exist_ok=True)
            with report_path.open('w', encoding='utf-8') as f:
                json.dump(report, f, indent=2)
            logger.info(f"Saved full quality report to {report_path}")

        except FileNotFoundError as e:
            logger.error(f"Error: {e}")
            continue
        except Exception as e:
            logger.error(f"Unexpected error evaluating {area}/{nature}: {e}", exc_info=True)
            continue

    logger.info("Completed quality evaluation of large samples")


if __name__ == '__main__':
    main()
