import os
import asyncio
import aiohttp
import logging
import subprocess
import wave
import re
import uuid
import numpy as np

import config

logger = logging.getLogger("audio_manager")

MODEL_DIR = "./audio_models"
TEMP_DIR = "./temp_audio"
ASSETS_DIR = "./assets/emotions"

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
    from pedalboard import Pedalboard, Compressor, HighpassFilter, PeakFilter, HighShelfFilter, Reverb, PitchShift
except ImportError:
    Pedalboard = None

PIPER_MODEL_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/hfc_female/medium/en_US-hfc_female-medium.onnx"
PIPER_CONFIG_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/hfc_female/medium/en_US-hfc_female-medium.onnx.json"

whisper_model = None
piper_voice = None
kokoro_pipeline = None

def _ensure_dirs():
    os.makedirs(MODEL_DIR, exist_ok=True)
    os.makedirs(TEMP_DIR, exist_ok=True)
    os.makedirs(ASSETS_DIR, exist_ok=True)

async def download_file(url, dest):
    if not os.path.exists(dest):
        logger.info(f"Downloading {os.path.basename(dest)}...")
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    with open(dest, 'wb') as f:
                        f.write(await response.read())
                else:
                    logger.error(f"Failed to download {url}. HTTP Status: {response.status}")

async def init_models():
    global whisper_model, piper_voice, kokoro_pipeline
    _ensure_dirs()

    if WhisperModel:
        logger.info("Initializing Faster-Whisper (STT) on CPU...")
        whisper_model = WhisperModel("base.en", device="cpu", compute_type="int8")
    else:
        logger.warning("faster-whisper is not installed. STT disabled.")

    tts_engine = config.TTS_ENGINE.lower()

    if tts_engine == "kokoro":
        if KPipeline:
            logger.info("Initializing Kokoro-82M TTS Engine...")
            voice_id = getattr(config, "TTS_VOICE_KOKORO", "af_heart")
            lang_code = voice_id[0] if voice_id else 'a'
            kokoro_pipeline = KPipeline(lang_code=lang_code)
            logger.info(f"Kokoro-82M Pipeline Initialized with voice: {voice_id}")
        else:
            logger.error("Kokoro is not installed! Falling back to Piper.")
            tts_engine = "piper"

    if tts_engine == "piper":
        if PiperVoice:
            piper_voice_name = getattr(config, "TTS_VOICE_PIPER", "en_US-hfc_female-medium")
            logger.info(f"Loading Piper Voice (TTS): {piper_voice_name}...")
            
            try:
                parts = piper_voice_name.split('-')
                lang = parts[0]
                lang_family = lang.split('_')[0]
                voice = parts[1]
                quality = parts[2]

                base_url = f"https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/{lang_family}/{lang}/{voice}/{quality}"
                piper_model_url = f"{base_url}/{piper_voice_name}.onnx"
                piper_config_url = f"{base_url}/{piper_voice_name}.onnx.json"

                model_path = os.path.join(MODEL_DIR, f"{piper_voice_name}.onnx")
                config_path = os.path.join(MODEL_DIR, f"{piper_voice_name}.onnx.json")

                await download_file(piper_model_url, model_path)
                await download_file(piper_config_url, config_path)

                if os.path.exists(model_path) and os.path.exists(config_path):
                    piper_voice = PiperVoice.load(model_path, config_path)
                    logger.info(f"Piper TTS Engine Initialized with {piper_voice_name}.")
                else:
                    logger.error("Failed to initialize Piper: Model files not found after download attempt.")
            except Exception as e:
                logger.error(f"Error parsing Piper voice format: {e}. Please use format 'lang-voice-quality'.")
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
        ffmpeg_path = config.FFMPEG_PATH
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


def preprocess_text_for_tts(text: str):
    text = re.sub(r'[*_~`"\']', '', text)

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
    text = text.replace("...", "... ").replace(",,", ",").replace(" ,", ",")
    text = text.replace("—", ", ")

    parts = re.split(r'(\[[a-zA-Z0-9:]+\])', text)
    processed_parts = []
    
    for part in parts:
        if not part.strip():
            continue
        if part.startswith('[') and part.endswith(']'):
            processed_parts.append(('tag', part.strip('[]').lower()))
        else:
            processed_parts.append(('text', part.strip()))
            
    return processed_parts

