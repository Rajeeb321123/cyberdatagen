import json
import os
import sys
import re
from pathlib import Path
from datetime import datetime
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

# --- Mock implementations for standalone execution ---
# In your actual project, you would remove these mock functions.

# def process_llm_request(system_prompt, user_prompt, model_name, temperature):
#     """Mocks a call to a Large Language Model."""
#     logger.info(f"Mock LLM call for model {model_name} with temp {temperature}")
#     if "evaluation" in system_prompt:
#         # Mock response for evaluation
#         return """
#         ```json
#         {
#           "evaluation_summary": "The existing problems provide good coverage of enterprise and cloud threats but lack depth in IoT and mobile security. Some descriptions could be more detailed.",
#           "missing_threats": [
#             {"area": "IoT", "nature": "insecure_firmware_updates"},
#             {"area": "Mobile", "nature": "improper_certificate_validation"}
#           ],
#           "merging_recommendations": []
#         }
#         ```
#         """
#     else:
#         # Mock response for update
#         return """
#         ```json
#         {
#           "problems": [
#             {
#               "area": "Enterprise",
#               "nature": "phishing",
#               "description": "Employees receive targeted spear-phishing emails that appear to come from a known vendor, requesting urgent payment for a fake invoice. The messages contain malicious links that harvest login credentials when clicked.",
#               "risk_reduction": [
#                 "Enable multi-factor authentication (MFA) for all user accounts",
#                 "Deploy advanced email filtering and sandboxing to detect malicious links and attachments",
#                 "Run regular, targeted security awareness training and phishing simulations"
#               ]
#             },
#             {
#               "area": "Cloud",
#               "nature": "misconfigured_storage",
#               "description": "A misconfigured S3 bucket containing sensitive customer PII and internal documents is inadvertently left publicly readable, exposing the data to unauthorized access and download from the internet.",
#               "risk_reduction": [
#                 "Enforce automated checks for public-access settings using tools like AWS Config",
#                 "Use IAM policies and bucket policies to restrict access to known roles and IP ranges",
#                 "Enable bucket logging and use services like Amazon Macie to detect sensitive data exposure"
#               ]
#             }
#           ]
#         }
#         ```
#         """

# def setup_logger(name):
#     """Mocks the logger setup."""
#     import logging
#     logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
#     return logging.getLogger(name)

# def load_system_prompt(name, prompt_name):
#     """Mocks loading a system prompt."""
#     if prompt_name == "evaluation":
#         return "You are a cybersecurity curriculum evaluator."
#     return "You are a cybersecurity curriculum developer."

# def load_user_prompt(name, prompt_name, **kwargs):
#     """Mocks loading a user prompt."""
#     if prompt_name == "evaluation":
#         return f"Evaluate these problems: {kwargs.get('problems_json', '{}')}"
#     return f"Update these problems: {kwargs.get('original_json', '{}')} based on this evaluation: {kwargs.get('evaluation_json', '{}')}"

# # --- End of Mock implementations ---


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
        problems = config_manager.load_problems(prefer_updated=False)
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
    logger.debug("Extracting JSON from LLM response")
    try:
        return json.loads(response_content)
    except json.JSONDecodeError:
        logger.debug("Direct JSON parsing failed, trying regex")
        pass
    
    pattern = r'```(?:json)?\s*([\s\S]*?)```'
    match = re.search(pattern, response_content)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            logger.warning("JSON parsing from markdown block failed")
            pass

    logger.error(f"Could not extract valid JSON from response")
    raise ValueError("Could not extract valid JSON from LLM response")


def evaluate_problems(problems):
    """Use LLM to evaluate the existing problems and return the result and prompts."""
    logger.info("Starting LLM evaluation of existing problems")
    problems_json = json.dumps({"problems": problems}, indent=2)
    system_prompt = load_system_prompt("extension_prompts", prompt_name="evaluation")
    user_prompt = load_user_prompt("extension_prompts", prompt_name="evaluation", problems_json=problems_json)
    
    logger.info("Calling LLM for problems evaluation")
    response_content = process_llm_request(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model_name=MODEL_NAME,
        temperature=0.3
    )
    
    try:
        evaluation_result = extract_json_from_response(response_content)
        logger.info("Successfully extracted evaluation JSON")
        return evaluation_result, system_prompt, user_prompt
    except Exception as e:
        logger.error(f"Error extracting evaluation JSON: {str(e)}")
        return {"error": str(e), "raw_response": response_content}, system_prompt, user_prompt


