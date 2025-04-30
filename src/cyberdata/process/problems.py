import json
import os
from importlib.resources import files
from pathlib import Path

from dotenv import load_dotenv
from langchain.prompts import PromptTemplate

from cyberdata.utils.llm_invoke import process_llm_request

# Correct: files() takes the package, then you "/" the filename
problem_init_path = files("cyberdata.config") / "problems_init.json"

with problem_init_path.open(encoding="utf-8") as f:
    problem_init = json.load(f)  # ← this returns a dict

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

- "area": One of ["Phishing", "A man-in-the-middle (MITM) attack"]
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

return_str = process_llm_request(system_prompt, user_prompt)

print("output_problem:\n", return_str)

# Parse the returned string into a JSON object
try:
    problems_data = json.loads(return_str)
    
    output_path = files("cyberdata.config") / "problems.json"
    
    # Make sure parent directories exist
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open('w', encoding='utf-8') as f:
        json.dump(problems_data, f, indent=2, ensure_ascii=False)
    
    print(f"Successfully saved problems data to {output_path}")
    
except json.JSONDecodeError as e:
    print(f"Error: Could not parse the LLM response as JSON: {e}")
    print("Raw response:", return_str)