def generate_musical_hum(base_audio: np.ndarray, sample_rate: int, pattern="scale_up") -> np.ndarray:
    if Pedalboard is None:
        return base_audio

    if pattern == "scale_up":
        steps = [0, 2, 4] 
    elif pattern == "thinking":
        steps = [0, -2, 0] 
    else:
        steps = [0]

    segments = []
    for step in steps:
        shift = PitchShift(semitones=step)
        shifted = shift(base_audio, sample_rate)
        segments.append(shifted)
    
    return np.concatenate(segments)

def apply_studio_mastering(audio_array: np.ndarray, sample_rate: int) -> np.ndarray:
    if Pedalboard is None:
        return audio_array
    
    # FIX 1: Ensure the incoming audio array is strictly float32 (required by Pedalboard)
    audio_array = audio_array.astype(np.float32)
    
    tail_duration = 2.0 
    tail_samples = int(tail_duration * sample_rate)
    
    # FIX 2: Ensure dither array is perfectly sized and typed
    dither_pad = np.random.normal(0, 0.00001, size=tail_samples).astype(np.float32)
    
    padded_audio = np.concatenate((audio_array, dither_pad))

    if padded_audio.ndim == 1:
        stereo_audio = np.vstack((padded_audio, padded_audio))
    else:
        stereo_audio = padded_audio

    board = Pedalboard([
        HighpassFilter(cutoff_frequency_hz=60),
        PeakFilter(cutoff_frequency_hz=300, gain_db=-1.5, q=1.5),
        PeakFilter(cutoff_frequency_hz=3500, gain_db=1.5, q=1.0),
        HighShelfFilter(cutoff_frequency_hz=10000, gain_db=2.0),
        Compressor(threshold_db=-12, ratio=2.0, attack_ms=15, release_ms=250),
        Reverb(room_size=0.2, damping=0.4, wet_level=0.08, dry_level=0.95, width=1.0) 
    ])
    
    effected_audio = board(stereo_audio, sample_rate=sample_rate)
    return effected_audio


