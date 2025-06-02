# cyberdata/scripts/extend_problems.py

import json
import os
import sys
import re
from pathlib import Path
from datetime import datetime

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
logger = setup_logger("cyberdata.scripts.extend_problems")

# Load environment variables
load_dotenv()

# Constants
MODEL_NAME = "gpt-4.1-mini"

# Get config manager instance
config_manager = get_config_manager()

logger.info(f"Using model: {MODEL_NAME}")
logger.info(f"Project root: {config_manager.project_root}")
logger.info(f"Config directory: {config_manager.config_dir}")


def load_existing_problems():
    """Load existing problems from problems.json"""
    try:
        problems = config_manager.load_problems(prefer_updated=False)  # Load original problems.json
        logger.info(f"Loaded {len(problems)} problems")
        return problems
    except FileNotFoundError:
        logger.error(f"Problems file not found in {config_manager.config_dir}")
        raise
    except Exception as e:
        logger.error(f"Error loading problems: {str(e)}", exc_info=True)
        raise


def extract_json_from_response(response_content):
    """Extract JSON from LLM response that might contain markdown or other formatting"""
    logger.debug("Extracting JSON from evaluation response")
    
    # Try direct JSON parsing first
    try:
        return json.loads(response_content)
    except json.JSONDecodeError:
        logger.debug("Direct JSON parsing failed, trying alternative methods")
        pass
    
    # Remove markdown code blocks if present
    if '```' in response_content:
        logger.debug("Response contains code blocks, cleaning up")
        pattern = r'```(?:json)?\s*([\s\S]*?)```'
        matches = re.findall(pattern, response_content)
        if matches:
            response_content = matches[0]
            logger.debug("Extracted content from code block")
    
    # Try parsing cleaned content
    try:
        return json.loads(response_content)
    except json.JSONDecodeError as e:
        logger.warning(f"JSON parsing failed: {str(e)}")
        
        # Try to extract JSON object by finding braces
        try:
            start_idx = response_content.find('{')
            if start_idx != -1:
                # Find the matching closing brace
                brace_count = 0
                for i in range(start_idx, len(response_content)):
                    if response_content[i] == '{':
                        brace_count += 1
                    elif response_content[i] == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            json_str = response_content[start_idx:i+1]
                            logger.debug("Extracted JSON by brace matching")
                            return json.loads(json_str)
        except Exception as e:
            logger.warning(f"JSON extraction by brace matching failed: {str(e)}")
            pass
        
        # If all methods fail, raise an exception
        logger.error(f"Could not extract valid JSON from response")
        raise ValueError("Could not extract valid JSON from evaluation response")


def evaluate_problems(problems):
    """Use LLM to evaluate the existing problems"""
    logger.info("Starting LLM evaluation of existing problems")
    
    # Convert problems to JSON string for the prompt
    problems_json = json.dumps({"problems": problems}, indent=2)
    
    # Load prompts from YAML
    system_prompt = load_system_prompt("extension_prompts", prompt_name="evaluation")
    user_prompt = load_user_prompt("extension_prompts", prompt_name="evaluation", problems_json=problems_json)
    
    # Call LLM for evaluation
    logger.info("Calling LLM for problems evaluation")
    response_content = process_llm_request(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model_name=MODEL_NAME,
        temperature=0.3  # Slightly higher for more creative analysis
    )
    
    logger.debug(f"Evaluation response received, length: {len(response_content)} characters")
    
    # Extract and return JSON
    try:
        evaluation_result = extract_json_from_response(response_content)
        logger.info("Successfully extracted evaluation JSON")
        return evaluation_result
    except Exception as e:
        logger.error(f"Error extracting evaluation JSON: {str(e)}")
        # Return a basic structure if parsing fails
        return {
            "evaluation_summary": "Error parsing LLM response",
            "raw_response": response_content,
            "error": str(e)
        }


def save_evaluation_report(evaluation_result):
    """Save the evaluation report to a JSON file"""
    logger.info(f"Saving evaluation report")
    
    # Add metadata to the report
    report_data = {
        "evaluation_metadata": {
            "timestamp": datetime.now().isoformat(),
            "model_used": MODEL_NAME,
            "evaluation_version": "1.0"
        },
        "evaluation_result": evaluation_result
    }
    
    try:
        # Save using config manager
        config_manager.save_config_file("problems_evaluation_report", report_data)
        logger.info(f"Evaluation report saved successfully")
    except Exception as e:
        logger.error(f"Error saving evaluation report: {str(e)}", exc_info=True)
        raise


def update_problems_based_on_evaluation(original_problems, evaluation_result):
    """Use LLM to update problems based on evaluation findings"""
    logger.info("Starting problems update based on evaluation")
    
    # Create JSON strings for the prompts
    original_json = json.dumps({"problems": original_problems}, indent=2)
    evaluation_json = json.dumps(evaluation_result, indent=2)
    
    # Load prompts from YAML
    system_prompt = load_system_prompt("extension_prompts", prompt_name="update")
    user_prompt = load_user_prompt(
        "extension_prompts", 
        prompt_name="update",
        original_json=original_json,
        evaluation_json=evaluation_json
    )
    
    # Call LLM for update
    logger.info("Calling LLM for problems update")
    response_content = process_llm_request(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model_name=MODEL_NAME,
        temperature=0.5  # Balanced creativity for good updates
    )
    
    logger.debug(f"Update response received, length: {len(response_content)} characters")
    
    # Extract and return updated problems
    try:
        updated_data = extract_json_from_response(response_content)
        updated_problems = updated_data.get('problems', [])
        logger.info(f"Successfully extracted {len(updated_problems)} updated problems")
        return updated_problems
    except Exception as e:
        logger.error(f"Error extracting updated problems JSON: {str(e)}")
        logger.warning("Returning original problems due to update failure")
        return original_problems


