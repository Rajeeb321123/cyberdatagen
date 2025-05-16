import json
import os
import sys
import re
from pathlib import Path

from dotenv import load_dotenv

# Add parent directory to path for imports
CURRENT_DIR = Path(__file__).parent
PROJECT_ROOT = CURRENT_DIR.parent.parent.parent
sys.path.append(str(CURRENT_DIR.parent))  # Add cyberdata package to path

# Import process_llm_request from utility module
from cyberdata.utils.llm_invoke import process_llm_request

# Load environment variables
load_dotenv()

# Constants and paths
MODEL_NAME = "gpt-4.1-mini"  # Match with small_dataset.py
PROBLEMS_PATH = CURRENT_DIR.parent / 'config' / 'problems.json'
SEEDS_DIR = PROJECT_ROOT / 'data' / 'seeds'
OUTPUT_DIR = PROJECT_ROOT / 'data' / 'large_samples'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_problems(file_path: Path = PROBLEMS_PATH) -> list:
    """Load problem definitions from config."""
    if not file_path.exists():
        raise FileNotFoundError(f"Missing problems config: {file_path}")
    data = json.loads(file_path.read_text(encoding='utf-8'))
    return data.get('problems', [])


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


def load_examples(problem: dict) -> list:
    """
    Load few-shot examples for a given problem.
    
    Args:
        problem (dict): The problem dictionary containing 'area' and 'nature'
    
    Returns:
        list: The examples for the given problem
    """
    example_file = find_examples_file(problem)
    
    if not example_file or not example_file.exists():
        raise FileNotFoundError(f"Examples file not found for {problem['area']}/{problem['nature']}")
    
    data = json.loads(example_file.read_text(encoding='utf-8'))
    return data.get('examples', [])


def make_system_prompt() -> str:
    """
    Create the system prompt for generating synthetic data.
    
    Returns:
        str: The system prompt
    """
    return (
        "You are a cybersecurity synthetic data generator specialized in creating realistic, diverse examples. "
        "Given a few example samples of a specific cybersecurity problem, generate additional distinct samples following the same schema. "
        "Focus on technical accuracy and realism while maintaining the same structure as the examples. "
        "Keep your response concise and follow the JSON structure exactly. "
        "Return valid JSON with a key 'samples' containing an array of generated examples."
    )


def make_user_prompt(problem: dict, examples: list, n: int) -> str:
    """
    Construct the user prompt with examples and request count.
    
    Args:
        problem (dict): The problem definition
        examples (list): List of example samples
        n (int): Number of samples to generate
        
    Returns:
        str: The user prompt
    """
    # Only include essential fields from examples to avoid token limit issues
    simplified_examples = []
    for example in examples:
        # Keep only key fields to demonstrate structure
        simplified = {}
        exclude_fields = []  # Add fields to exclude if needed
        
        for key, value in example.items():
            if key not in exclude_fields:
                # If value is a large dict or complex structure, simplify it
                if isinstance(value, dict) and len(json.dumps(value)) > 500:
                    simplified[key] = f"[Complex structure with keys: {', '.join(value.keys())}]"
                elif isinstance(value, list) and len(json.dumps(value)) > 500:
                    simplified[key] = f"[List with {len(value)} items]"
                else:
                    simplified[key] = value
                    
        simplified_examples.append(simplified)
        
    examples_json = json.dumps(simplified_examples, indent=2)
    
    return (
        f"Problem Nature: {problem['nature']} (Area: {problem['area']})\n"
        f"Description: {problem.get('description')}\n"
        f"Seed Examples:\n{examples_json}\n"
        f"\nPlease generate {n} additional unique examples following the exact same structure as the examples. "
        f"Each example should include the same fields and maintain a similar level of detail. "
        f"Make sure the examples are realistic and technically accurate for {problem['nature']} scenarios. "
        "Do not include the original examples, only the newly generated ones. "
        "Keep the response concise by avoiding unnecessary fields or overly verbose content. "
        "Return ONLY valid, well-formed JSON with a 'samples' key containing an array of the generated examples."
    )


