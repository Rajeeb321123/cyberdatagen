import os
import json
import random
from pathlib import Path
from dotenv import load_dotenv
from langchain.chat_models import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage
import pandas as pd

# Load environment variables
load_dotenv()

# Paths
PROBLEMS_PATH = Path('./config/problems.json')
LARGE_SAMPLES_DIR = Path('./data/large_samples')
REPORTS_DIR = Path('./data/quality_reports')
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# Initialize LLM
api_key = os.getenv('OPENAI_API_KEY')
chat = ChatOpenAI(temperature=0, openai_api_key=api_key)


def load_problems():
    data = json.loads(PROBLEMS_PATH.read_text(encoding='utf-8'))
    return data.get('problems', [])


def load_samples(nature: str):
    file_path = LARGE_SAMPLES_DIR / f"{nature}_large.json"
    if not file_path.exists():
        raise FileNotFoundError(f"Large samples not found: {file_path}")
    data = json.loads(file_path.read_text(encoding='utf-8'))
    return data.get('samples', [])


def automated_metrics(samples):
    total = len(samples)
    # Unique count by serialized sample
    unique_count = len({json.dumps(s, sort_keys=True) for s in samples})
    # Required keys from first sample
    req_keys = set(samples[0].keys()) if samples else set()
    missing_counts = sum(1 for s in samples if not req_keys.issubset(s.keys()))
    return {
        'total_samples': total,
        'unique_samples': unique_count,
        'uniqueness_ratio': unique_count / total if total else 0,
        'missing_keys_count': missing_counts
    }


def make_quality_system_prompt():
    return (
        "You are a synthetic data quality evaluator specializing in cybersecurity datasets. "
        "Assess the quality of generated samples in terms of realism, consistency, and adherence to schema."
    )


def make_quality_user_prompt(problem: dict, sample_snippet: list):
    snippet_json = json.dumps(sample_snippet, indent=2)
    return (
        f"Problem Nature: {problem['nature']} (Area: {problem['area']})\n"
        f"Description: {problem.get('description')}\n"
        "Here are a few sample entries:"
        f"\n{snippet_json}\n"
        "Please provide a JSON object with keys:\n"
        "- 'realism': comment on how realistic the samples are.\n"
        "- 'consistency': comment on uniformity and schema adherence.\n"
        "- 'suggestions': list of improvement suggestions.\n"
        "Return only valid JSON."
    )


def evaluate_with_llm(problem, samples, snippet_size=5):
    snippet = random.sample(samples, min(snippet_size, len(samples)))
    sys_msg = SystemMessage(content=make_quality_system_prompt())
    usr_msg = HumanMessage(content=make_quality_user_prompt(problem, snippet))
    response = chat([sys_msg, usr_msg])
    try:
        return json.loads(response.content)
    except json.JSONDecodeError:
        return {'realism': None, 'consistency': None, 'suggestions': [response.content]}


def main():
    problems = load_problems()
    for problem in problems:
        nature = problem['nature']
        print(f"Evaluating quality for {nature}...")
        samples = load_samples(nature)
        metrics = automated_metrics(samples)
        llm_eval = evaluate_with_llm(problem, samples)
        report = {
            'problem': {'area': problem['area'], 'nature': nature},
            'metrics': metrics,
            'llm_evaluation': llm_eval
        }
        report_path = REPORTS_DIR / f"{nature}_quality_report.json"
        with report_path.open('w', encoding='utf-8') as f:
            json.dump(report, f, indent=2)
        print(f"Saved quality report to {report_path}")

if __name__ == '__main__':
    main()
