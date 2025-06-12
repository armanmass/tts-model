import os
import tempfile
import subprocess
import shutil

import asyncio
import edge_tts

from typing import List

async def synthesize(text: str, voice: str, output_path: str = "local.mp3", rate: str = "+0%", \
                     volume: str = "+0%", format: str = ".mp3") -> str:
    """
    Synthesize text to speech using Edge TTS.
    """
    texts = [text] if len(text) <= 2000 else split_text(text)
    temp_files = []

    for i, chunk in enumerate(texts):
        temp_fd, temp_mp3_path = tempfile.mkstemp(suffix=".mp3")
        os.close(temp_fd)

        comm = edge_tts.Communicate(chunk, voice=voice, rate=rate, volume=volume)

        with open(temp_mp3_path, "wb") as f:
            async for chunk in comm.stream():
                if chunk["type"] == "audio":
                    f.write(chunk["data"])
        temp_files.append(temp_mp3_path)
    
    if len(temp_files) == 1:
        shutil.move(temp_files[0], output_path)
    else:
        list_fd, list_path = tempfile.mkstemp(suffix=".txt")
        with os.fdopen(list_fd, 'w') as lf:
            for mp3_path in temp_files:
                lf.write(f"file '{mp3_path}'\n")
        
        try:
            subprocess.run([
                "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_path,
                "-c", "copy", output_path
            ], check=True)
        except Exception as e:
            raise RuntimeError(f"Failed to concatenate audio files: {e}")
        finally:
            for fpath in temp_files:
                os.remove(fpath)
            os.remove(list_path)
    return output_path
    

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
    asyncio.run(synthesize(args.text, args.voice, args.output, rate=args.rate, volume=args.volume))


    