def extract_json_from_response(response_content: str) -> dict:
    """
    Extract valid JSON from LLM response that might contain markdown or other content.
    
    Args:
        response_content (str): The raw response content from the LLM
        
    Returns:
        dict: The extracted JSON object or None if extraction fails
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
        return json.loads(response_content)
    except json.JSONDecodeError:
        # Try alternative extraction methods
        
        # Try extracting JSON with regex
        json_pattern = r'\{[\s\S]*\}'
        match = re.search(json_pattern, response_content)
        if match:
            try:
                potential_json = match.group(0)
                return json.loads(potential_json)
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
            
            return json.loads(fixed_content)
        except json.JSONDecodeError:
            pass
        
        # Try a last-resort, more aggressive approach for nested JSON
        try:
            # Find the start of what looks like a JSON object
            start_idx = response_content.find('{"samples":')
            if start_idx != -1:
                # Try to reconstruct valid JSON with a simpler structure
                truncated_content = response_content[start_idx:]
                # Find a balanced number of brackets
                open_braces = 0
                close_braces = 0
                for idx, char in enumerate(truncated_content):
                    if char == '{':
                        open_braces += 1
                    elif char == '}':
                        close_braces += 1
                        if open_braces > 0 and open_braces == close_braces:
                            balanced_json = truncated_content[:idx+1]
                            return json.loads(balanced_json)
        except Exception:
            pass
        
        return None


def generate_for_problem(problem: dict, n: int = 10) -> list:
    """
    Generate n synthetic samples for the given problem.
    
    Args:
        problem (dict): The problem definition
        n (int): Number of samples to generate (default: 10)
        
    Returns:
        list: The generated samples
    """
    nature = problem['nature']
    area = problem['area']
    
    try:
        # Load examples from appropriate area subdirectory
        examples = load_examples(problem)
        
        # Simplify the structure of examples if they are too complex
        simplified_examples = []
        for example in examples:
            # Create a simplified version by removing deeply nested structures
            simplified = {}
            for key, value in example.items():
                # Keep simple fields and first level of nested objects
                if isinstance(value, dict) and any(isinstance(v, dict) for v in value.values()):
                    # If there are nested dictionaries within dictionaries, simplify
                    simplified[key] = {k: str(v) if isinstance(v, dict) else v 
                                      for k, v in value.items()}
                else:
                    simplified[key] = value
            simplified_examples.append(simplified)
        
        # Limit to 2 examples to avoid overwhelming the model
        if len(simplified_examples) > 2:
            simplified_examples = simplified_examples[:2]
        
        # Create prompts
        system_content = make_system_prompt()
        user_content = make_user_prompt(problem, simplified_examples, n)
        
        # Reduce sample count if the examples are complex
        actual_n = min(n, 5) if len(json.dumps(simplified_examples)) > 2000 else n
        if actual_n < n:
            print(f"Reducing sample count to {actual_n} due to complexity of examples")
            # Update the user prompt with the new count
            user_content = make_user_prompt(problem, simplified_examples, actual_n)
        
        # Use process_llm_request instead of direct OpenAI call
        response_content = process_llm_request(
            system_prompt=system_content,
            user_prompt=user_content,
            model_name=MODEL_NAME,
            temperature=0.7  # Higher temperature for diversity in generated samples
        )
        
        # Debug: Print response content before parsing
        print(f"Response for {problem['nature']} (first 100 chars): {response_content[:100]}...")
        
        # Parse and extract samples using the improved extraction function
        parsed = extract_json_from_response(response_content)
        
        if parsed is None:
            print(f"Failed to extract JSON from response for {nature}")
            return []
        
        samples = parsed.get('samples', [])
        
        if not samples:
            # Try again with a more direct approach
            print(f"No samples found in parsed JSON for {nature}, trying again with simpler prompt...")
            
            simplified_user_prompt = f"Generate {actual_n} simple examples of {nature} attacks. Return a JSON object with a 'samples' array."
            
            response_content = process_llm_request(
                system_prompt=system_content,
                user_prompt=simplified_user_prompt,
                model_name=MODEL_NAME,
                temperature=0.7
            )
            
            parsed = extract_json_from_response(response_content)
            if parsed:
                samples = parsed.get('samples', [])
        
        return samples
            
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return []
    except Exception as e:
        print(f"Unexpected error generating samples for {nature}: {e}")
        import traceback
        traceback.print_exc()
        return []


def save_samples(problem: dict, samples: list):
    """
    Save generated samples to a JSON file.
    
    Args:
        problem (dict): The problem definition
        samples (list): The generated samples
    """
    if not samples:
        print(f"No samples to save for {problem['nature']}")
        return
    
    area = problem['area']
    nature = problem['nature']
    
    # Create a sanitized version of area and nature for directory and filename
    sanitized_area = area.replace(' ', '_').replace('(', '').replace(')', '').replace('-', '_')
    sanitized_nature = nature.replace(' ', '_')
    
    # Create area directory
    area_dir = OUTPUT_DIR / sanitized_area
    area_dir.mkdir(parents=True, exist_ok=True)
    
    # Create filename
    filename = f"{sanitized_nature}_large.json"
    
    # Create output file path
    out_file = area_dir / filename
    
    # Save samples
    with out_file.open('w', encoding='utf-8') as f:
        json.dump({'samples': samples}, f, indent=2)
    
    print(f"Saved {len(samples)} samples to {out_file}")


def main(count: int = 10):
    """
    Main function to generate samples for all problems.
    
    Args:
        count (int): Number of samples to generate per problem (default: 10)
    """
    # Load problem definitions
    problems = load_problems()
    
    # Group problems by area for better organization in output
    areas = set(problem['area'] for problem in problems)
    print(f"Found {len(problems)} problems across {len(areas)} areas: {', '.join(areas)}")
    
    for problem in problems:
        area = problem['area']
        nature = problem['nature']
        print(f"Generating {count} samples for {area}/{nature}...")
        
        try:
            # Generate samples
            samples = generate_for_problem(problem, count)
            
            if not samples:
                print(f"No samples generated for {nature}, trying backup approach...")
                # Simplified backup approach
                system_prompt = (
                    "You are a cybersecurity example generator. Create simple examples "
                    "for the specified attack type. Return a JSON object with 'samples' array."
                )
                user_prompt = (
                    f"Generate {min(count, 5)} simple examples of {nature} attacks in the context of {area}. "
                    f"Description: {problem.get('description', '')}\n"
                    "Each example should have these fields: scenario, technical_data, indicators.\n"
                    "Return ONLY a valid JSON object with a 'samples' array containing the examples."
                )
                
                response_content = process_llm_request(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    model_name=MODEL_NAME,
                    temperature=0.7
                )
                
                parsed = extract_json_from_response(response_content)
                if parsed:
                    samples = parsed.get('samples', [])
            
            # Save samples
            save_samples(problem, samples)
            
        except Exception as e:
            print(f"Error during sample generation for {nature}: {e}")
            import traceback
            traceback.print_exc()
            continue  # Continue with the next problem
    
    print("Sample generation completed.")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate synthetic cybersecurity data samples")
    parser.add_argument('--count', type=int, default=10, help='Number of samples to generate per problem (default: 10)')
    parser.add_argument('--problems', nargs='+', help='Specific problem natures to generate samples for (optional)')
    
    args = parser.parse_args()
    
    if args.problems:
        # Filter problems by specified natures
        all_problems = load_problems()
        problems = [p for p in all_problems if p['nature'] in args.problems]
        
        if not problems:
            print(f"No matching problems found for {args.problems}")
            sys.exit(1)
            
        for problem in problems:
            area = problem['area']
            nature = problem['nature']
            print(f"Generating {args.count} samples for {area}/{nature}...")
            
            try:
                samples = generate_for_problem(problem, args.count)
                save_samples(problem, samples)
            except Exception as e:
                print(f"Error: {e}")
                import traceback
                traceback.print_exc()
        
        print("Sample generation completed.")
    else:
        main(args.count)