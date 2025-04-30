import json
import os
import sys
import re
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

# Import process_llm_request from your utility module
from cyberdata.utils.llm_invoke import process_llm_request

# Add parent directory to path for imports
CURRENT_DIR = Path(__file__).parent
PROJECT_ROOT = CURRENT_DIR.parent.parent.parent
sys.path.append(str(CURRENT_DIR.parent))  # Add cyberdata package to path

# The purpose of this code is to achieve a goal to generate a set of seeds for each problem. 
# It will loop over all the identified problem and use the samples as few-shots if they are availble for a given problem.

# Load environment variables
load_dotenv()

# Update paths to match new project structure
# Assuming the script is in project_folder/src/cyberdata/process/
# And problems.json is in project_folder/src/cyberdata/config/
PROBLEMS_PATH = CURRENT_DIR.parent / 'config' / 'problems.json'
SEEDS_BASE_DIR = PROJECT_ROOT / 'data' / 'seeds'

# Create the base output directory if it doesn't exist
SEEDS_BASE_DIR.mkdir(parents=True, exist_ok=True)

# Model configuration
MODEL_NAME = "gpt-4.1-mini"  # Used in logging but not needed for API calls now

# Prompts
def make_system_prompt(problem: dict) -> str:
    return f"""
You are a cybersecurity expert. Generate realistic, detailed examples for the following problem.

Problem:
- Area: {problem['area']}
- Nature: {problem['nature']}
- Description: {problem.get('description')}
- Risk Reduction: {', '.join(problem.get('risk_reduction', []))}

Output a JSON array named `examples` with 2–3 items. Each item should be a JSON object containing fields relevant to the problem type (e.g., a phishing email, a data exfiltration event, etc.), and an `indicators` list explaining why it represents the problem. Return only valid JSON.
"""


def make_user_prompt() -> str:
    return """
Generate the JSON as specified, without additional explanation.
"""


def load_problems(file_path: Path = PROBLEMS_PATH) -> list:
    if not file_path.exists():
        raise FileNotFoundError(f"Missing problems config: {file_path}")
    data = json.loads(file_path.read_text(encoding='utf-8'))
    return data.get('problems', [])


def extract_json_from_response(response_content: str) -> dict:
    """
    Extract valid JSON from LLM response that might contain markdown or other content.
    """
    # Clean up content by removing markdown code blocks if present
    if response_content.startswith('```'):
        # Find the first and last backtick groups
        first_backticks_end = response_content.find('\n', 3)
        if first_backticks_end != -1:
            # Find the closing backticks
            last_backticks_start = response_content.rfind('```')
            if last_backticks_start > first_backticks_end:
                # Extract the content between the backticks
                response_content = response_content[first_backticks_end + 1:last_backticks_start].strip()
            else:
                # Just remove the first backticks line if no closing backticks found
                response_content = response_content[first_backticks_end + 1:].strip()
    
    # Try direct JSON parsing
    try:
        examples = json.loads(response_content)
        # Check if we have 'examples' key in the response
        if 'examples' in examples:
            return examples['examples']
        else:
            return examples  # Assume the response is the examples array directly
    except json.JSONDecodeError:
        # Try alternative extraction methods
        
        # Try extracting JSON with regex
        json_pattern = r'\{[\s\S]*\}'
        match = re.search(json_pattern, response_content)
        if match:
            try:
                potential_json = match.group(0)
                examples = json.loads(potential_json)
                if 'examples' in examples:
                    return examples['examples']
                else:
                    return examples
            except json.JSONDecodeError:
                pass
        
        # Try fixing common JSON issues
        try:
            # Replace single quotes with double quotes
            fixed_content = response_content.replace("'", '"')
            # Fix missing commas after closing braces in arrays
            fixed_content = re.sub(r'}\s*{', '},{', fixed_content)
            # Fix trailing commas in arrays/objects
            fixed_content = re.sub(r',\s*}', '}', fixed_content)
            fixed_content = re.sub(r',\s*]', ']', fixed_content)
            
            examples = json.loads(fixed_content)
            if 'examples' in examples:
                return examples['examples']
            else:
                return examples
        except json.JSONDecodeError:
            pass
        
        # If all extraction methods fail, raise exception
        print(f"Failed to extract JSON from: {response_content[:100]}...")
        raise ValueError("Could not extract valid JSON from model response")


