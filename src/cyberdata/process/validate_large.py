# cyberdata/scripts/validate_large.py

import os
import json
import random
from pathlib import Path
from dotenv import load_dotenv
import sys
import time
from typing import Dict, List, Any, Tuple
import statistics

# Add parent directory to path for imports
CURRENT_DIR = Path(__file__).parent
sys.path.append(str(CURRENT_DIR.parent))  # Add cyberdata package to path

# Import utilities
from cyberdata.utils.llm_invoke import process_llm_request
from cyberdata.utils.logger_config import setup_logger
from cyberdata.utils.prompt_loader import load_prompt
from cyberdata.utils.config_manager import get_config_manager

# Set up logger
logger = setup_logger("cyberdata.scripts.validate_large")

# Load environment variables
load_dotenv()

# Constants
MODEL_NAME = "gpt-4.1-mini"

# Get config manager instance
config_manager = get_config_manager()

# Validation configuration
SAMPLE_VALIDATION_BATCH_SIZE = 10  # Number of samples to validate individually
VALIDATION_SAMPLE_PERCENTAGE = 0.2  # Validate 20% of samples (or at least SAMPLE_VALIDATION_BATCH_SIZE)

logger.info(f"Using model: {MODEL_NAME}")
logger.info(f"Project root: {config_manager.project_root}")
logger.info(f"Large samples directory: {config_manager.large_samples_dir}")
logger.info(f"Reports directory: {config_manager.quality_reports_dir}")


def load_problems() -> list:
    """Load problem definitions using config manager"""
    return config_manager.load_problems()


def find_samples_file(problem):
    """
    Find the large samples file for a specific problem using config manager.
    """
    area = problem['area']
    nature = problem['nature']
    
    # First try the standard path
    expected_file = config_manager.get_large_samples_file(area, nature)
    if expected_file.exists():
        logger.debug(f"Found samples file: {expected_file}")
        return expected_file
    
    # If not found, use the config manager's search function
    found_file = config_manager.find_existing_file(
        config_manager.large_samples_dir, 
        nature, 
        "_large.json"
    )
    
    if found_file:
        logger.debug(f"Found samples file in alternative location: {found_file}")
        return found_file
    
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
        'missing_keys_count': missing_counts,
        'completeness_ratio': (total - missing_counts) / total if total else 0
    }
    
    logger.info(f"Metrics calculated: uniqueness ratio = {metrics['uniqueness_ratio']:.2f}")
    return metrics


def validate_individual_sample(problem: dict, sample: dict, sample_index: int) -> dict:
    """
    Validate an individual sample using LLM.
    
    Args:
        problem (dict): The problem definition
        sample (dict): The sample to validate
        sample_index (int): Index of the sample in the dataset
        
    Returns:
        dict: Validation results for the sample
    """
    logger.debug(f"Validating individual sample {sample_index} for problem: {problem['nature']}")
    
    # Serialize sample to JSON
    sample_json = json.dumps(sample, indent=2)
    
    # Load prompts from YAML
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
    
    # Use process_llm_request for LLM call
    response_content = process_llm_request(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model_name=MODEL_NAME,
        temperature=0.0  # Use 0 for consistent evaluation
    )
    
    try:
        # Clean up content by removing markdown code blocks if present
        if response_content.startswith('```'):
            first_backticks_end = response_content.find('\n', 3)
            if first_backticks_end != -1:
                last_backticks_start = response_content.rfind('```')
                if last_backticks_start > first_backticks_end:
                    response_content = response_content[first_backticks_end + 1:last_backticks_start].strip()
        
        result = json.loads(response_content)
        result['sample_index'] = sample_index
        logger.debug(f"Sample {sample_index} validation: valid={result.get('is_valid', False)}, score={result.get('overall_score', 0):.2f}")
        return result
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON response for sample {sample_index}: {str(e)}")
        # Return a default failed validation
        return {
            'sample_index': sample_index,
            'is_valid': False,
            'scores': {
                'relevance': 0.0,
                'consistency': 0.0,
                'correctness': 0.0,
                'completeness': 0.0,
                'realism': 0.0
            },
            'overall_score': 0.0,
            'issues': ['Failed to parse LLM validation response'],
            'strengths': []
        }


