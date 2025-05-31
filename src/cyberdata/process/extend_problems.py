# cyberdata/scripts/extend_problem.py

import json
import os
import sys
import re
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv

# Add parent directory to path for imports
CURRENT_DIR = Path(__file__).parent
PROJECT_ROOT = CURRENT_DIR.parent.parent.parent
sys.path.append(str(CURRENT_DIR.parent))  # Add cyberdata package to path

# Import process_llm_request from utility module
from cyberdata.utils.llm_invoke import process_llm_request
from cyberdata.utils.logger_config import setup_logger

# Set up logger
logger = setup_logger("cyberdata.scripts.extend_problem")

# Load environment variables
load_dotenv()

# Constants and paths
MODEL_NAME = "gpt-4.1-mini"
PROBLEMS_PATH = CURRENT_DIR.parent / 'config' / 'problems.json'
EVALUATION_REPORT_PATH = CURRENT_DIR.parent / 'config' / 'problems_evaluation_report.json'
UPDATED_PROBLEMS_PATH = CURRENT_DIR.parent / 'config' / 'problems_updated.json'

logger.info(f"Using model: {MODEL_NAME}")
logger.info(f"Problems path: {PROBLEMS_PATH}")
logger.info(f"Evaluation report path: {EVALUATION_REPORT_PATH}")
logger.info(f"Updated problems path: {UPDATED_PROBLEMS_PATH}")


def load_existing_problems():
    """Load existing problems from problems.json"""
    if not PROBLEMS_PATH.exists():
        logger.error(f"Problems file not found: {PROBLEMS_PATH}")
        raise FileNotFoundError(f"Problems file not found: {PROBLEMS_PATH}")
    
    try:
        with PROBLEMS_PATH.open('r', encoding='utf-8') as f:
            data = json.load(f)
        
        problems = data.get('problems', [])
        logger.info(f"Loaded {len(problems)} problems from {PROBLEMS_PATH}")
        return problems
    except Exception as e:
        logger.error(f"Error loading problems: {str(e)}", exc_info=True)
        raise


def create_evaluation_system_prompt():
    """Create system prompt for evaluation"""
    logger.debug("Creating evaluation system prompt")
    return """
You are an expert cybersecurity analyst and taxonomy specialist with deep knowledge of threat intelligence, 
incident response, and cybersecurity frameworks including MITRE ATT&CK, NIST Cybersecurity Framework, 
VERIS schema, and emerging threat landscapes.

Your task is to evaluate and improve a structured JSON list of cybersecurity problems to ensure it:
1. Uses effective categorization and taxonomy
2. Covers current and emerging threats (2023-2025)
3. Follows industry best practices for threat classification
4. Provides actionable intelligence for security teams

Provide detailed, technical analysis with specific recommendations for improvement.
"""


def create_evaluation_user_prompt(problems_json):
    """Create user prompt for evaluation with the problems JSON"""
    logger.debug("Creating evaluation user prompt")
    return f"""
I have a structured JSON list of cybersecurity problems. Each entry includes:

- `area`: High-level category of the threat (e.g., Enterprise, Cloud, EDTC)
- `nature`: Specific subtype (e.g., phishing, misconfigured_storage)
- `description`: Explanation of the threat
- `risk_reduction`: Recommended mitigations

Please evaluate the list along the following dimensions:

1. **Categorization Structure**:
   - Is the use of `area` and `nature` fields effective and scalable?
   - Would a hierarchical taxonomy (e.g., `area > category > variant`) improve clarity?
   - Should any standard taxonomy (MITRE ATT&CK, NIST, VERIS, etc.) be used for alignment?

2. **Opportunities for Merging or Reclassification**:
   - Identify any entries that could be logically merged under a broader umbrella category (e.g., consolidate phishing subtypes).
   - Suggest a more unified or normalized structure if applicable.

3. **Coverage of Emerging and Important Threats**:
   - Identify if the list is missing any **recent or rising cyberattacks** (2023–2025).
   - Recommend at least **5 newly relevant or high-impact threats**, including their categories and brief descriptions.
   - Include areas such as AI-generated attacks, supply chain risks, cloud misconfigurations, or adversarial ML attacks.

4. **Optional Enhancement Suggestions**:
   - Suggest adding new fields (e.g., `attack_vector`, `asset_targeted`, `kill_chain_phase`, `impact_level`) to make the dataset more useful for incident classification or training datasets.

Here is the JSON list for evaluation:

{problems_json}

Please provide your evaluation as a structured JSON response with the following format:
{{
  "evaluation_summary": "Brief overview of findings",
  "categorization_analysis": {{
    "current_structure_assessment": "Analysis of current area/nature structure",
    "taxonomy_recommendations": "Suggestions for taxonomy improvements",
    "standard_alignment": "Recommendations for standard framework alignment"
  }},
  "merging_recommendations": [
    {{
      "suggestion": "Description of merging opportunity",
      "affected_items": ["list of items to merge"],
      "proposed_structure": "How to restructure"
    }}
  ],
  "missing_threats": [
    {{
      "area": "Proposed area",
      "nature": "Proposed nature",
      "description": "Detailed description",
      "risk_reduction": ["list of mitigation strategies"],
      "justification": "Why this threat is important and emerging"
    }}
  ],
  "enhancement_suggestions": {{
    "new_fields": [
      {{
        "field_name": "proposed field name",
        "description": "what this field would contain",
        "example_values": ["example1", "example2"]
      }}
    ],
    "structural_improvements": "Other structural suggestions"
  }}
}}

Return only valid JSON with your complete analysis.
"""


