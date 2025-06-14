from datetime import datetime, timezone
from typing import List, Annotated
from pydantic import BaseModel, Field

from tts_service.services.pdf_service import TextChunk

class TTSRequest(BaseModel):
    """Model for TTS synthesis requests"""
    text: Annotated[str, Field(min_length=1)]
    voice: str = "en-US-AriaNeural"
    rate: str = "+0%"
    volume: str = "+0%"

class PDFSession(BaseModel):
    """Model for PDF processing sessions"""
    id: str
    chunks: List[TextChunk]
    current_index: int = Field(default=0, ge=0)
    last_accessed: datetime = Field(default_factory=lambda: datetime.now(timezone.utc)) 