async def synthesize(text: str) -> bytes:
    if not text:
        logger.warning("TTS: Received empty text to synthesize.")
        return None
        
    engine = config.TTS_ENGINE.lower()
    if engine == "kokoro" and kokoro_pipeline is None:
        logger.warning("TTS: Kokoro requested but not loaded. Falling back to Piper.")
        engine = "piper"
        
    if engine == "piper" and piper_voice is None:
        logger.error("TTS: No TTS engines are loaded.")
        return None

    _ensure_dirs()
    temp_combined_wav = os.path.join(TEMP_DIR, f"out_{uuid.uuid4().hex}.wav")
    temp_ogg = os.path.join(TEMP_DIR, f"out_{uuid.uuid4().hex}.ogg")
    
    segments = preprocess_text_for_tts(text)
    if not segments:
        logger.warning("TTS: No valid text segments left after preprocessing.")
        return None

    audio_chunks = []
    global_sr = 24000 if engine == "kokoro" else 22050

    try:
        for kind, content in segments:
            if not content: continue
            
            if kind == 'text':
                if engine == "kokoro" and KPipeline is not None:
                    voice_id = getattr(config, "TTS_VOICE_KOKORO", "af_heart")
                    generator = kokoro_pipeline(content, voice=voice_id, speed=1.0, split_pattern=r'\n+')
                    for _, _, audio in generator:
                        audio_chunks.append(audio)
                
                elif engine == "piper":
                    temp_dir_batch = os.path.join(TEMP_DIR, f"batch_{uuid.uuid4().hex}")
                    os.makedirs(temp_dir_batch, exist_ok=True)
                    sub_sentences = re.split(r'(?<=[.!?])\s+', content)
                    
                    for i, sentence in enumerate(sub_sentences):
                        sentence = sentence.strip()
                        if not sentence: continue
                        seg_path = os.path.join(temp_dir_batch, f"seg_{i}.wav")
                        
                        with wave.open(seg_path, "wb") as wav_file:
                            wav_file.setnchannels(1)
                            wav_file.setsampwidth(2)
                            wav_file.setframerate(22050)
                            
                            syn_config = SynthesisConfig(
                                length_scale=1.1,
                                noise_scale=0.75,
                                noise_w_scale=0.85
                            )
                            piper_voice.synthesize_wav(sentence, wav_file, syn_config=syn_config)
                        
                        if sf is not None:
                            data, sr = sf.read(seg_path)
                            audio_chunks.append(data)
                        os.remove(seg_path)
                    os.rmdir(temp_dir_batch)

            elif kind == 'tag':
                if content == 'laugh':
                    laugh_path = os.path.join(ASSETS_DIR, "human_laugh.wav")
                    if sf is not None and os.path.exists(laugh_path):
                        data, sr = sf.read(laugh_path)
                        if sr != global_sr and len(data) > 0:
                            data = np.interp(np.linspace(0, len(data), int(len(data) * global_sr / sr)), np.arange(len(data)), data)
                        if data.ndim > 1: data = data.mean(axis=1) 
                        audio_chunks.append(data)
                        
                elif content in ['hmm', 'hum:up']:
                    if engine == "kokoro" and KPipeline is not None:
                        voice_id = getattr(config, "TTS_VOICE_KOKORO", "af_heart")
                        generator = kokoro_pipeline("mmm", voice=voice_id, speed=0.8)
                        pattern = "thinking" if content == 'hmm' else "scale_up"
                        for _, _, audio in generator:
                            hummed = generate_musical_hum(audio, global_sr, pattern)
                            audio_chunks.append(hummed)
                    elif engine == "piper":
                        temp_hum = os.path.join(TEMP_DIR, f"hum_{uuid.uuid4().hex}.wav")
                        with wave.open(temp_hum, "wb") as w:
                            w.setnchannels(1)
                            w.setsampwidth(2)
                            w.setframerate(22050)
                            syn_config = SynthesisConfig(length_scale=1.1, noise_scale=0.75, noise_w_scale=0.85)
                            piper_voice.synthesize_wav("mmm", w, syn_config=syn_config)
                            
                        if sf is not None:
                            data, _ = sf.read(temp_hum)
                            pattern = "thinking" if content == 'hmm' else "scale_up"
                            hummed = generate_musical_hum(data, global_sr, pattern)
                            audio_chunks.append(hummed)
                        os.remove(temp_hum)

        if not audio_chunks:
            logger.warning("TTS: No audio chunks generated. Teks mungkin hanya berisi karakter tidak terbaca.")
            return None

        # FIX 3: Ensure Float32 before Master
        combined_mono_audio = np.concatenate(audio_chunks).astype(np.float32)
        
        if sf is not None and Pedalboard is not None:
            final_stereo_audio = apply_studio_mastering(combined_mono_audio, global_sr)
            # Transpose to (frames, channels) for soundfile writing
            sf.write(temp_combined_wav, final_stereo_audio.T, global_sr)
        else:
            if sf is not None:
                sf.write(temp_combined_wav, combined_mono_audio, global_sr)

        # FIX 4: Safety check if WAV file was actually created and has size
        if not os.path.exists(temp_combined_wav) or os.path.getsize(temp_combined_wav) == 0:
            logger.error("TTS: WAV file creation failed or file is empty before FFmpeg.")
            return None

        ffmpeg_path = config.FFMPEG_PATH
        process = await asyncio.create_subprocess_exec(
            ffmpeg_path, '-y', '-i', temp_combined_wav,
            '-c:a', 'libopus', '-b:a', '96k', '-ac', '2', '-application', 'voip',
            temp_ogg, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            logger.error(f"FFmpeg conversion failed: {stderr.decode()}")
            return None

        with open(temp_ogg, "rb") as f:
            ogg_bytes = f.read()
            
        if not ogg_bytes:
            logger.error("TTS: Output OGG file is empty.")
            return None
            
        return ogg_bytes

    except Exception as e:
        logger.error(f"Hybrid Synthesis error: {e}", exc_info=True)
        return None
    finally:
        if os.path.exists(temp_combined_wav):
            try: os.remove(temp_combined_wav)
            except: pass
        if os.path.exists(temp_ogg):
            try: os.remove(temp_ogg)
            except: pass