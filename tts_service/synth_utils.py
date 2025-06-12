import os
import sys

import asyncio
import edge_tts

async def synthesize(text: str, voice: str, output_path: str, rate: str = "0%", \
                     volume: str = "0%") -> None:
    """
    Synthesize text to speech using Edge TTS.
    """
    #edge tts return mp3 by default
    communicate = edge_tts.Communicate(text, voice, rate=rate, volume=volume)
    temp_mp3_path = output_path + ".mp3"

    # write to temporary mp3 file
    with open(temp_mp3_path, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
    
    # TODO: convert mp3 to wav/other format if outpath does not end with .mp3
    os.rename(temp_mp3_path, output_path)
    print(f"Synthesized speech saved to {output_path}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Synthesize text to speech using Edge TTS.")
    parse.add_argument("--text", type=str, required=True, help="Text to synthesize")
    parser.add_argument("--voice", type=str, default="en-US-AriaNeural", help="Voice to use for synthesis")
    parser.add_argument("--output", type=str, default="output.mp3", help="Output file path")
    parser.add_argument("--rate", type=str, default="0%", help="Rate adjustment (e.g., '0%', '10%')")
    parser.add_argument("--volume", type=str, default="0%", help="Volume adjustment (e.g., '0%', '10%')")
    args = parser.parse_args()
    asyncio.run(synthesize(args.text, args.voice, args.output, rate=args.rate, volume=args.volume))


    


