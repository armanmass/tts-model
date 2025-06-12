import os
import base64
import aiofiles
import asyncio
from typing import Optional

from tts_service.synth_edge_tts import synthesize

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, constr

app = FastAPI(title="Edge-TTS Service")

class SynthesizeRequest(BaseModel):
    text: constr(min_length=1)
    voice: str = "en-US-AriaNeural"
    rate: Optional[str] = "+0%"
    volume: Optional[str] = "+0%"
    format: str = "mp3"

@app.post("/synth")
async def synth(request: SynthesizeRequest, background_tasks: BackgroundTasks):
    try:
        output_path = await synthesize(
            request.text,
            voice=request.voice,
            rate=request.rate,
            volume=request.volume,
            format=request.format
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    file_like = open(output_path, "rb")
    media_type = "audio/mpeg"

    background_tasks.add_task(os.remove, output_path)

    return StreamingResponse(file_like, media_type=media_type, background=background_tasks)

@app.get("/health")
async def health_check():
    return {"status": "ok"}