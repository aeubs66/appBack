"""
PDF processing service: extraction, chunking, and embedding.
"""

import io
import re
from typing import List, Tuple
import fitz  # PyMuPDF
from app.services.openai_service import get_embedding, get_embeddings_batch


def extract_text_from_pdf(pdf_bytes: bytes) -> List[Tuple[str, int]]:
    """
    Extract text from PDF with page numbers.
    
    Returns: List of (text, page_number) tuples
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = []
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text()
        pages.append((text, page_num + 1))  # 1-indexed pages
    
    doc.close()
    return pages


def estimate_tokens(text: str) -> int:
    """
    Rough token estimation: ~4 characters per token.
    More accurate would use tiktoken, but this is simpler.
    """
    return len(text) // 4


def chunk_text(
    pages: List[Tuple[str, int]],
    target_tokens: int = 1000,
    overlap_tokens: int = 120
) -> List[Tuple[str, int, int]]:
    """
    Chunk text into target token size with overlap.
    
    Args:
        pages: List of (text, page_number) tuples
        target_tokens: Target tokens per chunk (default 1000)
        overlap_tokens: Overlap tokens between chunks (default 120)
    
    Returns:
        List of (chunk_text, page_from, page_to) tuples
    """
    chunks = []
    current_chunk = []
    current_tokens = 0
    current_pages = set()
    
    for text, page_num in pages:
        text_tokens = estimate_tokens(text)
        
        # If adding this page would exceed target, finalize current chunk
        if current_tokens + text_tokens > target_tokens and current_chunk:
            chunk_text = "\n\n".join(current_chunk)
            chunks.append((
                chunk_text,
                min(current_pages),
                max(current_pages)
            ))
            
            # Start new chunk with overlap
            if overlap_tokens > 0:
                # Keep last portion of previous chunk for overlap
                overlap_text = current_chunk[-1] if current_chunk else ""
                overlap_text_tokens = estimate_tokens(overlap_text)
                
                # If overlap is too large, take last portion
                if overlap_text_tokens > overlap_tokens:
                    # Take roughly last overlap_tokens worth
                    chars_to_keep = overlap_tokens * 4
                    overlap_text = overlap_text[-chars_to_keep:]
                
                current_chunk = [overlap_text] if overlap_text else []
                current_tokens = estimate_tokens(overlap_text)
                current_pages = {max(current_pages)} if current_pages else set()
            else:
                current_chunk = []
                current_tokens = 0
                current_pages = set()
        
        # Add current page to chunk
        current_chunk.append(text)
        current_tokens += text_tokens
        current_pages.add(page_num)
    
    # Add final chunk if any remaining
    if current_chunk:
        chunk_text = "\n\n".join(current_chunk)
        chunks.append((
            chunk_text,
            min(current_pages),
            max(current_pages)
        ))
    
    return chunks


def process_pdf_chunks_sync(
    pdf_bytes: bytes,
    doc_id: str = None  # Optional, for logging
) -> Tuple[int, List[Tuple[str, int, int, List[float]]]]:
    """
    Synchronous wrapper for process_pdf_chunks (for Celery tasks).
    
    Returns:
        Tuple of (num_pages, chunks_with_embeddings)
        chunks_with_embeddings: List of (text, page_from, page_to, embedding)
    """
    import asyncio
    
    # Run async function in sync context
    return asyncio.run(process_pdf_chunks(pdf_bytes, doc_id))


async def process_pdf_chunks(
    pdf_bytes: bytes,
    doc_id: str = None  # Optional, for logging
) -> Tuple[int, List[Tuple[str, int, int, List[float]]]]:
    """
    Process PDF: extract, chunk, and generate embeddings.
    
    Returns:
        Tuple of (num_pages, chunks_with_embeddings)
        chunks_with_embeddings: List of (text, page_from, page_to, embedding)
    """
    # Extract text with page numbers
    pages = extract_text_from_pdf(pdf_bytes)
    num_pages = len(pages)
    
    # Chunk text
    chunks = chunk_text(pages, target_tokens=1000, overlap_tokens=120)
    
    # Generate embeddings in batch
    chunk_texts = [chunk[0] for chunk in chunks]
    embeddings = []
    
    # Batch process embeddings (OpenAI allows up to 2048 items per batch)
    batch_size = 100
    for i in range(0, len(chunk_texts), batch_size):
        batch = chunk_texts[i:i + batch_size]
        batch_embeddings = await get_embeddings_batch(batch)
        embeddings.extend(batch_embeddings)
    
    # Combine chunks with embeddings
    chunks_with_embeddings = [
        (chunk[0], chunk[1], chunk[2], embedding)
        for chunk, embedding in zip(chunks, embeddings)
    ]
    
    return num_pages, chunks_with_embeddings


