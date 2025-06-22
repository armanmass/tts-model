import os
import io

import asyncio
import tempfile
import subprocess

import edge_tts

from typing import List, AsyncIterator

async def synthesize(text: str, voice: str = "en-US-AriaNeural", rate: str = "+0%", volume: str = "+0%") -> bytes:
    """Synthesize text to speech using Edge TTS and return audio bytes"""
    buffer = io.BytesIO()
    communicate = edge_tts.Communicate(text, voice=voice, rate=rate, volume=volume)
    
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            buffer.write(chunk["data"])
    
    return buffer.getvalue()

def split_text(text: str, max_chars: int = 2000) -> List[str]:
    """
    Split text to avoid service limits.
    """

    import re
    sentences = re.split(r'(?<=[\.\?\!])\s+', text)
    
    chunks = []
    current_chunk = ""

    for s in sentences:
        if len(current_chunk) + len(s) + 1 <= max_chars:
            current_chunk += (" " + s if current_chunk else s).strip()
        else:
            if current_chunk: chunks.append(current_chunk)
            current_chunk = s.strip()

    if current_chunk:
        chunks.append(current_chunk)
    
    return chunks



if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Synthesize text to speech using Edge TTS.")
    parser.add_argument("--text", type=str, required=True, help="Text to synthesize")
    parser.add_argument("--voice", type=str, default="en-US-AriaNeural", help="Voice to use for synthesis")
    parser.add_argument("--output", type=str, default="output.mp3", help="Output file path")
    parser.add_argument("--rate", type=str, default="+0%", help="Rate adjustment (e.g., '0%', '10%')")
    parser.add_argument("--volume", type=str, default="+0%", help="Volume adjustment (e.g., '0%', '10%')")
    args = parser.parse_args()
    asyncio.run(synthesize(args.text, args.voice, args.rate, args.volume))

    async def save_audio():
        audio_bytes = await synthesize(args.text, args.voice, args.rate, args.volume)
        with open(args.output, "wb") as f:
            f.write(audio_bytes)
        print(f"Saved audio to {args.output}")

    asyncio.run(save_audio())
