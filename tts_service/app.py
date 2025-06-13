import os
import base64
import aiofiles
import asyncio
from typing import Optional
import tempfile
import uuid

from tts_service.synth_edge_tts import synthesize

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel, constr

app = FastAPI(title="Edge-TTS Service")

AUDIO_TEMP_DIR = os.path.join(tempfile.gettempdir(), "tts_audio")
os.makedirs(AUDIO_TEMP_DIR, exist_ok=True)

class SynthesizeRequest(BaseModel):
    text: constr(min_length=1)
    voice: str = "en-US-AriaNeural"
    rate: Optional[str] = "+0%"
    volume: Optional[str] = "+0%"
    format: str = "mp3"

async def file_iterator(file_path: str, chunk_size: int = 4096):
    async with aiofiles.open(file_path, "rb") as f:
        while True:
            chunk = await f.read(chunk_size)
            if not chunk:
                break
            yield chunk

@app.post("/synth")
async def synth(request: SynthesizeRequest, background_tasks: BackgroundTasks):
    filename = f"{uuid.uuid4()}.mp3"
    output_path = os.path.join(AUDIO_TEMP_DIR, filename)
    try:
        await synthesize(
            request.text,
            voice=request.voice,
            rate=request.rate,
            volume=request.volume,
            format=request.format,
            output_path=output_path
        )
        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            raise HTTPException(status_code=500, detail="Audio file is empty or missing")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    # Return the filename for GET access
    return {"filename": filename}

@app.get("/audio/{filename}")
async def get_audio(filename: str, background_tasks: BackgroundTasks):
    file_path = os.path.join(AUDIO_TEMP_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Audio not found")
    background_tasks.add_task(os.remove, file_path)
    return FileResponse(file_path, media_type="audio/mpeg", background=background_tasks)

@app.get("/health")
async def health_check():
    return {"status": "ok"}