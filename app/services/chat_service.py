"""
Chat service for RAG-based question answering.
"""

import re
from typing import List, Tuple, Dict, Any
from app.services.openai_service import get_embedding, get_chat_completion


def build_rag_prompt(question: str, context_chunks: List[Tuple[str, int, int, float]]) -> List[Dict[str, str]]:
    """
    Build a strict RAG prompt with context and citation requirements.
    
    Args:
        question: User's question
        context_chunks: List of (content, page_from, page_to, similarity) tuples
    
    Returns:
        Messages list for OpenAI chat completion
    """
    # Build context from chunks with page numbers
    context_parts = []
    for i, (content, page_from, page_to, similarity) in enumerate(context_chunks):
        page_range = f"[p{page_from}]" if page_from == page_to else f"[p{page_from}–{page_to}]"
        context_parts.append(f"Context {i+1} {page_range}:\n{content}")
    
    context_text = "\n\n".join(context_parts)
    
    system_message = """You are a helpful assistant that answers questions based ONLY on the provided document context.

STRICT RULES:
1. Answer ONLY using information from the context provided
2. If the answer is not in the context, say "I can't find that information in the document"
3. ALWAYS cite pages using the format [pX] for single pages or [pX–Y] for page ranges
4. Include citations immediately after the relevant information
5. Do not make up information or use external knowledge
6. Be concise and accurate

Example good answer: "The revenue was $2.5M in Q4 [p12]. The growth rate was 15% year-over-year [p13–14]."
Example bad answer: "Based on industry trends..." (this uses external knowledge)"""
    
    user_message = f"""Context from the document:

{context_text}

Question: {question}

Answer the question based ONLY on the context above. Include page citations in your answer."""
    
    return [
        {"role": "system", "content": system_message},
        {"role": "user", "content": user_message}
    ]


def extract_citations(answer: str) -> List[str]:
    """
    Extract page citations from answer text.
    
    Returns: List of citation strings like "[p3]" or "[p3-4]"
    """
    # Match patterns like [p3], [p12-15], [p3–4] (with en-dash)
    pattern = r'\[p\d+(?:[–-]\d+)?\]'
    citations = re.findall(pattern, answer)
    return citations


async def answer_question(
    question: str,
    context_chunks: List[Tuple[str, int, int, float]],
    model: str = "gpt-4o-mini"
) -> Tuple[str, List[str]]:
    """
    Generate an answer to a question using RAG.
    
    Args:
        question: User's question
        context_chunks: List of (content, page_from, page_to, similarity) tuples
        model: OpenAI model to use
    
    Returns:
        Tuple of (answer, citations)
    """
    # Build prompt with context
    messages = build_rag_prompt(question, context_chunks)
    
    # Get answer from OpenAI
    answer = await get_chat_completion(messages, model=model)
    
    # Extract citations
    citations = extract_citations(answer)
    
    return answer, citations

