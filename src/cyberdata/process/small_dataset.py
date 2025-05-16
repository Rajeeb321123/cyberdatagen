# cyberdata/scripts/small_dataset.py

import json
import os
import sys
import re
from pathlib import Path

from dotenv import load_dotenv

# Import process_llm_request from your utility module
from cyberdata.utils.llm_invoke import process_llm_request
from cyberdata.utils.logger_config import setup_logger

# Set up logger
logger = setup_logger("cyberdata.scripts.small_dataset")

# Add parent directory to path for imports
CURRENT_DIR = Path(__file__).parent
PROJECT_ROOT = CURRENT_DIR.parent.parent.parent
sys.path.append(str(CURRENT_DIR.parent))  # Add cyberdata package to path
logger.debug(f"Added {CURRENT_DIR.parent} to sys.path")

# The purpose of this code is to generate a set of seeds for each problem. 
# It will loop over all the identified problems and use the samples as few-shots if they are available for a given problem.

# Load environment variables
load_dotenv()

# Update paths to match new project structure
PROBLEMS_PATH = CURRENT_DIR.parent / 'config' / 'problems.json'
SEEDS_DIR = PROJECT_ROOT / 'data' / 'seeds'

logger.info(f"Problems path: {PROBLEMS_PATH}")
logger.info(f"Seeds directory: {SEEDS_DIR}")

# Create the output directory if it doesn't exist
SEEDS_DIR.mkdir(parents=True, exist_ok=True)
logger.info(f"Created seeds directory: {SEEDS_DIR}")

# Model configuration
MODEL_NAME = "gpt-4.1-mini"  # Used in logging but not needed for API calls now
logger.info(f"Using model: {MODEL_NAME}")

# Enhanced System Prompt for Realistic Cybersecurity Data Generation
def make_system_prompt(problem: dict) -> str:
    logger.debug(f"Creating system prompt for problem: {problem['nature']}")
    return f"""
You are an elite cybersecurity expert with extensive experience in security operations, threat intelligence, and incident response. Generate highly technical, realistic examples for the following cybersecurity problem:

Problem:
- Area: {problem['area']}
- Nature: {problem['nature']}
- Description: {problem.get('description')}
- Risk Reduction: {', '.join(problem.get('risk_reduction', []))}

For each example, include DETAILED TECHNICAL DATA that would appear in real-world scenarios, such as:

1. For network-based attacks (like SQL Injection, XSS):
   - Raw HTTP request/response data with headers, parameters, and payloads
   - Network packet captures in text format (similar to Wireshark output)
   - Log entries as they would appear in web servers, WAFs, or IDS/IPS
   - Actual exploit code or injection strings

2. For phishing and social engineering:
   - Complete email content with headers, including X-headers showing routing
   - SMTP transaction logs
   - Domain registration details for suspicious domains
   - Exact URL structures with obfuscation techniques

3. For malware and system compromise:
   - File hashes (MD5, SHA-1, SHA-256)
   - Registry changes or file system artifacts
   - Memory dump analysis snippets
   - Command-and-control traffic patterns
   - Process creation and execution chains

4. For cloud security issues:
   - API call sequences that demonstrate the attack
   - IAM policy definitions showing misconfigurations
   - CloudTrail or equivalent logs showing suspicious activity
   - Container escape proof-of-concept details

Each example should be structured with:
1. "scenario": Brief description of the attack instance
2. "technical_data": Detailed technical information as described above
3. "indicators": Specific technical indicators of compromise
4. "detection_method": How this would be detected in practice
5. "relevant_mitre_techniques": MITRE ATT&CK techniques relevant to this example

Output a JSON array named `examples` with 2–3 detailed items. Each item must contain realistic technical data that a security professional would encounter during an actual security incident. Return only valid JSON.
"""


# Enhanced User Prompt
def make_user_prompt() -> str:
    logger.debug("Creating user prompt")
    return """
Generate technically-detailed examples with realistic data artifacts for the specified cybersecurity problem. 

For each example, provide realistic, copy-pastable technical data that a security professional would encounter in the wild. This includes actual packet contents, HTTP requests, log entries, suspicious code, command outputs, etc.

Include enough technical detail that these examples could be used for:
1. Training security analysts to recognize real attacks
2. Testing detection systems with realistic data
3. Creating high-fidelity simulations

Focus on technical accuracy and realism. Include enough detail to distinguish this from generic examples. Return valid JSON containing the `examples` array.
"""


def load_problems(file_path: Path = PROBLEMS_PATH) -> list:
    if not file_path.exists():
        logger.error(f"Missing problems config: {file_path}")
        raise FileNotFoundError(f"Missing problems config: {file_path}")
    
    data = json.loads(file_path.read_text(encoding='utf-8'))
    logger.info(f"Loaded {len(data.get('problems', []))} problems from {file_path}")
    return data.get('problems', [])


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
    
    system_content = make_system_prompt(problem)
    user_content = make_user_prompt()
    
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
    Save examples to JSON files
    
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
    
    # Create area directory
    sanitized_area = area.replace(' ', '_').replace('(', '').replace(')', '').replace('-', '_')
    sanitized_nature = nature.replace(' ', '_')
    area_dir = SEEDS_DIR / sanitized_area
    area_dir.mkdir(parents=True, exist_ok=True)
    logger.debug(f"Created area directory: {area_dir}")
    
    # Create a filename for the nature
    filename = f"{sanitized_nature}_examples.json"
    
    # Save JSON file
    json_file_path = area_dir / filename
    with json_file_path.open('w', encoding='utf-8') as f:
        json.dump({'examples': examples}, f, indent=2)
    logger.info(f"Saved {len(examples)} examples for {area}/{nature} to {json_file_path}")


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

    logger.info(f"All detailed examples have been generated in '{SEEDS_DIR}'.")


if __name__ == '__main__':
    main()