def validate_sample_batch(problem: dict, samples: List[dict], max_samples: int = None) -> List[dict]:
    """
    Validate a batch of samples individually.
    
    Args:
        problem (dict): The problem definition
        samples (list): All samples to potentially validate
        max_samples (int): Maximum number of samples to validate
        
    Returns:
        list: Validation results for each validated sample
    """
    # Determine how many samples to validate
    total_samples = len(samples)
    samples_to_validate = max(
        SAMPLE_VALIDATION_BATCH_SIZE,
        int(total_samples * VALIDATION_SAMPLE_PERCENTAGE)
    )
    
    if max_samples:
        samples_to_validate = min(samples_to_validate, max_samples)
    
    samples_to_validate = min(samples_to_validate, total_samples)
    
    logger.info(f"Validating {samples_to_validate} out of {total_samples} samples individually")
    
    # Randomly select samples for validation
    selected_indices = random.sample(range(total_samples), samples_to_validate)
    validation_results = []
    
    for i, idx in enumerate(selected_indices):
        logger.info(f"Validating sample {i+1}/{samples_to_validate} (index: {idx})...")
        
        try:
            result = validate_individual_sample(problem, samples[idx], idx)
            validation_results.append(result)
            
            # Add small delay to avoid rate limiting
            if i < len(selected_indices) - 1:
                time.sleep(0.5)
                
        except Exception as e:
            logger.error(f"Error validating sample {idx}: {str(e)}")
            validation_results.append({
                'sample_index': idx,
                'is_valid': False,
                'overall_score': 0.0,
                'error': str(e)
            })
    
    return validation_results


