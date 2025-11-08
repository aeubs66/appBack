"""
Check the latest uploaded PDF's embedding format.
"""
from sqlalchemy import text
from app.db import SessionLocal

db = SessionLocal()

try:
    # Get the most recent document
    doc_query = text("""
        SELECT id, title, status, num_pages
        FROM pdf_document
        ORDER BY created_at DESC
        LIMIT 3
    """)
    
    print("\n=== Recent Documents ===")
    for doc in db.execute(doc_query):
        print(f"- {doc.title} (status: {doc.status}, pages: {doc.num_pages})")
        print(f"  ID: {doc.id}")
        
        # Check chunk count
        count_query = text("SELECT COUNT(*) FROM pdf_chunk WHERE doc_id = CAST(:doc_id AS uuid)")
        chunk_count = db.execute(count_query, {"doc_id": str(doc.id)}).scalar()
        print(f"  Chunks: {chunk_count}")
        
        if chunk_count > 0:
            # Check embedding format
            emb_query = text("""
                SELECT 
                    embedding,
                    LEFT(content, 60) as preview
                FROM pdf_chunk
                WHERE doc_id = CAST(:doc_id AS uuid)
                LIMIT 1
            """)
            result = db.execute(emb_query, {"doc_id": str(doc.id)}).fetchone()
            
            print(f"  Embedding type: {type(result.embedding)}")
            
            if isinstance(result.embedding, str):
                print(f"  ❌ STILL A STRING! (length: {len(result.embedding)})")
                print(f"     First 80 chars: {result.embedding[:80]}")
            else:
                print(f"  ✅ Proper type! Length: {len(result.embedding) if hasattr(result.embedding, '__len__') else 'unknown'}")
                if hasattr(result.embedding, '__len__'):
                    print(f"     First value: {result.embedding[0]}")
        print()
        
finally:
    db.close()

