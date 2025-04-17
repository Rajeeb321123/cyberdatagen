import json
from pathlib import Path
import os
from dotenv import load_dotenv
from langchain.chat_models import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage

# The purpose of this code is to achieve a goal to generate a set of seeds for each problem. 
# It will loop over all the identified problem and use the samples as few-shots if they are availble for a given problem.

# Load environment variables
load_dotenv()

# Constants
PROBLEMS_PATH = './config/problems.json'
OUTPUT_DIR = './data/seeds'

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


def load_problems(file_path: str = PROBLEMS_PATH) -> list:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Missing problems config: {file_path}")
    data = json.loads(path.read_text(encoding='utf-8'))
    return data.get('problems', [])


def generate_examples_for_problem(problem: dict, chat_model) -> list:
    sys_msg = SystemMessage(content=make_system_prompt(problem))
    usr_msg = HumanMessage(content=make_user_prompt())
    response = chat_model([sys_msg, usr_msg])
    # Parse JSON
    content = response.content.strip()
    return json.loads(content)


def save_examples(nature: str, examples: list):
    out_dir = Path(OUTPUT_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    file_path = out_dir / f"{nature}_examples.json"
    with file_path.open('w', encoding='utf-8') as f:
        json.dump({'examples': examples}, f, indent=2)
    print(f"Saved examples for {nature} to {file_path}")


def main():
    # Initialize model
    api_key = os.getenv('OPENAI_API_KEY')
    chat = ChatOpenAI(temperature=0.7, openai_api_key=api_key)

    problems = load_problems()
    for problem in problems:
        try:
            examples = generate_examples_for_problem(problem, chat)
            save_examples(problem['nature'], examples)
        except Exception as e:
            print(f"Error generating for {problem['nature']}: {e}")

    print("All detailed examples have been generated in the 'data/detailed_examples' folder.")

if __name__ == '__main__':
    main()
