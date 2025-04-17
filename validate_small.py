import os
import json
from pathlib import Path
from dotenv import load_dotenv
from langchain.chat_models import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage

# This code aims to use LLM as an initial step to validate the generated seeds for each problem.  
# We expect the LLM to help separate valid, beneficial seeds from unuseful ones. 

# Load environment variables
load_dotenv()

# Constants
SEEDS_DIR = Path('./data/seeds')  # CSV or JSON files with sample data
OUTPUT_DIR = Path('./data/validation_reports')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Initialize chat model
api_key = os.getenv('OPENAI_API_KEY')
chat = ChatOpenAI(temperature=0, openai_api_key=api_key)


def make_system_prompt(example: dict) -> str:
    """
    System prompt to instruct the LLM on validation criteria.
    """
    return (
        "You are a cybersecurity data validation assistant. "
        "Your task is to assess whether the given sample correctly represents its stated cybersecurity problem and to provide detailed feedback.\n"
        "Validation criteria:\n"
        "1. Correctness: Does the sample align with the problem nature?\n"
        "2. Realism: Is the example plausible in a real-world scenario?\n"
        "3. Completeness: Are all required fields present and accurately populated?\n"
        "4. Indicators: Do the indicators clearly explain why the sample matches the problem?"
    )


def make_user_prompt(example: dict) -> str:
    """
    Human prompt embedding the example to be validated.
    """
    # Serialize example to JSON string
    example_json = json.dumps(example, indent=2)
    return f"Please validate the following sample and return a JSON object with keys:\n" \
           "- 'valid': boolean, whether the sample is valid.\n" \
           "- 'issues': list of strings describing any problems or missing elements.\n" \
           "- 'comments': detailed feedback on improvements.\n" \
           "Sample:\n{example_json}"


def validate_example(example: dict) -> dict:
    """
    Call the LLM to validate a single example.
    """
    sys_msg = SystemMessage(content=make_system_prompt(example))
    usr_msg = HumanMessage(content=make_user_prompt(example))
    response = chat([sys_msg, usr_msg])
    # Parse and return the JSON response
    try:
        return json.loads(response.content)
    except json.JSONDecodeError:
        # If parsing fails, wrap raw content
        return {"valid": False, "issues": ["Invalid JSON response"], "comments": response.content}


def main():
    # Load problem definitions to map to seed files
    problems = json.loads(Path('./config/problems.json').read_text(encoding='utf-8')).get('problems', [])
    for problem in problems:
        area = problem.get('area', '').lower()
        nature = problem.get('nature', '')
        seed_filename = f"{area}_{nature}_seed.csv"
        seed_path = SEEDS_DIR / seed_filename
        if not seed_path.exists():
            print(f"Seed file not found for problem {nature} at {seed_path}, skipping.")
            continue

        # Read CSV into examples
        import pandas as pd
        df = pd.read_csv(seed_path)
        examples = df.to_dict(orient='records')

        report = []
        print(f"Validating samples for problem: {nature}...")
        for idx, ex in enumerate(examples):
            # Enrich example with problem metadata
            example_payload = ex.copy()
            example_payload.update({
                'area': problem.get('area'),
                'nature': nature,
                'description': problem.get('description'),
                'risk_reduction': problem.get('risk_reduction')
            })
            result = validate_example(example_payload)
            entry = {
                "index": idx,
                "problem": {
                    "area": problem.get('area'),
                    "nature": nature
                },
                "example": ex,
                "validation": result
            }
            report.append(entry)

        # Save validation report specific to this problem
        report_path = OUTPUT_DIR / f"{area}_{nature}_validation.json"
        with report_path.open('w', encoding='utf-8') as f:
            json.dump({"report": report}, f, indent=2)
        print(f"Saved validation report for {nature} to {report_path}")

if __name__ == '__main__':
    main()
