"""
Test script to check similarity scores without threshold.
"""
from sqlalchemy import text
from app.db import SessionLocal
from app.services.openai_service import get_embedding
import asyncio

async def test_similarity():
    db = SessionLocal()
    
    try:
        # Get a test question embedding
        question = "What is this about?"
        print(f"\nTest question: {question}")
        embedding = await get_embedding(question)
        print(f"Embedding length: {len(embedding)}")
        
        # Format for pgvector
        embedding_str = "[" + ",".join(map(str, embedding)) + "]"
        print(f"Embedding string length: {len(embedding_str)}")
        
        # Get doc_id
        doc_query = text("SELECT id FROM pdf_document ORDER BY created_at DESC LIMIT 1")
        doc_id = db.execute(doc_query).scalar()
        print(f"\nDocument ID: {doc_id}")
        
        # Count chunks
        count_query = text("SELECT COUNT(*) FROM pdf_chunk WHERE doc_id = CAST(:doc_id AS uuid)")
        count = db.execute(count_query, {"doc_id": str(doc_id)}).scalar()
        print(f"Total chunks: {count}")
        
        # Query WITHOUT threshold to see all similarity scores
        query = text("""
            SELECT 
                page_from,
                page_to,
                1 - (embedding <=> CAST(:embedding AS vector)) as similarity,
                LEFT(content, 100) as content_preview
            FROM pdf_chunk
            WHERE doc_id = CAST(:doc_id AS uuid)
            ORDER BY embedding <=> CAST(:embedding AS vector)
            LIMIT 10
        """)
        
        print("\nTop 10 chunks by similarity (no threshold):")
        print("-" * 80)
        
        result = db.execute(query, {
            "embedding": embedding_str,
            "doc_id": str(doc_id)
        })
        
        for row in result:
            print(f"Pages {row.page_from}-{row.page_to}: similarity={row.similarity:.6f}")
            print(f"  Content: {row.content_preview}...")
            print()
        
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test_similarity())

