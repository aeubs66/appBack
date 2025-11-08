"""
Check the format of stored embeddings.
"""
from sqlalchemy import text
from app.db import SessionLocal

db = SessionLocal()

try:
    # Get a sample chunk with its embedding
    query = text("""
        SELECT 
            id,
            page_from,
            page_to,
            LEFT(content, 80) as content_preview,
            embedding
        FROM pdf_chunk
        LIMIT 1
    """)
    
    result = db.execute(query).fetchone()
    
    if result:
        print("\n=== Sample Chunk ===")
        print(f"ID: {result.id}")
        print(f"Pages: {result.page_from}-{result.page_to}")
        print(f"Content: {result.content_preview}...")
        print(f"\nEmbedding type: {type(result.embedding)}")
        print(f"Embedding value (first 100 chars): {str(result.embedding)[:100]}...")
        
        # Try to check if it's a list/array
        if hasattr(result.embedding, '__len__'):
            print(f"Embedding length: {len(result.embedding)}")
            if len(result.embedding) > 0:
                print(f"First value: {result.embedding[0]} (type: {type(result.embedding[0])})")
                print(f"Last value: {result.embedding[-1]} (type: {type(result.embedding[-1])})")
        else:
            print("Embedding is NOT iterable!")
            
    else:
        print("No chunks found!")
        
finally:
    db.close()

