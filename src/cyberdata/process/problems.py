import json
import os
import re
from pathlib import Path
import csv

from dotenv import load_dotenv

# These would be your actual project imports
from cyberdata.utils.llm_invoke import process_llm_request
from cyberdata.utils.logger_config import setup_logger
from cyberdata.utils.prompt_loader import load_system_prompt, load_user_prompt
from cyberdata.utils.config_manager import get_config_manager

# --- Mock implementations for standalone execution ---
# In your actual project, you would remove these mock functions.

# def process_llm_request(system_prompt, user_prompt):
#     """Mocks a call to a Large Language Model."""
#     logger.info("Mock LLM call with system prompt and user prompt.")
#     return """
# ```json
# {
#   "problems": [
#     {
#       "area": "IoT",
#       "nature": "default_credentials",
#       "description": "A new line of smart cameras is shipped with default, publicly known administrator credentials, allowing attackers to easily gain access and view camera feeds.",
#       "risk_reduction": [
#         "Force credential change on first use",
#         "Implement a credential strength meter",
#         "Educate users on the importance of changing default passwords"
#       ]
#     },
#     {
#       "area": "Mobile",
#       "nature": "insecure_data_storage",
#       "description": "A mobile banking application stores the user's session token in a publicly accessible file on the device's local storage, allowing other apps to steal it.",
#       "risk_reduction": [
#         "Use secure storage mechanisms like the Android Keystore or iOS Keychain",
#         "Encrypt all sensitive data stored on the device",
#         "Do not store long-lived tokens on the client-side"
#       ]
#     }
#   ]
# }
# ```
# """

# def setup_logger(name):
#     """Mocks the logger setup."""
#     import logging
#     logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
#     return logging.getLogger(name)

# def load_system_prompt(name):
#     """Mocks loading a system prompt."""
#     return "You are a cybersecurity training assistant."

# def load_user_prompt(name, problem_examples):
#     """Mocks loading a user prompt."""
#     return f"Generate new problems based on these examples:\n{problem_examples}"

# # --- End of Mock implementations ---


# Set up logger
logger = setup_logger("cyberdata.scripts.problems")

# Load environment variables
load_dotenv()

# Get the config manager
config_manager = get_config_manager()

logger.info(f"Project root: {config_manager.project_root}")
logger.info(f"Config directory: {config_manager.config_dir}")
logger.info(f"Data directory: {config_manager.data_dir}")

# Load problems_init.json using the config manager
try:
    problem_init = config_manager.load_config_file("problems_init")
    logger.debug(f"Loaded problem init with {len(problem_init.get('problems', []))} problems")
except FileNotFoundError:
    logger.error("problems_init.json not found in config directory")
    raise

# pretty-print or get a JSON string:
problem_examples = json.dumps(problem_init, indent=4, ensure_ascii=False)

# Load prompts
logger.info("Loading prompts")
system_prompt = load_system_prompt("problems_prompts")
user_prompt = load_user_prompt("problems_prompts", problem_examples=problem_examples)

logger.info("Calling LLM to generate cybersecurity problems")
return_str = process_llm_request(system_prompt, user_prompt)

logger.info("Raw LLM response received.")

def extract_json(text):
    """Extract JSON from text that might contain markdown or other content."""
    logger.debug("Extracting JSON from LLM response")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.debug("Direct JSON parsing failed, trying alternative methods")
        pass
    
    json_pattern = r'```(?:json)?\s*([\s\S]*?)```'
    match = re.search(json_pattern, text)
    if match:
        try:
            extracted_json = match.group(1)
            logger.debug(f"Extracted JSON from markdown code block: {extracted_json[:100]}...")
            return json.loads(extracted_json)
        except json.JSONDecodeError:
            logger.debug("JSON parsing from markdown code block failed")
            pass
    
    try:
        start_idx = text.find('{')
        if start_idx != -1:
            brace_count = 0
            for i in range(start_idx, len(text)):
                if text[i] == '{':
                    brace_count += 1
                elif text[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        json_str = text[start_idx:i+1]
                        logger.debug(f"Extracted JSON by brace matching: {json_str[:100]}...")
                        return json.loads(json_str)
    except Exception as e:
        logger.debug(f"JSON extraction by brace matching failed: {str(e)}")
        pass
    
    logger.warning("Could not extract valid JSON from the response")
    return None

def save_problems_to_csv(problems_data: dict, system_prompt: str, user_prompt: str, data_dir: Path):
    """
    Saves the generated problems and prompts to a CSV file. Appends if the file exists.
    The entire list of problems is saved as a single JSON string in one column.
    """
    # Define the path to the CSV file within the data directory
    file_path = data_dir / "problems.csv"
    file_exists = file_path.exists()
    logger.info(f"Attempting to save problems to {file_path}")

    try:
        # Open the file in append mode
        with open(file_path, 'a', newline='', encoding='utf-8') as csvfile:
            # Define the new headers
            headers = ["system", "user", "assistant"]
            writer = csv.DictWriter(csvfile, fieldnames=headers)

            # If the file is new, write the header row first
            if not file_exists:
                writer.writeheader()

            # Get the list of problems
            problems_list = problems_data.get("problems", [])
            
            # Convert the entire list of problems to a single JSON string
            problems_generated_str = json.dumps(problems_list)

            # Prepare the single row to write
            row = {
                "system": system_prompt,
                "user": " Generate new cybersecurity problems.",
                "assistant": problems_generated_str
            }
            writer.writerow(row)
            
        logger.info(f"Successfully saved/appended problems data to {file_path}")
    except IOError as e:
        logger.error(f"Failed to write to CSV file {file_path}: {e}")

# Main execution block
try:
    problems_data = extract_json(return_str)
    
    if problems_data is None:
        logger.error("Could not extract valid JSON from the response.")
        logger.debug(f"Raw response: {return_str}")
        
        # Fallback to using an existing problems.json file if JSON extraction fails
        if config_manager.problems_file.exists():
            logger.warning(f"Using existing problems.json as fallback")
            problems_data = config_manager.load_config_file("problems")
            logger.info(f"Loaded {len(problems_data.get('problems', []))} problems from existing file")
        else:
            # If no valid data can be found, raise an error
            error_msg = "Failed to extract JSON and no fallback file is available."
            logger.error(error_msg)
            raise ValueError(error_msg)
    else:
        logger.info(f"Successfully extracted JSON with {len(problems_data.get('problems', []))} problems")
    
    # Save the extracted or fallback data to the CSV file
    save_problems_to_csv(problems_data, system_prompt, user_prompt, config_manager.data_dir)
    
    # Optionally, you can still save the latest problems to a JSON file as well
    config_manager.save_problems(problems_data['problems'], filename="problems")
    
except Exception as e:
    logger.critical(f"An error occurred during script execution: {str(e)}", exc_info=True)
    logger.debug(f"Raw response at time of error: {return_str}")
