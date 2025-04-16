from langchain.prompts import PromptTemplate

# System prompt: Contextualizes the LLM’s role and the cybersecurity domains
system_prompt_text = '''
You are an expert cybersecurity analyst and synthetic data engineer. Your mission is to help catalog and generate synthetic datasets for critical cybersecurity challenges across diverse operational environments.

Operational areas:
- **Enterprise**
- **Cloud**
- **EDTC** (Education, Data, Technology, and Communications)

For each problem you describe, include:
1. **Nature**: The specific category or type (e.g., phishing, data exfiltration, misconfiguration).
2. **Description**: A concise but comprehensive overview of the issue.
3. **Risk Reduction**: Concrete strategies or controls to mitigate the threat.
'''  

# User prompt: Requests structured JSON output detailing each problem
user_prompt_text = '''
Please generate a JSON object with a single key "problems", whose value is an array of problem entries. Each entry must include:

- "area": One of ["Enterprise", "Cloud", "EDTC"]
- "nature": A concise label for the problem category (e.g., "phishing", "misconfiguration").
- "description": A detailed explanation of the problem scenario.
- "risk_reduction": A list of recommended mitigation measures.

Include at least three problems per area. Return valid JSON only—no additional text.  
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


if __name__ == "__main__":
    print("=== SYSTEM PROMPT ===")
    print(get_system_prompt())
    print("\n=== USER PROMPT ===")
    print(get_user_prompt())
