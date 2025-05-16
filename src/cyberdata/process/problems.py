# cyberdata/scripts/problems.py

import json
import os
import re
from pathlib import Path
from importlib.resources import files

from dotenv import load_dotenv
from langchain.prompts import PromptTemplate

from cyberdata.utils.llm_invoke import process_llm_request
from cyberdata.utils.logger_config import setup_logger

# Set up logger
logger = setup_logger("cyberdata.scripts.problems")

# Load environment variables
load_dotenv()

# Get the project root directory
CURRENT_DIR = Path(__file__).parent
PROJECT_ROOT = Path(__file__).resolve().parent.parent  # src/cyberdata

# Define direct path to problems.json
PROBLEMS_OUTPUT_PATH = PROJECT_ROOT / "config" / "problems.json"

logger.info(f"Problems output path: {PROBLEMS_OUTPUT_PATH}")

# Correct: files() takes the package, then you "/" the filename
problem_init_path = files("cyberdata.config") / "problems_init.json"

logger.info(f"Problem init path: {problem_init_path}")

with problem_init_path.open(encoding="utf-8") as f:
    problem_init = json.load(f)  # ← this returns a dict
    logger.debug(f"Loaded problem init with {len(problem_init.get('problems', []))} problems")

# pretty-print or get a JSON string:
problem_examples = json.dumps(problem_init, indent=4, ensure_ascii=False)

# System prompt: Contextualizes the LLM's role and the cybersecurity domains
system_prompt_text = """
You are an expert cybersecurity analyst and synthetic data engineer. Your mission is to help catalog and generate synthetic datasets for critical cybersecurity challenges across diverse operational environments.

Operational areas:
- **Enterprise**
- **Cloud**
- **Personal**

For each problem you describe, include:
1. **nature**: The specific category or type (e.g., phishing, data exfiltration, misconfiguration).
2. **description**: A concise but comprehensive overview of the issue.
3. **risk_reduction**: Concrete strategies or controls to mitigate the threat.
"""

# User prompt: Requests structured JSON output detailing each problem
user_prompt_text = """
Please generate a JSON object with a single key "problems", whose value is an array of problem entries. Each entry must include:

- "area": One of ["Phishing Attack", "Man-in-the-Middle (MITM) Attack"]
- "nature": A concise label for the problem category (e.g., "phishing", "misconfiguration").
- "description": A detailed explanation of the problem scenario.
- "risk_reduction": A list of recommended mitigation measures.

Include at least three problems per area. Return valid JSON only—no additional text.

Please refer this example of JSON file as format as well as the illlustrated examples.

{problem_examples}
"""

system_prompt_format = PromptTemplate(input_variables=[], template=system_prompt_text)

user_prompt_format = PromptTemplate(
    input_variables=["problem_examples"], template=user_prompt_text
)

system_prompt = system_prompt_format.format()
user_prompt = user_prompt_format.format(problem_examples=problem_examples)

logger.info("Calling LLM to generate cybersecurity problems")
return_str = process_llm_request(system_prompt, user_prompt)

logger.info("Raw LLM response received.")

# Clean up the response to extract valid JSON
def extract_json(text):
    """Extract JSON from text that might contain markdown or other content."""
    logger.debug("Extracting JSON from LLM response")
    # Try direct parsing first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.debug("Direct JSON parsing failed, trying alternative methods")
        pass
    
    # Try to extract JSON if it's wrapped in markdown code blocks
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
    
    # Try to find JSON-like content with { and } as delimiters
    try:
        start_idx = text.find('{')
        if start_idx != -1:
            # Find the matching closing brace
            brace_count = 0
            for i in range(start_idx, len(text)):
                if text[i] == '{':
                    brace_count += 1
                elif text[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        # Found the complete JSON object
                        json_str = text[start_idx:i+1]
                        logger.debug(f"Extracted JSON by brace matching: {json_str[:100]}...")
                        return json.loads(json_str)
    except Exception as e:
        logger.debug(f"JSON extraction by brace matching failed: {str(e)}")
        pass
    
    # Return None if no valid JSON could be extracted
    logger.warning("Could not extract valid JSON from the response")
    return None

# Try to parse the returned string into a JSON object
try:
    # First try to extract valid JSON from the response
    problems_data = extract_json(return_str)
    
    if problems_data is None:
        logger.error("Could not extract valid JSON from the response.")
        logger.debug(f"Raw response: {return_str}")
        
        # Fallback: Use existing problems.json if available
        if PROBLEMS_OUTPUT_PATH.exists():
            logger.warning(f"Using existing problems.json as fallback")
            with PROBLEMS_OUTPUT_PATH.open('r', encoding='utf-8') as f:
                problems_data = json.load(f)
                logger.info(f"Loaded {len(problems_data.get('problems', []))} problems from existing file")
        else:
            # If we can't even fallback, raise an exception
            error_msg = "Failed to extract JSON and no fallback available"
            logger.error(error_msg)
            raise ValueError(error_msg)
    else:
        logger.info(f"Successfully extracted JSON with {len(problems_data.get('problems', []))} problems")
    
    # Ensure the output directory exists
    PROBLEMS_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    # Remove the existing file if it exists
    if PROBLEMS_OUTPUT_PATH.exists():
        logger.info(f"Removing existing file: {PROBLEMS_OUTPUT_PATH}")
        PROBLEMS_OUTPUT_PATH.unlink()
    
    # Write the new data to the file
    with PROBLEMS_OUTPUT_PATH.open('w', encoding='utf-8') as f:
        json.dump(problems_data, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Successfully saved problems data to {PROBLEMS_OUTPUT_PATH}")
    
except Exception as e:
    logger.critical(f"Error: {str(e)}", exc_info=True)
    logger.debug(f"Raw response: {return_str}")