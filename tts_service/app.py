import os
import tempfile
import uuid
from datetime import datetime, timezone
from typing import Optional, List, AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, constr

from tts_service.synth_edge_tts import synthesize
from tts_service.pdf_processor import PDFProcessor, TextChunk

# Constants
TEMP_DIR = os.path.join(tempfile.gettempdir(), "tts_service")
os.makedirs(TEMP_DIR, exist_ok=True)

# Models
class TTSRequest(BaseModel):
    text: constr(min_length=1)
    voice: str = "en-US-AriaNeural"
    rate: str = "+0%"
    volume: str = "+0%"

class PDFSession(BaseModel):
    id: str
    chunks: List[TextChunk]
    current_index: int = 0
    last_accessed: datetime = datetime.now(timezone.utc)

# In-memory session store (would be Redis/DB in production)
pdf_sessions: dict[str, PDFSession] = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI app"""
    # Clean old files from temp directory
    for file in os.listdir(TEMP_DIR):
        try:
            os.remove(os.path.join(TEMP_DIR, file))
        except:
            pass
    yield

app = FastAPI(title="Edge-TTS Service", lifespan=lifespan)

@app.post("/pdf/upload")
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
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error processing PDF: {str(e)}")
        
        if not chunks:
            raise HTTPException(status_code=400, detail="No text content found in PDF")
        
        session_id = str(uuid.uuid4())
        pdf_sessions[session_id] = PDFSession(
            id=session_id, 
            chunks=chunks,
            last_accessed=datetime.now(timezone.utc)
        )
        
        return JSONResponse({
            "session_id": session_id,
            "total_chunks": len(chunks)
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/pdf/{session_id}/read/{chunk_index}")
async def read_chunk(session_id: str, chunk_index: int):
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/pdf/{session_id}/status")
async def get_status(session_id: str) -> JSONResponse:
    session = pdf_sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    current_chunk = session.chunks[session.current_index]
    return JSONResponse({
        "current_index": session.current_index,
        "total_chunks": len(session.chunks),
        "current_page": current_chunk.page_number
    })

@app.post("/tts")
async def synthesize_text(request: TTSRequest):
    try:
        audio_data = await synthesize(
            request.text,
            voice=request.voice,
            rate=request.rate,
            volume=request.volume
        )
        return Response(content=audio_data, media_type="audio/mpeg")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