def save_evaluation_report(evaluation_result, system_prompt, user_prompt):
    """Save the evaluation report to a JSON file and a CSV file."""
    logger.info(f"Saving evaluation report")
    
    # --- Save JSON Report (original functionality) ---
    report_data = {
        "evaluation_metadata": {"timestamp": datetime.now().isoformat(), "model_used": MODEL_NAME},
        "evaluation_result": evaluation_result
    }
    try:
        config_manager.save_config_file("problems_evaluation_report", report_data)
        logger.info(f"Evaluation JSON report saved successfully")
    except Exception as e:
        logger.error(f"Error saving evaluation JSON report: {str(e)}", exc_info=True)

    # --- Save CSV Report (new functionality) ---
    file_path = config_manager.data_dir / "evaluation.csv"
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
                "assistant": json.dumps(evaluation_result)
            }
            writer.writerow(row)
        logger.info(f"Successfully saved/appended evaluation data to {file_path}")
    except IOError as e:
        logger.error(f"Failed to write to evaluation CSV file {file_path}: {e}")


def update_problems_based_on_evaluation(original_problems, evaluation_result):
    """Use LLM to update problems and return the result and prompts."""
    logger.info("Starting problems update based on evaluation")
    original_json = json.dumps({"problems": original_problems}, indent=2)
    evaluation_json = json.dumps(evaluation_result, indent=2)
    
    system_prompt = load_system_prompt("extension_prompts", prompt_name="update")
    user_prompt = load_user_prompt(
        "extension_prompts", 
        prompt_name="update",
        original_json=original_json,
        evaluation_json=evaluation_json
    )
    
    logger.info("Calling LLM for problems update")
    response_content = process_llm_request(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model_name=MODEL_NAME,
        temperature=0.5
    )
    
    try:
        updated_data = extract_json_from_response(response_content)
        updated_problems = updated_data.get('problems', [])
        logger.info(f"Successfully extracted {len(updated_problems)} updated problems")
        return updated_problems, system_prompt, user_prompt
    except Exception as e:
        logger.error(f"Error extracting updated problems JSON: {str(e)}")
        return original_problems, system_prompt, user_prompt


def save_updated_problems(updated_problems, system_prompt, user_prompt):
    """Save updated problems to a JSON file and a CSV file."""
    logger.info(f"Saving updated problems")
    
    # --- Save JSON file (original functionality) ---
    try:
        config_manager.save_problems(updated_problems, "problems_updated")
        logger.info(f"Updated problems JSON saved successfully")
    except Exception as e:
        logger.error(f"Error saving updated problems JSON: {str(e)}", exc_info=True)

    # --- Save CSV file (new functionality) ---
    file_path = config_manager.data_dir / "problem_update.csv"
    file_exists = file_path.exists()
    try:
        with open(file_path, 'a', newline='', encoding='utf-8') as csvfile:
            headers = ["system_prompt", "user_prompt", "updated_problems"]
            writer = csv.DictWriter(csvfile, fieldnames=headers)
            if not file_exists:
                writer.writeheader()
            
            row = {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "updated_problems": json.dumps(updated_problems)
            }
            writer.writerow(row)
        logger.info(f"Successfully saved/appended updated problems data to {file_path}")
    except IOError as e:
        logger.error(f"Failed to write to problem update CSV file {file_path}: {e}")


def main():
    """Main function to evaluate and extend problems"""
    logger.info("Starting problems evaluation and extension process")
    
    try:
        # Step 1: Load
        original_problems = load_existing_problems()
        
        # Step 2: Evaluate
        evaluation_result, eval_sys_prompt, eval_user_prompt = evaluate_problems(original_problems)
        
        # Step 3: Save Evaluation
        save_evaluation_report(evaluation_result, eval_sys_prompt, eval_user_prompt)
        
        # Step 4: Update
        updated_problems, update_sys_prompt, update_user_prompt = update_problems_based_on_evaluation(original_problems, evaluation_result)
        
        # Step 5: Save Update
        save_updated_problems(updated_problems, update_sys_prompt, update_user_prompt)
        
        logger.info("Problems evaluation and extension completed successfully")
        
    except Exception as e:
        logger.critical(f"A critical error occurred in the main process: {str(e)}", exc_info=True)
        raise

if __name__ == '__main__':
    main()
