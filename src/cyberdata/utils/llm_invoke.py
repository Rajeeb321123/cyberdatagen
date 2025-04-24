# nlp2opt/utils/llm_invoke.py

import os
import logging
from dotenv import load_dotenv
from openai import OpenAI
from nlp2opt import logger


load_dotenv()
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# Global configuration variables
MODEL_NAME = "gpt-4o-mini"
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
    try:

        logger.info(f"The system prompt of the call: {system_prompt}")
        logger.info(f"The user prompt of the call: {user_prompt}")

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

        logger.info(f"The LLM call result: {result}")

        return result
    except Exception as e:
        error_msg = f"Request failed: {str(e)}"
        print(error_msg)
        logger.error(error_msg)
        return f"[Error: {str(e)}]"
