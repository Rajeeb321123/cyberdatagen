from pathlib import Path
import json
import os
from dotenv import load_dotenv
from langchain.prompts import PromptTemplate
from langchain.chat_models import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage

# Load environment variables from .env
load_dotenv()

# System prompt: Contextualizes the LLM’s role and the cybersecurity domains
system_prompt_text = '''
You are an expert cybersecurity analyst and synthetic data engineer. Your mission is to help catalog and generate synthetic datasets for critical cybersecurity challenges across diverse operational environments.

Operational areas:
- **Enterprise**
- **Cloud**
- **EDTC** (Education, Data, Technology, and Communications)

For each problem you describe, include:
1. **nature**: The specific category or type (e.g., phishing, data exfiltration, misconfiguration).
2. **description**: A concise but comprehensive overview of the issue.
3. **risk_reduction**: Concrete strategies or controls to mitigate the threat.
'''

# User prompt: Requests structured JSON output detailing each problem
user_prompt_text = '''
Please generate a JSON object with a single key "problems", whose value is an array of problem entries. Each entry must include:

- "area": One of ["Enterprise", "Cloud", "EDTC"]
- "nature": A concise label for the problem category (e.g., "phishing", "misconfiguration").
- "description": A detailed explanation of the problem scenario.
- "risk_reduction": A list of recommended mitigation measures.

Include at least three problems per area. Return valid JSON only—no additional text.

Please refer this example of JSON file as format as well as the illlustrated examples.

{problem_examples}
'''

# Create LangChain prompt templates
system_prompt = PromptTemplate(input_variables=[], template=system_prompt_text)
user_prompt = PromptTemplate(input_variables=[], template=user_prompt_text)


def get_system_prompt() -> str:
    """Format and return the system prompt."""
    return system_prompt.format()


def get_user_prompt() -> str:
    """Format and return the user prompt."""
    return user_prompt.format()


def generate_and_save_problems(file_path: str = './config/problems.json'):
    """
    Invoke the LLM to generate the problems JSON and save to the specified file path.
    """
    # Ensure output directory exists
    output_path = Path(file_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Initialize chat model with API key from environment
    api_key = os.getenv("OPENAI_API_KEY")
    chat = ChatOpenAI(temperature=0, openai_api_key=api_key)
    messages = [
        SystemMessage(content=get_system_prompt()),
        HumanMessage(content=get_user_prompt())
    ]

    # Call the model
    response = chat(messages)
    content = response.content.strip()

    # Save to file
    try:
        # Validate JSON
        parsed = json.loads(content)
        with output_path.open('w', encoding='utf-8') as f:
            json.dump(parsed, f, indent=2)
        print(f"Problems JSON successfully saved to {output_path}")
    except json.JSONDecodeError as e:
        print("Failed to parse JSON from model response:", e)
        print(content)


if __name__ == '__main__':

    # load the sample JSON file as string 
    samples = ""
    generate_and_save_problems()

