"""
Document routes.
"""

import uuid
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status, Body
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional, List
from pydantic import BaseModel
from app.auth import get_current_user
from app.db import get_db, get_supabase
from app.models import PDFDocument, DocumentStatus, PDFChunk
from app.schemas import PDFDocumentResponse
from app.workers.tasks import ingest_pdf_task
from app.services.openai_service import get_embedding
from app.services.vector_search import search_similar_chunks
from app.services.chat_service import answer_question
from app.services.billing_service import (
    increment_usage,
    prepare_usage_context,
    usage_remaining,
)

router = APIRouter()


# Request/Response schemas for chat
class ChatRequest(BaseModel):
    question: str
    k: Optional[int] = 5  # Number of chunks to retrieve


class Citation(BaseModel):
    text: str  # e.g., "[p3]" or "[p3–4]"
    pages: List[int]  # e.g., [3] or [3, 4]


class ChatResponse(BaseModel):
    answer: str
    citations: List[str]
    context_used: int  # Number of chunks used
    similarity_scores: List[float]  # Similarity scores of retrieved chunks


@router.get("/{document_id}")
async def get_document(
    document_id: str,
    clerk_user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a single document by ID."""
    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid document ID format"
        )
    
    doc = db.query(PDFDocument).filter(
        PDFDocument.id == doc_uuid,
        PDFDocument.owner_clerk_user_id == clerk_user_id
    ).first()
    
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found or you don't have access"
        )
    
    return {
        "id": str(doc.id),
        "title": doc.title,
        "num_pages": doc.num_pages,
        "status": doc.status,
        "created_at": doc.created_at.isoformat(),
    }


@router.get("/")
async def list_documents(
    clerk_user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List user's documents (personal and team)."""
    # Get user's personal documents
    personal_docs = db.query(PDFDocument).filter(
        PDFDocument.owner_clerk_user_id == clerk_user_id,
        PDFDocument.team_id.is_(None)
    ).all()
    
    # Get team documents (where user is a team member)
    # TODO: Add team membership check when team routes are implemented
    team_docs = db.query(PDFDocument).filter(
        PDFDocument.owner_clerk_user_id == clerk_user_id,
        PDFDocument.team_id.isnot(None)
    ).all()
    
    all_docs = personal_docs + team_docs
    
    return {
        "documents": [
            {
                "id": str(doc.id),
                "title": doc.title,
                "num_pages": doc.num_pages,
                "status": doc.status,  # status is already a string, not an enum
                "created_at": doc.created_at.isoformat(),
            }
            for doc in all_docs
        ]
    }


@router.get("/{document_id}")
async def get_document(
    document_id: str,
    clerk_user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a specific document."""
    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid document ID format"
        )
    
    doc = db.query(PDFDocument).filter(
        PDFDocument.id == doc_uuid,
        PDFDocument.owner_clerk_user_id == clerk_user_id
    ).first()
    
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    return PDFDocumentResponse.model_validate(doc)


@router.post("/upload")
async def upload_pdf(
    file: UploadFile = File(...),
    team_id: Optional[str] = None,
    clerk_user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload a PDF file for processing.
    
    Flow:
    1. Verify JWT → get clerk_user_id
    2. Store PDF to Supabase Storage
    3. Create pdf_document row with status='processing'
    4. Enqueue Celery task for ingestion
    """
    # Validate file type
    if not file.filename.endswith('.pdf'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a PDF"
        )
    
    # Validate file size (10MB limit)
    file_content = await file.read()
    if len(file_content) > 10 * 1024 * 1024:  # 10MB
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size exceeds 10MB limit"
        )
    
    # Validate team_id if provided
    team_uuid = None
    if team_id:
        try:
            team_uuid = uuid.UUID(team_id)
            # TODO: Verify user is member of this team
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid team ID format"
            )
    
    # Generate document ID and storage path
    doc_id = uuid.uuid4()
    storage_path = f"pdfs/{clerk_user_id}/{doc_id}.pdf"
    if team_uuid:
        storage_path = f"pdfs/teams/{team_uuid}/{doc_id}.pdf"
    
    # Upload to Supabase Storage
    try:
        supabase = get_supabase()
        bucket = "pdfs"  # Create this bucket in Supabase Storage
        
        # Upload file
        supabase.storage.from_(bucket).upload(
            path=storage_path,
            file=file_content,
            file_options={"content-type": "application/pdf"}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file to storage: {str(e)}"
        )
    
    # Create database record
    doc = PDFDocument(
        id=doc_id,
        owner_clerk_user_id=clerk_user_id,
        team_id=team_uuid,
        title=file.filename or "Untitled PDF",
        num_pages=0,  # Will be updated by worker
        storage_path=storage_path,
        status=DocumentStatus.PROCESSING.value  # Use .value to ensure lowercase string
    )
    
    db.add(doc)
    db.commit()
    db.refresh(doc)
    
    # Enqueue Celery task for background processing
    try:
        ingest_pdf_task.delay(str(doc_id), storage_path)
    except Exception as e:
        # If Celery/Redis is not available, log error but don't fail the upload
        import logging
        logging.warning(f"Failed to enqueue Celery task (Redis may not be running): {e}")
        # Optionally, you could process synchronously here, but it's not recommended
        # For now, the document is created and can be processed later when Redis is available
    
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={
            "message": "PDF uploaded successfully. Processing in background.",
            "document_id": str(doc_id),
            "status": "processing"
        }
    )


