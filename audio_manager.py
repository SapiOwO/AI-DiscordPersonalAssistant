import os
import asyncio
import aiohttp
import logging
import subprocess
import wave
import re
import uuid
from faster_whisper import WhisperModel
from piper.voice import PiperVoice
from piper.config import SynthesisConfig
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("audio_manager")

MODEL_DIR = "./audio_models"
TEMP_DIR = "./temp_audio"

# ELITE UPGRADE: Using 'hfc_female' medium for significantly better clarity and expressive tone
PIPER_MODEL_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/hfc_female/medium/en_US-hfc_female-medium.onnx"
PIPER_CONFIG_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/hfc_female/medium/en_US-hfc_female-medium.onnx.json"

model_path = os.path.join(MODEL_DIR, "en_US-hfc_female-medium.onnx")
config_path = os.path.join(MODEL_DIR, "en_US-hfc_female-medium.onnx.json")

whisper_model = None
piper_voice = None

async def download_file(url: str, dest: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            response.raise_for_status()
            with open(dest, 'wb') as f:
                while True:
                    chunk = await response.content.read(8192)
                    if not chunk:
                        break
                    f.write(chunk)

async def init_models():
    global whisper_model, piper_voice
    os.makedirs(MODEL_DIR, exist_ok=True)
    os.makedirs(TEMP_DIR, exist_ok=True)

    logger.info("Initializing Faster-Whisper (STT) on CPU...")
    whisper_model = WhisperModel("base.en", device="cpu", compute_type="int8")

    if not os.path.exists(model_path) or not os.path.exists(config_path):
        logger.info("Downloading Upgraded Piper TTS English model (hfc_female)...")
        await download_file(PIPER_MODEL_URL, model_path)
        await download_file(PIPER_CONFIG_URL, config_path)
        logger.info("Piper TTS model downloaded successfully.")
    
    logger.info("Loading Piper Voice (TTS)...")
    piper_voice = PiperVoice.load(model_path, config_path)
    logger.info("Native Two-Way Audio system is fully operational.")

async def transcribe(audio_bytes: bytes) -> str:
    file_id = uuid.uuid4().hex
    temp_path = os.path.join(TEMP_DIR, f"stt_{file_id}.ogg")
    
    with open(temp_path, "wb") as f:
        f.write(audio_bytes)
    
    try:
        segments, _ = await asyncio.to_thread(whisper_model.transcribe, temp_path, beam_size=5)
        text = " ".join([segment.text for segment in segments])
        return text.strip()
    except Exception as e:
        logger.error(f"Transcription error: {e}")
        return ""
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

def optimize_prosody(text: str) -> str:
    """
    Optimize text for natural TTS prosody: clean markup, normalize punctuation,
    and inject pause cues that Piper's phonemizer respects.
    """
    # 1. Strip non-ASCII (emoji, special chars) — NOT a raw string so \x works as hex
    text = re.sub('[^\x00-\x7F]+', ' ', text)
    
    # 2. Remove markdown/formatting artifacts
    text = re.sub(r'[<>\[\]\(\)\*\|_~`#]', '', text)
    
    # 3. Normalize ellipses and dashes into natural pause commas
    text = re.sub(r'\.{2,}', ', ', text)       # ".." or "..." -> comma pause
    text = re.sub(r'\s*[-–—]{2,}\s*', ', ', text)  # "--" or "---" -> comma pause
    text = re.sub(r'\s*[-–—]\s+', ', ', text)       # standalone dash " - " -> comma pause

    # 4. Normalize common chat shorthand that Piper mispronounces
    text = re.sub(r'\blol\b', 'haha', text, flags=re.IGNORECASE)
    text = re.sub(r'\bomg\b', 'oh my god', text, flags=re.IGNORECASE)
    text = re.sub(r'\bbtw\b', 'by the way', text, flags=re.IGNORECASE)
    text = re.sub(r'\bidk\b', 'I don\'t know', text, flags=re.IGNORECASE)
    text = re.sub(r'\bimo\b', 'in my opinion', text, flags=re.IGNORECASE)
    text = re.sub(r'\bimho\b', 'in my honest opinion', text, flags=re.IGNORECASE)
    text = re.sub(r'\brn\b', 'right now', text, flags=re.IGNORECASE)
    text = re.sub(r'\bwyd\b', 'what are you doing', text, flags=re.IGNORECASE)
    text = re.sub(r'\bwbu\b', 'what about you', text, flags=re.IGNORECASE)
    text = re.sub(r'\bngl\b', 'not gonna lie', text, flags=re.IGNORECASE)
    text = re.sub(r'\btbh\b', 'to be honest', text, flags=re.IGNORECASE)
    text = re.sub(r'\bbrb\b', 'be right back', text, flags=re.IGNORECASE)
    text = re.sub(r'\bafk\b', 'away from keyboard', text, flags=re.IGNORECASE)

    # 5. Ensure spacing after punctuation so Piper doesn't slur words
    text = re.sub(r'([.!?])(?=[a-zA-Z])', r'\1 ', text)
    text = re.sub(r'([,;:])(?=[a-zA-Z])', r'\1 ', text)
    
    # 6. Strip repeated punctuation that sounds glitchy (e.g. "!!!" -> "!")
    text = re.sub(r'([!?]){2,}', r'\1', text)
    
    # 7. Add end punctuation if missing — forces natural pitch drop at sentence end
    text = text.strip()
    if text and text[-1] not in '.!?':
        text += '.'
    
    # 8. Collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

async def synthesize(text: str) -> bytes:
    """Synthesize text to OGG Opus audio bytes using Piper TTS."""
    cleaned_text = optimize_prosody(text)
    
    if not cleaned_text or len(cleaned_text) < 2:
        logger.warning(f"TTS: Text empty after cleaning. Original: {text[:100]!r}")
        return None

    logger.debug(f"TTS: Synthesizing: {cleaned_text[:120]!r}")

    file_id = uuid.uuid4().hex
    temp_wav = os.path.join(TEMP_DIR, f"tts_{file_id}.wav")
    temp_ogg = os.path.join(TEMP_DIR, f"tts_{file_id}.ogg")
    
    try:
        # Configure voice naturalness parameters:
        # - length_scale: >1.0 = slower/more relaxed, <1.0 = faster (1.05 = 5% slower for conversational feel)
        # - noise_scale: phoneme variation, higher = more expressive (default ~0.667)
        # - noise_w_scale: duration variation, higher = more natural rhythm (default ~0.8)
        syn_config = SynthesisConfig(
            length_scale=1.05,
            noise_scale=0.7,
            noise_w_scale=0.85,
        )
        
        # synthesize_wav is the correct method that writes audio to a WAV file
        # (synthesize() returns AudioChunk iterables, NOT file output)
        with wave.open(temp_wav, "wb") as wav_file:
            piper_voice.synthesize_wav(cleaned_text, wav_file, syn_config=syn_config)
        
        # Verify actual audio was generated (not just a 44-byte WAV header)
        wav_size = os.path.getsize(temp_wav) if os.path.exists(temp_wav) else 0
        if wav_size <= 44:
            logger.error(f"PIPER ERROR: WAV was {wav_size} bytes (no audio). Text: {cleaned_text[:80]!r}")
            return None
            
        ffmpeg_path = os.getenv("FFMPEG_PATH", "ffmpeg")
        if ffmpeg_path != "ffmpeg" and not os.path.exists(ffmpeg_path):
            ffmpeg_path = "ffmpeg"
            
        # Convert WAV -> OGG Opus for Discord voice messages
        # Using higher bitrate (96k) for clearer voice quality
        process = await asyncio.create_subprocess_exec(
            ffmpeg_path, '-y', '-i', temp_wav,
            '-c:a', 'libopus', '-b:a', '96k',
            '-application', 'voip',  # Optimized for speech
            temp_ogg,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            logger.error(f"FFmpeg conversion failed: {stderr.decode()}")
            return None
            
        with open(temp_ogg, "rb") as f:
            ogg_bytes = f.read()
        return ogg_bytes
    except Exception as e:
        logger.error(f"TTS synthesis error: {e}")
        return None
    finally:
        if os.path.exists(temp_wav): os.remove(temp_wav)
        if os.path.exists(temp_ogg): os.remove(temp_ogg)