def generate_examples_for_problem(problem: dict) -> list:
    """Generate examples for a problem using process_llm_request function"""
    system_content = make_system_prompt(problem)
    user_content = make_user_prompt()
    
    # Use process_llm_request instead of direct OpenAI call
    response_content = process_llm_request(
        system_prompt=system_content,
        user_prompt=user_content,
        model_name=MODEL_NAME,
        temperature=0.7
    )
    
    # Debug: Print response content before parsing
    print(f"Response for {problem['nature']}: {response_content[:100]}...")
    
    try:
        # Use the enhanced JSON extraction
        examples = extract_json_from_response(response_content)
        return examples
    except Exception as e:
        print(f"JSON parse error for {problem['nature']}: {str(e)}")
        print(f"Response content: {response_content}")
        # If JSON extraction fails completely, return empty list
        # This allows the script to continue with other problems
        return []


def json_to_csv_single_file(json_file_path, csv_file_path, examples=None):
    """
    Convert a single JSON file to CSV.
    
    Args:
        json_file_path (Path): Path to the JSON file
        csv_file_path (Path): Path to save the CSV file
        examples (list, optional): If provided, use these examples instead of loading from file
    """
    try:
        # If examples are not provided, load them from the file
        if examples is None:
            with open(json_file_path, 'r') as f:
                data = json.load(f)
                examples = data.get('examples', [])
        
        if not examples:
            print(f"No examples found for {json_file_path.name}")
            return
        
        # Convert to DataFrame with flattened structure
        flattened_data = []
        for example in examples:
            # Handle indicators which is typically a list
            if 'indicators' in example and isinstance(example['indicators'], list):
                example = example.copy()  # Create a copy to avoid modifying the original
                example['indicators'] = '; '.join(example['indicators'])
            
            # Handle other potential list fields (dynamically)
            example_copy = example.copy()  # Create a copy to avoid modifying during iteration
            for key, value in example.items():
                if isinstance(value, list):
                    example_copy[key] = '; '.join(str(item) for item in value)
            
            flattened_data.append(example_copy)
        
        # Create DataFrame
        df = pd.DataFrame(flattened_data)
        
        # Save to CSV
        df.to_csv(csv_file_path, index=False)
        
    except Exception as e:
        print(f"Error processing {json_file_path}: {e}")
        raise


def save_examples(problem: dict, examples: list):
    """
    Save examples to JSON and CSV files in area-specific directories.
    
    Args:
        problem (dict): Problem dictionary containing 'area' and 'nature'
        examples (list): List of examples to save
    """
    # Skip if no valid examples
    if not examples:
        print(f"No valid examples to save for {problem['nature']}")
        return
    
    area = problem['area']
    nature = problem['nature']
    
    # Create area directory structure
    area_dir = SEEDS_BASE_DIR / area
    json_dir = area_dir / 'json'
    csv_dir = area_dir / 'csv'
    
    # Create directories if they don't exist
    json_dir.mkdir(parents=True, exist_ok=True)
    csv_dir.mkdir(parents=True, exist_ok=True)
    
    # Save JSON file
    json_file_path = json_dir / f"{nature}_examples.json"
    with json_file_path.open('w', encoding='utf-8') as f:
        json.dump({'examples': examples}, f, indent=2)
    print(f"Saved examples for {nature} to {json_file_path}")
    
    # Convert to CSV immediately after saving
    try:
        # Convert just this one JSON file to CSV
        csv_file_path = csv_dir / f"{nature}_examples.csv"
        json_to_csv_single_file(json_file_path, csv_file_path, examples)
        print(f"Converted {nature} examples to CSV at {csv_file_path}")
    except Exception as e:
        print(f"Error during CSV conversion for {nature}: {e}")


def main():
    """Main function to generate examples for all problems"""
    problems = load_problems()
    
    # Group problems by area for better organization in output
    areas = set(problem['area'] for problem in problems)
    print(f"Found {len(problems)} problems across {len(areas)} areas: {', '.join(areas)}")
    
    for problem in problems:
        try:
            area = problem['area']
            nature = problem['nature']
            print(f"Generating examples for {area}/{nature}...")
            examples = generate_examples_for_problem(problem)
            save_examples(problem, examples)
        except Exception as e:
            print(f"Error generating for {problem['area']}/{problem['nature']}: {e}")
            continue  # Continue with the next problem

    print(f"All detailed examples have been generated in '{SEEDS_BASE_DIR}'.")
    print("Directory structure:")
    for area in areas:
        print(f"  {area}/")
        print(f"    ├── json/")
        print(f"    └── csv/")


if __name__ == '__main__':
    main()