def save_updated_problems(updated_problems):
    """Save updated problems to a new JSON file"""
    logger.info(f"Saving updated problems")
    
    try:
        # Save using config manager
        config_manager.save_problems(updated_problems, "problems_updated")
        logger.info(f"Updated problems saved successfully")
        logger.info(f"Total problems in updated dataset: {len(updated_problems)}")
        
        # Log summary of areas
        areas = set(problem.get('area', 'Unknown') for problem in updated_problems)
        logger.info(f"Areas covered: {', '.join(sorted(areas))}")
        
    except Exception as e:
        logger.error(f"Error saving updated problems: {str(e)}", exc_info=True)
        raise


def generate_summary_report(original_problems, updated_problems, evaluation_result):
    """Generate a summary of changes made"""
    logger.info("Generating summary report")
    
    original_count = len(original_problems)
    updated_count = len(updated_problems)
    
    original_areas = set(p.get('area', 'Unknown') for p in original_problems)
    updated_areas = set(p.get('area', 'Unknown') for p in updated_problems)
    
    original_natures = set(p.get('nature', 'Unknown') for p in original_problems)
    updated_natures = set(p.get('nature', 'Unknown') for p in updated_problems)
    
    summary = {
        "summary": {
            "original_problems_count": original_count,
            "updated_problems_count": updated_count,
            "net_change": updated_count - original_count,
            "original_areas": sorted(list(original_areas)),
            "updated_areas": sorted(list(updated_areas)),
            "new_areas": sorted(list(updated_areas - original_areas)),
            "original_natures_count": len(original_natures),
            "updated_natures_count": len(updated_natures),
            "new_natures": sorted(list(updated_natures - original_natures))
        },
        "evaluation_highlights": {
            "evaluation_summary": evaluation_result.get("evaluation_summary", "No summary available"),
            "missing_threats_added": len(evaluation_result.get("missing_threats", [])),
            "merging_recommendations_count": len(evaluation_result.get("merging_recommendations", []))
        }
    }
    
    logger.info(f"Summary: {original_count} -> {updated_count} problems ({updated_count - original_count:+d})")
    logger.info(f"Areas: {len(original_areas)} -> {len(updated_areas)} ({len(updated_areas) - len(original_areas):+d})")
    logger.info(f"New areas added: {summary['summary']['new_areas']}")
    logger.info(f"New threat types: {len(summary['summary']['new_natures'])}")
    
    return summary


def main():
    """Main function to evaluate and extend problems"""
    logger.info("Starting problems evaluation and extension process")
    
    try:
        # Step 1: Load existing problems
        logger.info("Step 1: Loading existing problems")
        original_problems = load_existing_problems()
        
        # Step 2: Evaluate problems using LLM
        logger.info("Step 2: Evaluating problems with LLM")
        evaluation_result = evaluate_problems(original_problems)
        
        # Step 3: Save evaluation report
        logger.info("Step 3: Saving evaluation report")
        save_evaluation_report(evaluation_result)
        
        # Step 4: Update problems based on evaluation
        logger.info("Step 4: Updating problems based on evaluation")
        updated_problems = update_problems_based_on_evaluation(original_problems, evaluation_result)
        
        # Step 5: Save updated problems
        logger.info("Step 5: Saving updated problems")
        save_updated_problems(updated_problems)
        
        # Step 6: Generate and log summary
        logger.info("Step 6: Generating summary report")
        summary = generate_summary_report(original_problems, updated_problems, evaluation_result)
        
        # Print summary to console
        print("\n" + "="*60)
        print("PROBLEMS EVALUATION AND EXTENSION COMPLETED")
        print("="*60)
        print(f"Original problems: {summary['summary']['original_problems_count']}")
        print(f"Updated problems:  {summary['summary']['updated_problems_count']}")
        print(f"Net change:        {summary['summary']['net_change']:+d}")
        print(f"New areas:         {', '.join(summary['summary']['new_areas']) if summary['summary']['new_areas'] else 'None'}")
        print(f"New threat types:  {len(summary['summary']['new_natures'])}")
        print("\nFiles generated:")
        print(f"- Evaluation report: {config_manager.config_dir / 'problems_evaluation_report.json'}")
        print(f"- Updated problems:  {config_manager.problems_updated_file}")
        print("="*60)
        
        logger.info("Problems evaluation and extension completed successfully")
        
    except Exception as e:
        logger.error(f"Error in main process: {str(e)}", exc_info=True)
        print(f"\nError: {str(e)}")
        print("Check the logs for detailed error information.")
        raise


if __name__ == '__main__':
    main()