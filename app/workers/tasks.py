"""
Celery background tasks for PDF ingestion.
"""

import uuid
from sqlalchemy.orm import Session
from app.workers.celery_app import celery_app
from app.db import SessionLocal, get_supabase
from app.models import PDFDocument, PDFChunk, DocumentStatus
from app.services.pdf_service import process_pdf_chunks_sync


@celery_app.task(bind=True, max_retries=3)
def ingest_pdf_task(self, doc_id: str, storage_path: str):
    """
    Background task to ingest PDF: download, extract, chunk, embed, store.
    
    Args:
        doc_id: UUID string of the document
        storage_path: Path in Supabase Storage
    """
    db: Session = SessionLocal()
    
    try:
        # Get document from database
        doc_uuid = uuid.UUID(doc_id)
        doc = db.query(PDFDocument).filter(PDFDocument.id == doc_uuid).first()
        
        if not doc:
            raise ValueError(f"Document {doc_id} not found")
        
        # Download PDF from Supabase Storage
        supabase = get_supabase()
        bucket = "pdfs"
        
        try:
            pdf_bytes = supabase.storage.from_(bucket).download(storage_path)
        except Exception as e:
            # Update status to failed
            doc.status = DocumentStatus.FAILED.value
            db.commit()
            raise Exception(f"Failed to download PDF from storage: {str(e)}")
        
        # Process PDF: extract, chunk, embed
        try:
            num_pages, chunks_with_embeddings = process_pdf_chunks_sync(pdf_bytes, doc_id)
        except Exception as e:
            doc.status = DocumentStatus.FAILED.value
            db.commit()
            raise Exception(f"Failed to process PDF: {str(e)}")
        
        # Insert chunks into database
        # Note: Using add() instead of bulk_save_objects() to ensure proper type conversion
        for chunk_text, page_from, page_to, embedding in chunks_with_embeddings:
            chunk = PDFChunk(
                doc_id=doc_uuid,
                content=chunk_text,
                page_from=page_from,
                page_to=page_to,
                embedding=embedding  # pgvector will convert List[float] to vector type
            )
            db.add(chunk)
        
        # Update document with page count and status
        doc.num_pages = num_pages
        doc.status = DocumentStatus.READY.value
        db.commit()
        
        return {
            "document_id": doc_id,
            "num_pages": num_pages,
            "num_chunks": len(chunks_with_embeddings),
            "status": "ready"
        }
        
    except Exception as e:
        # Update status to failed if not already
        try:
            doc_uuid = uuid.UUID(doc_id)
            doc = db.query(PDFDocument).filter(PDFDocument.id == doc_uuid).first()
            if doc:
                doc.status = DocumentStatus.FAILED.value
                db.commit()
        except:
            pass
        
        # Retry on transient errors
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))
        else:
            raise e
    
    finally:
        db.close()
