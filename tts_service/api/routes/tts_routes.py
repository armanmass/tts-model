from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from tts_service.models.tts_models import TTSRequest
from tts_service.services.tts_service import synthesize

router = APIRouter(prefix="/tts", tags=["tts"])

@router.post("")
async def synthesize_text(request: TTSRequest) -> Response:
    """Synthesize text to speech"""
    try:
        audio_data = await synthesize(
            text=request.text,
            voice=request.voice,
            rate=request.rate,
            volume=request.volume
        )
        return Response(content=audio_data, media_type="audio/mpeg")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 