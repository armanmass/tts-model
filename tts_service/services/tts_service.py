import io
import re
from typing import List
import edge_tts

async def synthesize(text: str, voice: str = "en-US-AriaNeural", rate: str = "+0%", volume: str = "+0%") -> bytes:
    """Synthesize text to speech using Edge TTS and return audio bytes"""
    if not text or not text.strip():
        raise ValueError("Text cannot be empty")
    
    # Validate parameters
    def validate_percentage(value: str, param_name: str) -> None:
        if not value.endswith('%'):
            raise ValueError(f"{param_name} must be a percentage value (e.g. '+20%')")
        try:
            num_value = int(value[:-1])
            if num_value < -100 or num_value > 100:
                raise ValueError(f"{param_name} must be between -100% and +100%")
        except ValueError:
            raise ValueError(f"{param_name} must be a valid percentage (e.g. '+20%')")

    validate_percentage(rate, "Rate")
    validate_percentage(volume, "Volume")
    
    buffer = io.BytesIO()
    communicate = edge_tts.Communicate(text, voice=voice, rate=rate, volume=volume)
    
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            buffer.write(chunk["data"])
    
    return buffer.getvalue()

def split_text(text: str, max_chars: int = 2000) -> List[str]:
    """Split text to avoid service limits"""
    sentences = re.split(r'(?<=[\.\?\!])\s+', text)
    
    chunks = []
    current_chunk = ""

    for s in sentences:
        if len(current_chunk) + len(s) + 1 <= max_chars:
            current_chunk += (" " + s if current_chunk else s).strip()
        else:
            if current_chunk: 
                chunks.append(current_chunk)
            current_chunk = s.strip()

    if current_chunk:
        chunks.append(current_chunk)
    
    return chunks 