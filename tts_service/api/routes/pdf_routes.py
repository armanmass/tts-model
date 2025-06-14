import os
import uuid
from datetime import datetime, timezone
from typing import Dict

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse, Response

from tts_service.models.tts_models import PDFSession
from tts_service.services.pdf_service import PDFProcessor, PDFExtractionError
from tts_service.services.tts_service import synthesize

router = APIRouter(prefix="/pdf", tags=["pdf"])

# In-memory session store (would be Redis/DB in production)
pdf_sessions: Dict[str, PDFSession] = {}

@router.post("/upload")
async def upload_pdf(file: UploadFile = File(...)) -> JSONResponse:
    """Upload and process a PDF file"""
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    try:
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Empty PDF file")
            
        processor = PDFProcessor()
        chunks = []
        
        try:
            async for chunk in processor.process_uploaded_pdf(content, file.filename):
                chunks.append(chunk)
        except PDFExtractionError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Unexpected error processing PDF: {str(e)}")
        
        if not chunks:
            raise HTTPException(status_code=400, detail="No text content found in PDF")
        
        session_id = str(uuid.uuid4())
        pdf_sessions[session_id] = PDFSession(
            id=session_id, 
            chunks=chunks,
            current_index=0,
            last_accessed=datetime.now(timezone.utc)
        )
        
        return JSONResponse({
            "session_id": session_id,
            "total_chunks": len(chunks)
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

@router.get("/{session_id}/read/{chunk_index}")
async def read_chunk(session_id: str, chunk_index: int):
    """Read a specific chunk from a PDF session"""
    session = pdf_sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    try:
        chunk = session.chunks[chunk_index]
    except IndexError:
        raise HTTPException(status_code=400, detail="Invalid chunk index")
    
    # Update session state
    session.current_index = chunk_index
    session.last_accessed = datetime.now(timezone.utc)
    
    # Generate audio directly to memory
    try:
        audio_data = await synthesize(chunk.text)
        return Response(content=audio_data, media_type="audio/mpeg")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating audio: {str(e)}")

@router.get("/{session_id}/status")
async def get_status(session_id: str) -> JSONResponse:
    """Get the current status of a PDF session"""
    session = pdf_sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    current_chunk = session.chunks[session.current_index]
    return JSONResponse({
        "current_index": session.current_index,
        "total_chunks": len(session.chunks),
        "current_page": current_chunk.page_number
    }) 