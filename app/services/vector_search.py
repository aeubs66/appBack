"""
Vector similarity search service.
"""

from typing import List, Tuple
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.models import PDFChunk


async def search_similar_chunks(
    db: Session,
    doc_id: str,
    query_embedding: List[float],
    k: int = 5,
    similarity_threshold: float = 0.70
) -> List[Tuple[PDFChunk, float]]:
    """
    Search for similar chunks using cosine similarity.
    
    Args:
        db: Database session
        doc_id: Document UUID
        query_embedding: Query embedding vector (1536 dimensions)
        k: Number of results to return
        similarity_threshold: Minimum similarity score (0-1)
    
    Returns:
        List of (chunk, similarity_score) tuples, sorted by similarity desc
    """
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # Convert embedding to pgvector format string
    embedding_str = "[" + ",".join(map(str, query_embedding)) + "]"
    
    logging.info(f"[VECTOR SEARCH] doc_id={doc_id}, threshold={similarity_threshold}, k={k}")
    logging.info(f"[VECTOR SEARCH] Embedding length: {len(query_embedding)}")
    logging.info(f"[VECTOR SEARCH] Embedding string length: {len(embedding_str)}")
    
    # First, check how many chunks exist for this document
    count_query = text("SELECT COUNT(*) FROM pdf_chunk WHERE doc_id = CAST(:doc_id AS uuid)")
    count_result = db.execute(count_query, {"doc_id": doc_id}).scalar()
    logging.info(f"[VECTOR SEARCH] Total chunks for document: {count_result}")
    
    # Use cosine similarity (1 - cosine_distance)
    # pgvector's <=> operator returns cosine distance, so we use 1 - distance for similarity
    # Note: We use CAST() instead of :: for type conversion to avoid SQLAlchemy parameter conflicts
    query = text("""
        SELECT 
            id,
            doc_id,
            content,
            page_from,
            page_to,
            1 - (embedding <=> CAST(:embedding AS vector)) as similarity
        FROM pdf_chunk
        WHERE doc_id = CAST(:doc_id AS uuid)
            AND 1 - (embedding <=> CAST(:embedding AS vector)) >= :threshold
        ORDER BY embedding <=> CAST(:embedding AS vector)
        LIMIT :k
    """)

    fallback_query = text("""
        SELECT 
            id,
            doc_id,
            content,
            page_from,
            page_to,
            1 - (embedding <=> CAST(:embedding AS vector)) as similarity
        FROM pdf_chunk
        WHERE doc_id = CAST(:doc_id AS uuid)
        ORDER BY embedding <=> CAST(:embedding AS vector)
        LIMIT :fallback_k
    """)
    
    try:
        result = db.execute(
            query,
            {
                "embedding": embedding_str,
                "doc_id": doc_id,
                "threshold": similarity_threshold,
                "k": k
            }
        )
        
        chunks_with_scores = []
        for row in result:
            # Create chunk object from row data
            chunk = PDFChunk(
                id=row.id,
                doc_id=row.doc_id,
                content=row.content,
                page_from=row.page_from,
                page_to=row.page_to
            )
            similarity = float(row.similarity)
            chunks_with_scores.append((chunk, similarity))
            logging.info(f"[VECTOR SEARCH] Found chunk with similarity: {similarity:.3f}")
        
        logging.info(f"[VECTOR SEARCH] Total chunks returned: {len(chunks_with_scores)}")
        
        # Fallback: if no chunks pass the threshold, return the top results without threshold
        if not chunks_with_scores:
            logging.info("[VECTOR SEARCH] No chunks passed threshold. Running fallback query without threshold.")
            fallback_result = db.execute(
                fallback_query,
                {
                    "embedding": embedding_str,
                    "doc_id": doc_id,
                    "fallback_k": min(k, 3)
                }
            )
            for row in fallback_result:
                chunk = PDFChunk(
                    id=row.id,
                    doc_id=row.doc_id,
                    content=row.content,
                    page_from=row.page_from,
                    page_to=row.page_to
                )
                similarity = float(row.similarity)
                chunks_with_scores.append((chunk, similarity))
                logging.info(f"[VECTOR SEARCH][FALLBACK] Chunk similarity: {similarity:.3f}")
            logging.info(f"[VECTOR SEARCH] Fallback returned {len(chunks_with_scores)} chunks")
        
        return chunks_with_scores
        
    except Exception as e:
        logging.error(f"[VECTOR SEARCH] Error: {e}")
        raise

