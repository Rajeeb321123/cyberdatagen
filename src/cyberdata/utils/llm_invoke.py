# cyberdata/utils/llm_invoke.py

import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from cyberdata.utils.logger_config import setup_logger

# Set up logger
logger = setup_logger("cyberdata.utils.llm_invoke")

load_dotenv()
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# Global configuration variables
MODEL_NAME = "gpt-4.1-mini"
MODEL_TOKEN_SIZE = 16384
LOG_LEVEL = logging.INFO

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)  # Make sure to set this environment variable


def process_llm_request(
    system_prompt,
    user_prompt,
    model_name=MODEL_NAME,
    max_tokens=MODEL_TOKEN_SIZE,
    temperature=0.1,
):
    """
    Process a request to the LLM.
    
    Args:
        system_prompt (str): The system prompt for the LLM
        user_prompt (str): The user prompt for the LLM
        model_name (str): The model to use (default: gpt-4.1-mini)
        max_tokens (int): Maximum tokens in the response (default: 16384)
        temperature (float): Temperature for the response (default: 0.1)
        
    Returns:
        str: The response from the LLM
    """
    try:
        # Log the prompts for debugging
        logger.info(f"Calling {model_name} with system prompt: {system_prompt[:100]}...")
        logger.debug(f"Full system prompt: {system_prompt}")
        logger.info(f"User prompt: {user_prompt[:100]}...")
        logger.debug(f"Full user prompt: {user_prompt}")

        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )

        result = response.choices[0].message.content
        logger.info(f"LLM response received, length: {len(result)} characters")
        logger.debug(f"LLM response: {result[:500]}...")

        return result
    except Exception as e:
        error_msg = f"Request failed: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return f"[Error: {str(e)}]"