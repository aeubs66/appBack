"""
Debug script to check if chunks were saved to database.
"""
from sqlalchemy import text
from app.db import SessionLocal
from app.models import PDFChunk, PDFDocument

db = SessionLocal()

try:
    # Count total chunks
    chunk_count = db.query(PDFChunk).count()
    print(f"\n=== Database Check ===")
    print(f"Total chunks in database: {chunk_count}")
    
    if chunk_count == 0:
        print("\nERROR: NO CHUNKS FOUND!")
        print("This means the PDF processing didn't save chunks.")
        print("\nCheck the Celery worker logs for errors.")
    else:
        print(f"\nOK: {chunk_count} chunks found!")
        
        # Show chunks per document
        result = db.execute(text("""
            SELECT 
                d.title,
                d.id,
                d.status,
                COUNT(c.id) as chunk_count
            FROM pdf_document d
            LEFT JOIN pdf_chunk c ON d.id = c.doc_id
            GROUP BY d.id, d.title, d.status
            ORDER BY d.created_at DESC
        """))
        
        print("\nChunks per document:")
        for title, doc_id, status, cnt in result:
            print(f"  • {title}: {cnt} chunks (status: {status})")
            
        # Show sample chunk
        sample = db.query(PDFChunk).first()
        if sample:
            print(f"\nSample chunk:")
            print(f"  Content: {sample.content[:100]}...")
            print(f"  Pages: {sample.page_from}-{sample.page_to}")
            print(f"  Has embedding: {sample.embedding is not None}")
            if sample.embedding:
                print(f"  Embedding dimensions: {len(sample.embedding) if hasattr(sample.embedding, '__len__') else 'unknown'}")
        
finally:
    db.close()