def extract_json_from_response(response_content):
    """Extract JSON from LLM response that might contain markdown or other formatting"""
    logger.debug("Extracting JSON from evaluation response")
    
    # Try direct JSON parsing first
    try:
        return json.loads(response_content)
    except json.JSONDecodeError:
        logger.debug("Direct JSON parsing failed, trying alternative methods")
        pass
    
    # Remove markdown code blocks if present
    if '```' in response_content:
        logger.debug("Response contains code blocks, cleaning up")
        pattern = r'```(?:json)?\s*([\s\S]*?)```'
        matches = re.findall(pattern, response_content)
        if matches:
            response_content = matches[0]
            logger.debug("Extracted content from code block")
    
    # Try parsing cleaned content
    try:
        return json.loads(response_content)
    except json.JSONDecodeError as e:
        logger.warning(f"JSON parsing failed: {str(e)}")
        
        # Try to extract JSON object by finding braces
        try:
            start_idx = response_content.find('{')
            if start_idx != -1:
                # Find the matching closing brace
                brace_count = 0
                for i in range(start_idx, len(response_content)):
                    if response_content[i] == '{':
                        brace_count += 1
                    elif response_content[i] == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            json_str = response_content[start_idx:i+1]
                            logger.debug("Extracted JSON by brace matching")
                            return json.loads(json_str)
        except Exception as e:
            logger.warning(f"JSON extraction by brace matching failed: {str(e)}")
            pass
        
        # If all methods fail, raise an exception
        logger.error(f"Could not extract valid JSON from response")
        raise ValueError("Could not extract valid JSON from evaluation response")


def evaluate_problems(problems):
    """Use LLM to evaluate the existing problems"""
    logger.info("Starting LLM evaluation of existing problems")
    
    # Convert problems to JSON string for the prompt
    problems_json = json.dumps({"problems": problems}, indent=2)
    
    # Create prompts
    system_prompt = create_evaluation_system_prompt()
    user_prompt = create_evaluation_user_prompt(problems_json)
    
    # Call LLM for evaluation
    logger.info("Calling LLM for problems evaluation")
    response_content = process_llm_request(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model_name=MODEL_NAME,
        temperature=0.3  # Slightly higher for more creative analysis
    )
    
    logger.debug(f"Evaluation response received, length: {len(response_content)} characters")
    
    # Extract and return JSON
    try:
        evaluation_result = extract_json_from_response(response_content)
        logger.info("Successfully extracted evaluation JSON")
        return evaluation_result
    except Exception as e:
        logger.error(f"Error extracting evaluation JSON: {str(e)}")
        # Return a basic structure if parsing fails
        return {
            "evaluation_summary": "Error parsing LLM response",
            "raw_response": response_content,
            "error": str(e)
        }


