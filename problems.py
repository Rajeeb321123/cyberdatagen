# problems.py

from langchain.prompts import PromptTemplate

# System prompt: Provides context about the project and cybersecurity areas.
system_prompt_text = """
You are an expert cybersecurity analyst and synthetic data engineer. Your task is to generate synthesis datasets for various cybersecurity problems. 
The cybersecurity areas you should consider include:
- **Enterprise**
- **Cloud**
- **EDTC** (Education, Data, Technology, and Communications)

When describing the problems, include:
- The nature of the problem (e.g., phishing, data exfiltration, misconfiguration, etc.).
- A detailed description of the problem.
- Possible ways to reduce its risk.
"""

# Updated user prompt: Requests a JSON output with a detailed list of problems, including area, nature, description, and risk reduction measures.
user_prompt_text = """
Generate a JSON output that includes an array of cybersecurity problems. For each problem, provide the following keys:

- **area**: The operational area (e.g., Enterprise, Cloud, EDTC)
- **nature**: The type or nature of the cybersecurity problem (e.g., phishing, data exfiltration, misconfiguration).
- **description**: A detailed description of the problem.
- **risk_reduction**: Possible measures to reduce the risk of this problem.

Ensure the JSON is properly formatted.
"""

# Create LangChain prompt templates
system_prompt = PromptTemplate(
    input_variables=[],
    template=system_prompt_text
)

user_prompt = PromptTemplate(
    input_variables=[],
    template=user_prompt_text
)

def get_system_prompt() -> str:
    """Returns the formatted system prompt."""
    return system_prompt.format()

def get_user_prompt() -> str:
    """Returns the formatted user prompt."""
    return user_prompt.format()

if __name__ == "__main__":
    print("=== System Prompt ===")
    print(get_system_prompt())
    print("\n=== User Prompt ===")
    print(get_user_prompt())
