import os
import json
from pathlib import Path
from dotenv import load_dotenv
from langchain.chat_models import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage

# Load environment variables
load_dotenv()

# Paths
PROBLEMS_PATH = Path('./config/problems.json')
EXAMPLES_DIR = Path('./data/detailed_examples')
OUTPUT_DIR = Path('./data/large_samples')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Initialize LLM
api_key = os.getenv('OPENAI_API_KEY')
chat = ChatOpenAI(temperature=0.7, openai_api_key=api_key)


def load_problems() -> list:
    """Load problem definitions from config."""
    data = json.loads(PROBLEMS_PATH.read_text(encoding='utf-8'))
    return data.get('problems', [])


def load_examples(nature: str) -> list:
    """Load few-shot examples for a given problem nature."""
    file_path = EXAMPLES_DIR / f"{nature}_examples.json"
    if not file_path.exists():
        raise FileNotFoundError(f"Examples file not found: {file_path}")
    data = json.loads(file_path.read_text(encoding='utf-8'))
    return data.get('examples', [])


def make_system_prompt() -> str:
    return (
        "You are a cybersecurity synthetic data generator. "
        "Given a few realistic examples of a specific cybersecurity problem, generate additional distinct samples following the same schema. "
        "Return valid JSON with a key 'samples' containing an array of generated examples."
    )


def make_user_prompt(problem: dict, examples: list, n: int) -> str:
    """Construct the user prompt with examples and request count."""
    examples_json = json.dumps(examples, indent=2)
    return (
        f"Problem Nature: {problem['nature']} (Area: {problem['area']})\n"
        f"Seed Examples:\n{examples_json}\n"
        f"\nPlease generate {n} additional unique examples following the same structure. "
        "Do not include the original examples, only the newly generated ones."
    )


def generate_for_problem(problem: dict, n: int = 1000) -> list:
    """Generate n synthetic samples for the given problem."""
    nature = problem['nature']
    examples = load_examples(nature)

    sys_msg = SystemMessage(content=make_system_prompt())
    usr_msg = HumanMessage(content=make_user_prompt(problem, examples, n))
    response = chat([sys_msg, usr_msg])
    content = response.content.strip()
    # Parse JSON
    parsed = json.loads(content)
    return parsed.get('samples', [])


def main(count: int = 1000):
    problems = load_problems()
    for problem in problems:
        nature = problem.get('nature')
        print(f"Generating {count} samples for {nature}...")
        try:
            samples = generate_for_problem(problem, count)
            out_file = OUTPUT_DIR / f"{nature}_large.json"
            with out_file.open('w', encoding='utf-8') as f:
                json.dump({'samples': samples}, f, indent=2)
            print(f"Saved {len(samples)} samples to {out_file}")
        except Exception as e:
            print(f"Error generating samples for {nature}: {e}")

if __name__ == '__main__':
    main(1000)
