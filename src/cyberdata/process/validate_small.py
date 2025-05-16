import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Import process_llm_request from your utility module
from cyberdata.utils.llm_invoke import process_llm_request

# Add parent directory to path for imports
CURRENT_DIR = Path(__file__).parent
PROJECT_ROOT = CURRENT_DIR.parent.parent.parent
sys.path.append(str(CURRENT_DIR.parent))  # Add cyberdata package to path

# Load environment variables
load_dotenv()

# Constants
MODEL_NAME = "gpt-4.1-mini"  # Match with small_dataset.py
PROBLEMS_PATH = CURRENT_DIR.parent / 'config' / 'problems.json'
SEEDS_DIR = PROJECT_ROOT / 'data' / 'seeds'
VALIDATION_DIR = PROJECT_ROOT / 'data' / 'validation_reports'
VALIDATION_DIR.mkdir(parents=True, exist_ok=True)


def load_problems(file_path: Path = PROBLEMS_PATH) -> list:
    """Load problem definitions from config."""
    if not file_path.exists():
        raise FileNotFoundError(f"Missing problems config: {file_path}")
    data = json.loads(file_path.read_text(encoding='utf-8'))
    return data.get('problems', [])


def make_system_prompt(problem: dict, example: dict) -> str:
    """
    System prompt to instruct the LLM on validation criteria.
    """
    return f"""
You are a cybersecurity data validation assistant. 
Your task is to assess whether the given sample correctly represents the stated cybersecurity problem and to provide detailed feedback.

Problem:
- Area: {problem['area']}
- Nature: {problem['nature']}
- Description: {problem.get('description')}
- Risk Reduction: {', '.join(problem.get('risk_reduction', []))}

Validation criteria:
1. Correctness: Does the sample align with the problem nature?
2. Realism: Is the example plausible in a real-world scenario?
3. Completeness: Are all required fields present and accurately populated?
4. Indicators: Do the indicators clearly explain why the sample matches the problem?
"""


def make_user_prompt(example: dict) -> str:
    """
    User prompt embedding the example to be validated.
    """
    # Serialize example to JSON string
    example_json = json.dumps(example, indent=2)
    return f"""
Please validate the following sample and return a JSON object with keys:
- 'valid': boolean, whether the sample is valid.
- 'issues': list of strings describing any problems or missing elements.
- 'comments': detailed feedback on improvements.

Sample:
{example_json}

Return only valid JSON.
"""


def validate_example(problem: dict, example: dict) -> dict:
    """
    Call the LLM to validate a single example.
    """
    system_content = make_system_prompt(problem, example)
    user_content = make_user_prompt(example)
    
    # Use process_llm_request instead of direct model call
    response_content = process_llm_request(
        system_prompt=system_content,
        user_prompt=user_content,
        model_name=MODEL_NAME,
        temperature=0.0  # Use 0 for consistent validation
    )
    
    # Parse and return the JSON response
    try:
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
                    
        return json.loads(response_content)
    except json.JSONDecodeError:
        # If parsing fails, wrap raw content
        return {"valid": False, "issues": ["Invalid JSON response"], "comments": response_content}


def find_examples_file(problem):
    """
    Find the examples file for a specific problem.
    """
    area = problem['area']
    nature = problem['nature']
    
    # Create a sanitized version of area and nature for filename matching
    sanitized_area = area.replace(' ', '_').replace('(', '').replace(')', '').replace('-', '_')
    sanitized_nature = nature.replace(' ', '_')
    
    # Check for the file in the area-specific directory
    area_dir = SEEDS_DIR / sanitized_area
    if area_dir.exists():
        filename = f"{sanitized_nature}_examples.json"
        example_file = area_dir / filename
        
        if example_file.exists():
            return example_file
    
    # If not found, try looking for the file in other area directories
    for dir_path in SEEDS_DIR.glob('*'):
        if dir_path.is_dir():
            for file_path in dir_path.glob('*.json'):
                if sanitized_nature.lower() in file_path.name.lower():
                    return file_path
            
    return None


def main():
    # Load problem definitions
    problems = load_problems()
    
    for problem in problems:
        area = problem['area']
        nature = problem['nature']
        print(f"Validating samples for problem: {area}/{nature}...")
        
        # Find the examples file for this problem
        example_file_path = find_examples_file(problem)
        
        if not example_file_path:
            print(f"Examples file not found for problem {nature}, skipping.")
            continue
        
        # Load examples
        with example_file_path.open('r', encoding='utf-8') as f:
            examples_data = json.load(f)
            examples = examples_data.get('examples', [])
        
        if not examples:
            print(f"No examples found in {example_file_path}, skipping.")
            continue
            
        report = []
        for idx, example in enumerate(examples):
            print(f"  Validating example {idx+1}/{len(examples)}...")
            
            result = validate_example(problem, example)
            
            entry = {
                "index": idx,
                "problem": {
                    "area": problem['area'],
                    "nature": nature
                },
                "example": example,
                "validation": result
            }
            report.append(entry)
        
        # Create area-specific directory structure for validation reports
        sanitized_area = area.replace(' ', '_').replace('(', '').replace(')', '').replace('-', '_')
        sanitized_nature = nature.replace(' ', '_')
        
        # Create area directory in validation reports
        area_validation_dir = VALIDATION_DIR / sanitized_area
        area_validation_dir.mkdir(parents=True, exist_ok=True)
        
        # Create filename for the report
        report_filename = f"{sanitized_nature}_validation.json"
        
        # Save validation report
        report_path = area_validation_dir / report_filename
        with report_path.open('w', encoding='utf-8') as f:
            json.dump({"report": report}, f, indent=2)
        
        print(f"Saved validation report for {area}/{nature} to {report_path}")


if __name__ == '__main__':
    main()