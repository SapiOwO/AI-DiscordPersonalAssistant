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

# --- Naturalness Configuration ---
# length_scale:  >1.0 = slower, more relaxed pacing (podcast feel)
# noise_scale:   higher = more phoneme variation (less monotone, more expressive)
# noise_w_scale: higher = more word duration variation (natural rhythm, not machine-gun)
TTS_LENGTH_SCALE = 1.1
TTS_NOISE_SCALE = 0.8
TTS_NOISE_W_SCALE = 0.9


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


# =============================================================================
# ADVANCED PROSODY ENGINE
# =============================================================================
# Transforms raw AI/LLM text into TTS-optimized text that Piper's phonemizer
# (espeak-ng) can render with natural pacing, intonation, and expressiveness.
# =============================================================================

# Chat shorthand → spoken English mapping
SHORTHAND_MAP = {
    r'\blol\b': 'haha',
    r'\blmao\b': 'hahaha',
    r'\bomg\b': 'oh my god',
    r'\bbtw\b': 'by the way',
    r'\bidk\b': "I don't know",
    r'\bimo\b': 'in my opinion',
    r'\bimho\b': 'in my honest opinion',
    r'\brn\b': 'right now',
    r'\bwyd\b': 'what are you doing',
    r'\bwbu\b': 'what about you',
    r'\bngl\b': 'not gonna lie',
    r'\btbh\b': 'to be honest',
    r'\bbrb\b': 'be right back',
    r'\bafk\b': 'away from keyboard',
    r'\bty\b': 'thank you',
    r'\bnp\b': 'no problem',
    r'\bpls\b': 'please',
    r'\bplz\b': 'please',
    r'\bthx\b': 'thanks',
    r'\bgtg\b': 'got to go',
    r'\bfr\b': 'for real',
    r'\bsmh\b': 'shaking my head',
    r'\bfyi\b': 'for your information',
    r'\bwdym\b': 'what do you mean',
    r'\birl\b': 'in real life',
    r'\bafaik\b': 'as far as I know',
    r'\bomw\b': 'on my way',
    r'\bwym\b': 'what you mean',
    r'\bgoat\b': 'greatest of all time',
}