def aggregate_validation_results(validation_results: List[dict]) -> dict:
    """
    Aggregate individual validation results into summary statistics.
    
    Args:
        validation_results (list): List of individual validation results
        
    Returns:
        dict: Aggregated statistics
    """
    if not validation_results:
        return {
            'samples_validated': 0,
            'valid_samples': 0,
            'invalid_samples': 0,
            'validity_rate': 0.0,
            'average_scores': {},
            'score_distribution': {}
        }
    
    valid_count = sum(1 for r in validation_results if r.get('is_valid', False))
    invalid_count = len(validation_results) - valid_count
    
    # Calculate average scores
    score_types = ['relevance', 'consistency', 'correctness', 'completeness', 'realism']
    average_scores = {}
    score_lists = {score_type: [] for score_type in score_types}
    
    for result in validation_results:
        scores = result.get('scores', {})
        for score_type in score_types:
            if score_type in scores:
                score_lists[score_type].append(scores[score_type])
    
    for score_type, scores in score_lists.items():
        if scores:
            average_scores[score_type] = statistics.mean(scores)
            average_scores[f'{score_type}_std'] = statistics.stdev(scores) if len(scores) > 1 else 0.0
    
    # Overall score statistics
    overall_scores = [r.get('overall_score', 0.0) for r in validation_results]
    
    # Score distribution (bins)
    score_bins = {
        'excellent': sum(1 for s in overall_scores if s >= 0.9),
        'good': sum(1 for s in overall_scores if 0.7 <= s < 0.9),
        'fair': sum(1 for s in overall_scores if 0.5 <= s < 0.7),
        'poor': sum(1 for s in overall_scores if s < 0.5)
    }
    
    # Common issues
    all_issues = []
    for r in validation_results:
        all_issues.extend(r.get('issues', []))
    
    # Count issue frequencies
    issue_counts = {}
    for issue in all_issues:
        issue_counts[issue] = issue_counts.get(issue, 0) + 1
    
    # Sort issues by frequency
    common_issues = sorted(issue_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    
    return {
        'samples_validated': len(validation_results),
        'valid_samples': valid_count,
        'invalid_samples': invalid_count,
        'validity_rate': valid_count / len(validation_results) if validation_results else 0.0,
        'average_scores': average_scores,
        'overall_score_mean': statistics.mean(overall_scores) if overall_scores else 0.0,
        'overall_score_std': statistics.stdev(overall_scores) if len(overall_scores) > 1 else 0.0,
        'score_distribution': score_bins,
        'common_issues': common_issues
    }


def evaluate_with_llm(problem, samples, snippet_size=5):
    """
    Use the LLM to evaluate overall sample quality.
    
    Args:
        problem (dict): The problem definition
        samples (list): The samples to evaluate
        snippet_size (int): Number of samples to include in the evaluation
        
    Returns:
        dict: The evaluation results
    """
    # Random sample of samples to evaluate (to avoid token limits)
    snippet = random.sample(samples, min(snippet_size, len(samples)))
    logger.info(f"Evaluating {len(snippet)} samples with LLM for overall quality assessment")
    
    # Serialize the snippet to JSON
    snippet_json = json.dumps(snippet, indent=2)
    
    # Load prompts from YAML
    system_prompt = load_prompt(
        "validation_prompts",
        "prompts.quality_assessment.system.template"
    )
    
    user_prompt = load_prompt(
        "validation_prompts",
        "prompts.quality_assessment.user.template",
        nature=problem['nature'],
        area=problem['area'],
        description=problem.get('description', ''),
        snippet_json=snippet_json
    )
    
    # Use process_llm_request for LLM call
    logger.info("Calling LLM for overall quality evaluation")
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
            first_backticks_end = response_content.find('\n', 3)
            if first_backticks_end != -1:
                last_backticks_start = response_content.rfind('```')
                if last_backticks_start > first_backticks_end:
                    response_content = response_content[first_backticks_end + 1:last_backticks_start].strip()
        
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
            
            # Calculate automated metrics
            logger.info("Calculating automated metrics...")
            metrics = automated_metrics(samples)
            
            # Validate individual samples
            logger.info("Validating individual samples...")
            individual_validations = validate_sample_batch(problem, samples)
            
            # Aggregate validation results
            logger.info("Aggregating validation results...")
            validation_summary = aggregate_validation_results(individual_validations)
            
            # Get overall quality assessment
            logger.info("Getting overall quality assessment...")
            overall_assessment = evaluate_with_llm(problem, samples)
            
            # Compile full report
            report = {
                'problem': {
                    'area': area,
                    'nature': nature,
                    'description': problem.get('description', '')
                },
                'automated_metrics': metrics,
                'individual_validations': {
                    'summary': validation_summary,
                    'detailed_results': individual_validations  # Include detailed results
                },
                'overall_assessment': overall_assessment,
                'report_metadata': {
                    'total_samples': len(samples),
                    'samples_validated_individually': len(individual_validations),
                    'validation_percentage': len(individual_validations) / len(samples) * 100 if samples else 0
                }
            }
            
            # Get the report file path using config manager
            report_path = config_manager.get_quality_report_file(area, nature)
            
            # Ensure the directory exists
            report_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Save the report
            with report_path.open('w', encoding='utf-8') as f:
                json.dump(report, f, indent=2)
            
            logger.info(f"Saved quality report to {report_path}")
            
            # Log summary statistics
            logger.info(f"Summary for {area}/{nature}:")
            logger.info(f"  - Total samples: {len(samples)}")
            logger.info(f"  - Unique samples: {metrics['unique_samples']} ({metrics['uniqueness_ratio']:.1%})")
            logger.info(f"  - Valid samples: {validation_summary['valid_samples']}/{validation_summary['samples_validated']} ({validation_summary['validity_rate']:.1%})")
            logger.info(f"  - Average overall score: {validation_summary['overall_score_mean']:.2f}")
            if validation_summary['average_scores']:
                logger.info("  - Average dimension scores:")
                for score_type in ['relevance', 'consistency', 'correctness', 'completeness', 'realism']:
                    if score_type in validation_summary['average_scores']:
                        logger.info(f"    - {score_type.capitalize()}: {validation_summary['average_scores'][score_type]:.2f}")
            
        except FileNotFoundError as e:
            logger.error(f"Error: {e}")
            continue
        except Exception as e:
            logger.error(f"Unexpected error evaluating {area}/{nature}: {e}", exc_info=True)
            continue

    logger.info("Completed quality evaluation of large samples")


if __name__ == '__main__':
    main()