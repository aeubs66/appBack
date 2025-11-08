"""
OpenAI service for embeddings and chat completions.
"""

import os
from typing import List
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize client lazily to ensure env vars are loaded
_client = None

def get_client() -> OpenAI:
    """Get OpenAI client, initializing if needed."""
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY not set. Please add it to your .env file. "
                "Get it from: https://platform.openai.com/api-keys"
            )
        _client = OpenAI(api_key=api_key)
    return _client


async def get_embedding(text: str) -> List[float]:
    """Get embedding for text using text-embedding-3-small."""
    client = get_client()
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text,
    )
    return response.data[0].embedding


async def get_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """Get embeddings for multiple texts in a single API call."""
    client = get_client()
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=texts,
    )
    return [item.embedding for item in response.data]


async def get_chat_completion(messages: list[dict], model: str = "gpt-4o-mini") -> str:
    """Get chat completion from OpenAI."""
    client = get_client()
    response = client.chat.completions.create(
        model=model,
        messages=messages,
    )
    return response.choices[0].message.content

