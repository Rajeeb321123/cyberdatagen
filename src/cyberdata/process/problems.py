from pathlib import Path
import json
import os
from dotenv import load_dotenv

import json
import importlib


from langchain.prompts import PromptTemplate

from cyberdata.utils.llm_invoke import process_llm_request


# Correct: files() takes the package, then you "/" the filename
problem_init_path = files("cyberdata.config") / "problems_init.json"

with importlib.resources.path(
    "woagent.event_forecasting.apis", "api_description_full_cbm.py"
) as api_desc_file_path:
    api_description = open(api_desc_file_path, "r").read()

with problem_init_path.open(encoding="utf-8") as f:
    problem_init = json.load(f)  # ← this returns a dict

# pretty-print or get a JSON string:
problem_examples = json.dumps(problem_init, indent=4, ensure_ascii=False)


# System prompt: Contextualizes the LLM’s role and the cybersecurity domains
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

- "area": One of ["Enterprise", "Cloud", "EDTC"]
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