def optimize_prosody(text: str) -> str:
    """
    Transform AI-generated text into TTS-optimized text for natural speech.
    Handles: non-verbal cues, hesitation pacing, humming/singing, chat shorthand,
    markdown cleanup, and punctuation-driven intonation control.
    """
    if not text or not text.strip():
        return ""

    # ===== PHASE 1: Strip non-speakable content =====
    # Remove non-ASCII (emoji, special chars) — NOT a raw string so \x works as hex
    text = re.sub('[^\x00-\x7F]+', ' ', text)

    # Remove markdown formatting (but preserve * for action detection below)
    text = re.sub(r'\*{2,}', '', text)          # ** bold → remove
    text = re.sub(r'[<>\[\]\(\)_~`#]', '', text)  # Other markdown syntax

    # ===== PHASE 2: Non-verbal cue translation =====
    # Map LLM emotive actions (*sighs*, *laughs*, etc.) into phonetic equivalents
    # that manipulate Piper's cadence via punctuation pauses

    # Sighs → breathy exhale pause
    text = re.sub(r'\*\s*sigh(?:s|ed|ing)?\s*\*', ', hahh, ', text, flags=re.IGNORECASE)
    # Laughs → natural laughter phonetics
    text = re.sub(r'\*\s*laugh(?:s|ed|ing)?\s*\*', ', hahaha, ', text, flags=re.IGNORECASE)
    text = re.sub(r'\*\s*chuckl(?:e|es|ed|ing)\s*\*', ', heh heh, ', text, flags=re.IGNORECASE)
    text = re.sub(r'\*\s*giggl(?:e|es|ed|ing)\s*\*', ', hehehe, ', text, flags=re.IGNORECASE)
    # Throat clear → ahem with pause
    text = re.sub(r'\*\s*clears?\s*(?:her |his |my )?throat\s*\*', ', ahem, ', text, flags=re.IGNORECASE)
    # Gasps → interjection
    text = re.sub(r'\*\s*gasp(?:s|ed|ing)?\s*\*', ', oh! ', text, flags=re.IGNORECASE)
    # Smiles/grins → strip silently (no audible equivalent)
    text = re.sub(r'\*\s*(?:smil|grin|nod|wink|shrug|eye ?roll)(?:s|ed|ing|ged|ks|gged)?\s*\*', ' ', text, flags=re.IGNORECASE)
    # Any remaining *action* tags → convert to comma pause
    text = re.sub(r'\*[^*]{1,50}\*', ', ', text)
    # Strip any leftover single asterisks
    text = text.replace('*', '')

    # ===== PHASE 3: Humming & singing normalization =====
    # Fix "hum/dot" artifacts and normalize phonetic spellings
    text = re.sub(r'\bhum\s*/\s*dot\b', 'hmm', text, flags=re.IGNORECASE)
    text = re.sub(r'\bhum(?:SLASH|\\)dot\b', 'hmm', text, flags=re.IGNORECASE)
    # Normalize extended humming: "hmmmmmm" → "hmm"
    text = re.sub(r'\bh+m{2,}\b', 'hmm', text, flags=re.IGNORECASE)
    # Affirmative hums: "mm-hmm", "mhm", "uh-huh" → clean phonetic
    text = re.sub(r'\b(?:mm-?hmm?|mhm+|uh-?huh)\b', 'mm hmm', text, flags=re.IGNORECASE)
    # Negative hums: "mm-mm", "nuh-uh"
    text = re.sub(r'\b(?:mm-?mm|nuh-?uh|uh-?uh)\b', 'mm mm', text, flags=re.IGNORECASE)
    # Single "mmm" → "hmm"
    text = re.sub(r'\bm{2,}\b', 'hmm', text, flags=re.IGNORECASE)

    # ===== PHASE 4: Hesitation & dynamic pacing =====
    # Convert textual pauses into punctuation that Piper's phonemizer respects
    # Ellipses → comma pause (Piper treats commas as ~200ms pauses)
    text = re.sub(r'\.{2,}', ', ', text)
    # Dashes as pauses (em-dash, en-dash, multi-hyphen)
    text = re.sub(r'\s*[—–]\s*', ', ', text)
    text = re.sub(r'\s*-{2,}\s*', ', ', text)
    # Standalone dash with spaces " - " → pause
    text = re.sub(r'\s+-\s+', ', ', text)

    # Vocal fillers → ensure surrounding pauses for natural timing
    # "umm" → ", umm,"  /  "uhh" → ", uhh,"  etc.
    text = re.sub(r'\b(u+mm+|u+hh*|e+rr+|a+hh+)\b', r', \1, ', text, flags=re.IGNORECASE)
    # "well" at sentence start → add comma for slight pause
    text = re.sub(r'(?:^|(?<=[.!?]\s))(well)\b', r'\1,', text, flags=re.IGNORECASE)

    # ===== PHASE 5: Chat shorthand expansion =====
    for pattern, replacement in SHORTHAND_MAP.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    # ===== PHASE 6: Punctuation normalization for intonation =====
    # Ensure spacing after sentence-ending punctuation
    text = re.sub(r'([.!?])(?=[a-zA-Z])', r'\1 ', text)
    # Ensure spacing after commas/semicolons/colons
    text = re.sub(r'([,;:])(?=[a-zA-Z])', r'\1 ', text)
    # Reduce excessive punctuation (sounds glitchy in TTS)
    text = re.sub(r'([!]){2,}', r'\1', text)       # !!! → !
    text = re.sub(r'([?]){2,}', r'\1', text)       # ??? → ?
    text = re.sub(r'([.]){2,}', r'\1', text)       # leftover dots

    # ===== PHASE 7: Final cleanup =====
    # Pipe characters (burst mode delimiter) → comma pause
    text = text.replace('|', ', ')
    # Add terminal punctuation if missing (forces natural pitch drop)
    text = text.strip()
    if text and text[-1] not in '.!?':
        text += '.'
    # Collapse multiple commas/spaces created by substitutions
    text = re.sub(r'[,\s]*,\s*', ', ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    # Clean leading comma if substitutions created one
    text = re.sub(r'^[,\s]+', '', text).strip()

    return text


# =============================================================================
# SYNTHESIS ENGINE — Sentence-Level with Dynamic Emotion
# =============================================================================

def _detect_emotion(sentence: str) -> dict:
    """Analyze a sentence for emotional cues and return adjusted synthesis parameters."""
    s = sentence.strip()
    # Default: calm, conversational
    params = {
        "length_scale": TTS_LENGTH_SCALE,
        "noise_scale": TTS_NOISE_SCALE,
        "noise_w_scale": TTS_NOISE_W_SCALE,
    }

    if s.endswith('?'):
        # Questions: slightly faster, more uncertain variation
        params["length_scale"] = TTS_LENGTH_SCALE - 0.1
        params["noise_scale"] = TTS_NOISE_SCALE + 0.1
    elif s.endswith('!'):
        # Exclamations: energetic, punchy
        params["length_scale"] = TTS_LENGTH_SCALE - 0.15
        params["noise_scale"] = TTS_NOISE_SCALE + 0.05
    elif ', ' in s and len(s) > 60:
        # Long, flowing sentences: slower, more relaxed
        params["length_scale"] = TTS_LENGTH_SCALE + 0.05
    
    # Hesitation markers → slower, more uncertain
    filler_count = len(re.findall(r'\b(?:umm|uhh|err|hmm|well)\b', s, flags=re.IGNORECASE))
    if filler_count >= 1:
        params["length_scale"] += 0.05 * min(filler_count, 2)

    return params


def _split_into_sentences(text: str) -> list:
    """Split text into sentences for individual synthesis.
    Preserves short fragments and doesn't over-split on abbreviations.
    """
    # Split on sentence-ending punctuation followed by whitespace or end
    parts = re.split(r'(?<=[.!?])\s+', text.strip())
    sentences = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        # Merge very short fragments (< 5 chars) with previous sentence
        if sentences and len(part) < 5 and part[-1] not in '.!?':
            sentences[-1] += ' ' + part
        else:
            sentences.append(part)
    return sentences if sentences else [text.strip()]


def _synthesize_sentence_to_wav(sentence: str, wav_path: str, emotion_params: dict):
    """Synthesize a single sentence with emotion-aware parameters."""
    syn_config = SynthesisConfig(
        length_scale=emotion_params["length_scale"],
        noise_scale=emotion_params["noise_scale"],
        noise_w_scale=emotion_params["noise_w_scale"],
    )
    with wave.open(wav_path, "wb") as wav_file:
        piper_voice.synthesize_wav(sentence, wav_file, syn_config=syn_config)


def _concatenate_wav_files(wav_paths: list, output_path: str):
    """Concatenate multiple WAV files into a single WAV file."""
    if not wav_paths:
        return
    
    # Read parameters from first valid file
    params = None
    for p in wav_paths:
        if os.path.exists(p) and os.path.getsize(p) > 44:
            with wave.open(p, 'rb') as wf:
                params = wf.getparams()
            break
    
    if not params:
        return
        
    with wave.open(output_path, 'wb') as out:
        out.setparams(params)
        for wav_path in wav_paths:
            try:
                if not os.path.exists(wav_path) or os.path.getsize(wav_path) <= 44:
                    continue
                with wave.open(wav_path, 'rb') as wf:
                    out.writeframes(wf.readframes(wf.getnframes()))
            except Exception as e:
                logger.warning(f"Skipping corrupt WAV segment: {e}")


async def synthesize(text: str) -> bytes:
    """Synthesize text to OGG Opus audio using sentence-level Piper TTS with dynamic emotion."""
    cleaned_text = optimize_prosody(text)

    if not cleaned_text or len(cleaned_text) < 2:
        logger.warning(f"TTS: Text empty after cleaning. Original: {text[:100]!r}")
        return None

    file_id = uuid.uuid4().hex
    temp_dir_batch = os.path.join(TEMP_DIR, f"batch_{file_id}")
    os.makedirs(temp_dir_batch, exist_ok=True)
    temp_combined_wav = os.path.join(TEMP_DIR, f"tts_{file_id}.wav")
    temp_ogg = os.path.join(TEMP_DIR, f"tts_{file_id}.ogg")
    segment_paths = []

    try:
        sentences = _split_into_sentences(cleaned_text)
        logger.debug(f"TTS: Synthesizing {len(sentences)} sentences: {cleaned_text[:150]!r}")

        # Synthesize each sentence with emotion-appropriate parameters
        for i, sentence in enumerate(sentences):
            if not sentence.strip() or len(sentence.strip()) < 2:
                continue
            emotion = _detect_emotion(sentence)
            seg_path = os.path.join(temp_dir_batch, f"seg_{i:03d}.wav")
            await asyncio.to_thread(_synthesize_sentence_to_wav, sentence, seg_path, emotion)
            segment_paths.append(seg_path)

        if not segment_paths:
            logger.error(f"TTS: No segments produced for: {cleaned_text[:80]!r}")
            return None

        # Concatenate all sentence WAVs into one
        if len(segment_paths) == 1:
            temp_combined_wav = segment_paths[0]
        else:
            await asyncio.to_thread(_concatenate_wav_files, segment_paths, temp_combined_wav)

        # Verify audio was generated
        wav_size = os.path.getsize(temp_combined_wav) if os.path.exists(temp_combined_wav) else 0
        if wav_size <= 44:
            logger.error(f"TTS: Combined WAV was {wav_size} bytes (no audio)")
            return None

        ffmpeg_path = os.getenv("FFMPEG_PATH", "ffmpeg")
        if ffmpeg_path != "ffmpeg" and not os.path.exists(ffmpeg_path):
            ffmpeg_path = "ffmpeg"

        # Convert WAV → OGG Opus for Discord voice messages
        process = await asyncio.create_subprocess_exec(
            ffmpeg_path, '-y', '-i', temp_combined_wav,
            '-c:a', 'libopus', '-b:a', '96k',
            '-application', 'voip',
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
        # Cleanup all temp files
        for p in segment_paths:
            if os.path.exists(p):
                try: os.remove(p)
                except: pass
        if os.path.exists(temp_dir_batch):
            try: os.rmdir(temp_dir_batch)
            except: pass
        if os.path.exists(temp_combined_wav):
            try: os.remove(temp_combined_wav)
            except: pass
        if os.path.exists(temp_ogg):
            try: os.remove(temp_ogg)
            except: pass