def save_evaluation_report(evaluation_result):
    """Save the evaluation report to a JSON file"""
    logger.info(f"Saving evaluation report to {EVALUATION_REPORT_PATH}")
    
    # Add metadata to the report
    report_data = {
        "evaluation_metadata": {
            "timestamp": datetime.now().isoformat(),
            "model_used": MODEL_NAME,
            "evaluation_version": "1.0"
        },
        "evaluation_result": evaluation_result
    }
    
    try:
        # Ensure config directory exists
        EVALUATION_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        # Save the report
        with EVALUATION_REPORT_PATH.open('w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Evaluation report saved successfully to {EVALUATION_REPORT_PATH}")
    except Exception as e:
        logger.error(f"Error saving evaluation report: {str(e)}", exc_info=True)
        raise


def create_update_system_prompt():
    """Create system prompt for updating problems based on evaluation"""
    logger.debug("Creating update system prompt")
    return """
You are an expert cybersecurity analyst tasked with updating and extending a cybersecurity problems dataset 
based on evaluation findings. You must:

1. Incorporate recommended new threats and attack vectors
2. Apply suggested structural improvements
3. Merge or reclassify problems where recommended
4. Ensure all entries follow consistent formatting and taxonomy
5. Maintain backwards compatibility while improving the dataset

Generate a comprehensive, updated problems list that addresses the evaluation findings while 
preserving existing valuable content.
"""


def create_update_user_prompt(original_problems, evaluation_result):
    """Create user prompt for updating problems"""
    logger.debug("Creating update user prompt")
    
    original_json = json.dumps({"problems": original_problems}, indent=2)
    evaluation_json = json.dumps(evaluation_result, indent=2)
    
    return f"""
Based on the evaluation findings, please update and extend the cybersecurity problems dataset.

Original Problems Dataset:
{original_json}

Evaluation Results and Recommendations:
{evaluation_json}

Please generate an updated problems dataset that:

1. **Incorporates New Threats**: Add the recommended missing threats from the evaluation
2. **Applies Structural Improvements**: Implement suggested categorization and field enhancements
3. **Merges/Reclassifies**: Apply any recommended merging or reclassification suggestions
4. **Maintains Consistency**: Ensure all entries follow the same structure and quality standards
5. **Preserves Existing Content**: Keep valuable existing problems while improving their classification

For any new threats added, ensure they include:
- Clear, technical descriptions
- Realistic risk reduction strategies
- Proper categorization using the improved taxonomy

Return the updated dataset as a JSON object with this exact structure:
{{
  "problems": [
    {{
      "area": "area_name",
      "nature": "specific_nature",
      "description": "detailed technical description",
      "risk_reduction": ["strategy1", "strategy2", "strategy3"]
    }}
  ]
}}

Return only valid JSON with the complete updated problems list.
"""


def update_problems_based_on_evaluation(original_problems, evaluation_result):
    """Use LLM to update problems based on evaluation findings"""
    logger.info("Starting problems update based on evaluation")
    
    # Create prompts for update
    system_prompt = create_update_system_prompt()
    user_prompt = create_update_user_prompt(original_problems, evaluation_result)
    
    # Call LLM for update
    logger.info("Calling LLM for problems update")
    response_content = process_llm_request(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model_name=MODEL_NAME,
        temperature=0.5  # Balanced creativity for good updates
    )
    
    logger.debug(f"Update response received, length: {len(response_content)} characters")
    
    # Extract and return updated problems
    try:
        updated_data = extract_json_from_response(response_content)
        updated_problems = updated_data.get('problems', [])
        logger.info(f"Successfully extracted {len(updated_problems)} updated problems")
        return updated_problems
    except Exception as e:
        logger.error(f"Error extracting updated problems JSON: {str(e)}")
        logger.warning("Returning original problems due to update failure")
        return original_problems


def save_updated_problems(updated_problems):
    """Save updated problems to a new JSON file"""
    logger.info(f"Saving updated problems to {UPDATED_PROBLEMS_PATH}")
    
    # Create the updated problems data structure (without metadata)
    updated_data = {
        "problems": updated_problems
    }
    
    try:
        # Ensure config directory exists
        UPDATED_PROBLEMS_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        # Save the updated problems
        with UPDATED_PROBLEMS_PATH.open('w', encoding='utf-8') as f:
            json.dump(updated_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Updated problems saved successfully to {UPDATED_PROBLEMS_PATH}")
        logger.info(f"Total problems in updated dataset: {len(updated_problems)}")
        
        # Log summary of areas
        areas = set(problem.get('area', 'Unknown') for problem in updated_problems)
        logger.info(f"Areas covered: {', '.join(sorted(areas))}")
        
    except Exception as e:
        logger.error(f"Error saving updated problems: {str(e)}", exc_info=True)
        raise


def generate_summary_report(original_problems, updated_problems, evaluation_result):
    """Generate a summary of changes made"""
    logger.info("Generating summary report")
    
    original_count = len(original_problems)
    updated_count = len(updated_problems)
    
    original_areas = set(p.get('area', 'Unknown') for p in original_problems)
    updated_areas = set(p.get('area', 'Unknown') for p in updated_problems)
    
    original_natures = set(p.get('nature', 'Unknown') for p in original_problems)
    updated_natures = set(p.get('nature', 'Unknown') for p in updated_problems)
    
    summary = {
        "summary": {
            "original_problems_count": original_count,
            "updated_problems_count": updated_count,
            "net_change": updated_count - original_count,
            "original_areas": sorted(list(original_areas)),
            "updated_areas": sorted(list(updated_areas)),
            "new_areas": sorted(list(updated_areas - original_areas)),
            "original_natures_count": len(original_natures),
            "updated_natures_count": len(updated_natures),
            "new_natures": sorted(list(updated_natures - original_natures))
        },
        "evaluation_highlights": {
            "evaluation_summary": evaluation_result.get("evaluation_summary", "No summary available"),
            "missing_threats_added": len(evaluation_result.get("missing_threats", [])),
            "merging_recommendations_count": len(evaluation_result.get("merging_recommendations", []))
        }
    }
    
    logger.info(f"Summary: {original_count} -> {updated_count} problems ({updated_count - original_count:+d})")
    logger.info(f"Areas: {len(original_areas)} -> {len(updated_areas)} ({len(updated_areas) - len(original_areas):+d})")
    logger.info(f"New areas added: {summary['summary']['new_areas']}")
    logger.info(f"New threat types: {len(summary['summary']['new_natures'])}")
    
    return summary


def main():
    """Main function to evaluate and extend problems"""
    logger.info("Starting problems evaluation and extension process")
    
    try:
        # Step 1: Load existing problems
        logger.info("Step 1: Loading existing problems")
        original_problems = load_existing_problems()
        
        # Step 2: Evaluate problems using LLM
        logger.info("Step 2: Evaluating problems with LLM")
        evaluation_result = evaluate_problems(original_problems)
        
        # Step 3: Save evaluation report
        logger.info("Step 3: Saving evaluation report")
        save_evaluation_report(evaluation_result)
        
        # Step 4: Update problems based on evaluation
        logger.info("Step 4: Updating problems based on evaluation")
        updated_problems = update_problems_based_on_evaluation(original_problems, evaluation_result)
        
        # Step 5: Save updated problems
        logger.info("Step 5: Saving updated problems")
        save_updated_problems(updated_problems)
        
        # Step 6: Generate and log summary
        logger.info("Step 6: Generating summary report")
        summary = generate_summary_report(original_problems, updated_problems, evaluation_result)
        
        # Print summary to console
        print("\n" + "="*60)
        print("PROBLEMS EVALUATION AND EXTENSION COMPLETED")
        print("="*60)
        print(f"Original problems: {summary['summary']['original_problems_count']}")
        print(f"Updated problems:  {summary['summary']['updated_problems_count']}")
        print(f"Net change:        {summary['summary']['net_change']:+d}")
        print(f"New areas:         {', '.join(summary['summary']['new_areas']) if summary['summary']['new_areas'] else 'None'}")
        print(f"New threat types:  {len(summary['summary']['new_natures'])}")
        print("\nFiles generated:")
        print(f"- Evaluation report: {EVALUATION_REPORT_PATH}")
        print(f"- Updated problems:  {UPDATED_PROBLEMS_PATH}")
        print("="*60)
        
        logger.info("Problems evaluation and extension completed successfully")
        
    except Exception as e:
        logger.error(f"Error in main process: {str(e)}", exc_info=True)
        print(f"\nError: {str(e)}")
        print("Check the logs for detailed error information.")
        raise


if __name__ == '__main__':
    main()