import os
import asyncio
import aiohttp
import logging
import subprocess
import wave
import re
import uuid
import numpy as np
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("audio_manager")

MODEL_DIR = "./audio_models"
TEMP_DIR = "./temp_audio"

# --- OPTIONAL IMPORTS (Graceful Degradation) ---
try:
    from faster_whisper import WhisperModel
except ImportError:
    WhisperModel = None

try:
    import soundfile as sf
except ImportError:
    sf = None

try:
    from piper.voice import PiperVoice
    from piper.config import SynthesisConfig
except ImportError:
    PiperVoice = None

try:
    from kokoro import KPipeline
except ImportError:
    KPipeline = None

try:
    from pedalboard import Pedalboard, Compressor, HighpassFilter, PeakFilter, HighShelfFilter, Reverb
except ImportError:
    Pedalboard = None


# --- PIPER CONFIG ---
PIPER_MODEL_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/hfc_female/medium/en_US-hfc_female-medium.onnx"
PIPER_CONFIG_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/hfc_female/medium/en_US-hfc_female-medium.onnx.json"

model_path = os.path.join(MODEL_DIR, "en_US-hfc_female-medium.onnx")
config_path = os.path.join(MODEL_DIR, "en_US-hfc_female-medium.onnx.json")

whisper_model = None
piper_voice = None
kokoro_pipeline = None

def _ensure_dirs():
    os.makedirs(MODEL_DIR, exist_ok=True)
    os.makedirs(TEMP_DIR, exist_ok=True)

async def download_file(url, dest):
    if not os.path.exists(dest):
        logger.info(f"Downloading {os.path.basename(dest)}...")
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    with open(dest, 'wb') as f:
                        f.write(await response.read())
                else:
                    logger.error(f"Failed to download {url}")

async def init_models():
    global whisper_model, piper_voice, kokoro_pipeline
    _ensure_dirs()

    # 1. Initialize STT (Whisper)
    if WhisperModel:
        logger.info("Initializing Faster-Whisper (STT) on CPU...")
        whisper_model = WhisperModel("base.en", device="cpu", compute_type="int8")
    else:
        logger.warning("faster-whisper is not installed. STT disabled.")

    # 2. Determine TTS Engine
    tts_engine = os.getenv("TTS_ENGINE", "kokoro").lower()

    if tts_engine == "kokoro":
        if KPipeline:
            logger.info("Initializing Kokoro-82M TTS Engine...")
            voice_id = os.getenv("TTS_VOICE", "af_heart")
            # 'a' for American English, 'b' for British English based on voice prefix
            lang_code = voice_id[0] if voice_id else 'a'
            kokoro_pipeline = KPipeline(lang_code=lang_code)
            logger.info(f"Kokoro-82M Pipeline Initialized with voice: {voice_id}")
        else:
            logger.error("Kokoro is not installed! Falling back to Piper.")
            tts_engine = "piper"

    if tts_engine == "piper":
        if PiperVoice:
            logger.info("Loading Piper Voice (TTS)...")
            await download_file(PIPER_MODEL_URL, model_path)
            await download_file(PIPER_CONFIG_URL, config_path)
            if os.path.exists(model_path) and os.path.exists(config_path):
                piper_voice = PiperVoice.load(model_path, config_path)
                logger.info("Piper TTS Engine Initialized.")
        else:
            logger.error("Piper is not installed! TTS will be unavailable.")

    if Pedalboard:
        logger.info("Pedalboard Studio Mastering FX loaded successfully.")
    else:
        logger.warning("Pedalboard not found. Post-processing will be bypassed.")

    logger.info("Native Audio system initialization complete.")