@router.post("/{document_id}/ask", response_model=ChatResponse)
async def ask_question(
    document_id: str,
    request: ChatRequest,
    clerk_user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Ask a question about a PDF document using RAG.
    
    Flow:
    1. Verify ownership/membership
    2. Embed query
    3. Retrieve top-k chunks by cosine similarity
    4. Apply similarity threshold (reject if < 0.70)
    5. Build prompt with strict citation rules
    6. Call gpt-4o-mini for answer
    7. Return answer with citations
    """
    # Validate document ID
    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid document ID format"
        )
    
    # Get document and verify ownership
    doc = db.query(PDFDocument).filter(
        PDFDocument.id == doc_uuid,
        PDFDocument.owner_clerk_user_id == clerk_user_id
    ).first()
    
    # TODO: Also check team membership when team routes are implemented
    
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found or you don't have access"
        )
    
    # Check if document is ready
    if doc.status != "ready":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Document is not ready for chat. Current status: {doc.status}"
        )
    
    # Usage enforcement (personal or team credits)
    usage_context = prepare_usage_context(
        db,
        clerk_user_id=clerk_user_id,
        team_id=str(doc.team_id) if doc.team_id else None,
    )

    remaining = usage_remaining(usage_context)
    if remaining <= 0:
        plan_name = usage_context.plan.product.value.capitalize()
        friendly_message = (
            f"You've used all {usage_context.plan.monthly_credits} monthly chat credits on the "
            f"{plan_name} plan. Visit /pricing to upgrade or wait for the next billing cycle."
        )
        return ChatResponse(
            answer=friendly_message,
            citations=[],
            context_used=0,
            similarity_scores=[],
        )

    # Embed the question
    try:
        query_embedding = await get_embedding(request.question)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate query embedding: {str(e)}"
        )
    
    # Retrieve similar chunks
    k = min(request.k or 5, 10)  # Cap at 10 chunks
    similarity_threshold = 0.50  # Lowered from 0.70 for testing
    
    try:
        chunks_with_scores = await search_similar_chunks(
            db=db,
            doc_id=document_id,
            query_embedding=query_embedding,
            k=k,
            similarity_threshold=similarity_threshold
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to search similar chunks: {str(e)}"
        )
    
    # Check if we have relevant chunks
    if not chunks_with_scores:
        return ChatResponse(
            answer="I can't find relevant information about that in the document. The question may be outside the scope of this PDF.",
            citations=[],
            context_used=0,
            similarity_scores=[]
        )
    
    # Prepare context for RAG
    context_chunks = [
        (chunk.content, chunk.page_from, chunk.page_to, similarity)
        for chunk, similarity in chunks_with_scores
    ]
    
    # Generate answer using RAG
    try:
        answer, citations = await answer_question(
            question=request.question,
            context_chunks=context_chunks,
            model="gpt-4o-mini"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate answer: {str(e)}"
        )
    
    # Extract similarity scores
    similarity_scores = [score for _, score in chunks_with_scores]

    # Record usage after successful response
    increment_usage(db, usage_context)
    
    return ChatResponse(
        answer=answer,
        citations=citations,
        context_used=len(chunks_with_scores),
        similarity_scores=similarity_scores
    )