async def transcribe(audio_bytes: bytes) -> str:
    if whisper_model is None:
        return ""
    _ensure_dirs()
    temp_in = os.path.join(TEMP_DIR, f"in_{uuid.uuid4().hex}.ogg")
    temp_wav = os.path.join(TEMP_DIR, f"in_{uuid.uuid4().hex}.wav")

    with open(temp_in, "wb") as f:
        f.write(audio_bytes)

    try:
        ffmpeg_path = os.getenv("FFMPEG_PATH", "ffmpeg")
        process = await asyncio.create_subprocess_exec(
            ffmpeg_path, '-y', '-i', temp_in, '-ar', '16000', '-ac', '1', temp_wav,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        await process.communicate()

        segments, _ = whisper_model.transcribe(temp_wav, beam_size=5)
        text = " ".join([segment.text for segment in segments])
        return text.strip()
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        return ""
    finally:
        if os.path.exists(temp_in): os.remove(temp_in)
        if os.path.exists(temp_wav): os.remove(temp_wav)


# --- SAPI's SECRET SAUCE 1: The Director (Pre-Processing) ---
def preprocess_text_for_tts(text: str) -> str:
    abbreviations = {
        r"\blol\b": "haha",
        r"\blmao\b": "oh my god",
        r"\bbrb\b": "be right back",
        r"\bbtw\b": "by the way",
        r"\bidk\b": "I don't know",
        r"\bimo\b": "in my opinion",
        r"\btbh\b": "to be honest",
        r"\brn\b": "right now",
        r"\bwdym\b": "what do you mean"
    }
    for pattern, replacement in abbreviations.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    text = re.sub(r'\b(and|but|so|because)\b', r',\1', text, flags=re.IGNORECASE)
    
    text = text.replace("...", "... ")
    text = text.replace(",,", ",")
    text = text.replace(" ,", ",")

    return text.strip()

def apply_studio_mastering(audio_array: np.ndarray, sample_rate: int) -> np.ndarray:
    if Pedalboard is None:
        return audio_array
    
    logger.info("Applying 200% Aggressive Punchy & Crisp Mastering...")
    board = Pedalboard([
        # 1. High-Pass Filter: Cut sub-bass rumble
        HighpassFilter(cutoff_frequency_hz=85),
        
        # 2. Extreme Body/Punch Boost: Double the low-mid weight
        PeakFilter(cutoff_frequency_hz=200, gain_db=3.0, q=1.0),
        
        # 3. Extreme Corrective EQ: aggressively scoop boxy/muddy frequencies
        PeakFilter(cutoff_frequency_hz=400, gain_db=-5.0, q=1.5),
        
        # 4. Hyper-Crisp Presence: Push articulation heavily
        PeakFilter(cutoff_frequency_hz=4500, gain_db=6.0, q=1.0),
        
        # 5. Extreme Air/Sparkle: 200% boost on the high-end for 96kHz clarity
        HighShelfFilter(cutoff_frequency_hz=10000, gain_db=8.0),
        
        # 6. Ultra-Punchy Compression: Heavy "In-your-face" radio compression
        Compressor(threshold_db=-24, ratio=6.0, attack_ms=15, release_ms=80),
        
        # 7. Micro-Reverb: Extremely tight, almost dry to prevent tail cuts
        Reverb(room_size=0.05, wet_level=0.02, dry_level=0.98)
    ])
    
    # Pedalboard expects shape (channels, samples)
    if audio_array.ndim == 1:
        audio_array = np.expand_dims(audio_array, axis=0)
        
    effected_audio = board(audio_array, sample_rate=sample_rate)
    
    # Convert back to 1D array
    return effected_audio.squeeze()


async def synthesize(text: str) -> bytes:
    if not text:
        return None
        
    engine = os.getenv("TTS_ENGINE", "kokoro").lower()
    if engine == "kokoro" and kokoro_pipeline is None:
        engine = "piper"
        
    if engine == "piper" and piper_voice is None:
        return None

    _ensure_dirs()
    temp_combined_wav = os.path.join(TEMP_DIR, f"out_{uuid.uuid4().hex}.wav")
    temp_ogg = os.path.join(TEMP_DIR, f"out_{uuid.uuid4().hex}.ogg")
    
    processed_text = preprocess_text_for_tts(text)

    try:
        if engine == "kokoro" and KPipeline is not None and sf is not None:
            voice_id = os.getenv("TTS_VOICE", "af_heart")
            logger.info(f"Generating Kokoro TTS with voice: {voice_id}")
            
            # Generate audio chunks
            generator = kokoro_pipeline(processed_text, voice=voice_id, speed=1.0, split_pattern=r'\n+')
            audio_chunks = []
            
            for i, (gs, ps, audio) in enumerate(generator):
                audio_chunks.append(audio)
                
            if not audio_chunks:
                return None
                
            combined_audio = np.concatenate(audio_chunks)
            mastered_audio = apply_studio_mastering(combined_audio, 24000)
            
            # Save to WAV
            sf.write(temp_combined_wav, mastered_audio, 24000)
            
        else: # Piper Fallback
            logger.info("Generating Piper TTS audio...")
            temp_dir_batch = os.path.join(TEMP_DIR, f"batch_{uuid.uuid4().hex}")
            os.makedirs(temp_dir_batch, exist_ok=True)
            sentences = re.split(r'(?<=[.!?])\s+', processed_text)
            
            segment_paths = []
            for i, sentence in enumerate(sentences):
                sentence = sentence.strip()
                if not sentence: continue
                seg_path = os.path.join(temp_dir_batch, f"seg_{i}.wav")
                with wave.open(seg_path, "wb") as wav_file:
                    syn_config = SynthesisConfig(
                        length_scale=1.1,
                        noise_scale=0.75,
                        noise_w_scale=0.85,
                    )
                    piper_voice.synthesize_wav(sentence, wav_file, syn_config=syn_config)
                segment_paths.append(seg_path)

            if not segment_paths:
                return None

            # Combine Piper chunks and optionally master them if soundfile/pedalboard are available
            if sf is not None and Pedalboard is not None:
                audio_chunks = []
                sample_rate = 22050
                for p in segment_paths:
                    data, sr = sf.read(p)
                    audio_chunks.append(data)
                    sample_rate = sr
                
                combined_audio = np.concatenate(audio_chunks)
                mastered_audio = apply_studio_mastering(combined_audio, sample_rate)
                sf.write(temp_combined_wav, mastered_audio, sample_rate)
            else:
                # Basic WAV concatenation if no soundfile library
                data = []
                for p in segment_paths:
                    w = wave.open(p, 'rb')
                    data.append([w.getparams(), w.readframes(w.getnframes())])
                    w.close()
                with wave.open(temp_combined_wav, 'wb') as output:
                    output.setparams(data[0][0])
                    for params, frames in data:
                        output.writeframes(frames)
                        
            # Cleanup piper segments
            for p in segment_paths:
                if os.path.exists(p): os.remove(p)
            if os.path.exists(temp_dir_batch): os.rmdir(temp_dir_batch)

        # Convert WAV to OGG Opus via FFmpeg
        ffmpeg_path = os.getenv("FFMPEG_PATH", "ffmpeg")
        process = await asyncio.create_subprocess_exec(
            ffmpeg_path, '-y', '-i', temp_combined_wav,
            '-c:a', 'libopus', '-b:a', '96k', '-application', 'voip',
            temp_ogg, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            logger.error(f"FFmpeg conversion failed: {stderr.decode()}")
            return None

        with open(temp_ogg, "rb") as f:
            ogg_bytes = f.read()
        return ogg_bytes

    except Exception as e:
        logger.error(f"TTS synthesis error: {e}", exc_info=True)
        return None
    finally:
        if os.path.exists(temp_combined_wav):
            try: os.remove(temp_combined_wav)
            except: pass
        if os.path.exists(temp_ogg):
            try: os.remove(temp_ogg)
            except: pass