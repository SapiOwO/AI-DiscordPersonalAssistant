# Discord AI Personal Assistant — Update Journal

This journal documents critical architectural decisions, database schema migrations, and updates to the Discord AI Personal Assistant project.

---

## 💎 THE 4 PILLARS OF WORKSPACE INTEGRITY

1. **Unified Context and Vector Logs**:
   * Chat logs and vector memories must reside in the same physical row to ensure transaction consistency, zero memory duplication, and fast indexing.
2. **Anti-Hallucination & Model Size Awareness**:
   * Small models (under 4B) are sensitive to heavy system instructions. We prioritize context pruning (Lean Mode) and image downscaling over generic instruction inputs.
3. **Studio Audio Quality (Audiophile Voice)**:
   * The AI's spoken responses must sound polished. We apply digital mastering (gates, high-pass, compression, dithered tail reverb) locally on the host CPU/GPU.
4. **Clean RAM Buffer Tracking**:
   * The live RAM buffer must remain synced between text messages and transcribed voice inputs, preventing the model from ignoring voice turns or treating them as isolated contexts.

---

## 🛠️ ARCHITECTURAL DECISIONS & HISTORICAL CHANGELOG

### May 02, 2026 — The Grand Architecture Rework
* **WHY**: ChromaDB memory storage and MySQL chat logging were running out of sync and consuming unnecessary RAM. Smaller models like Qwen-4B suffered from "Attention Dilution" due to excessively verbose system instructions. Voice messages were also invisible to the dynamic context buffer.
* **HOW**:
  * **Unified Database**: Dropped the legacy `vector_memories` table. Added an `embedding vector(768)` column directly to the `messages` table in PostgreSQL. Setup HNSW indexing for rapid cosine similarity lookups.
  * **Dynamic Lean Mode**: Implemented a tiered system prompt builder in `session_manager.py` that strips guidelines and security structures for models with context sizes ≤ 4096 tokens, saving ~400 tokens per call.
  * **RAM Buffer Backfilling**: Modified `main.py` to skip audio attachments in `on_message` (since their content is empty initially), transcribing them with Whisper in `process_ai_request`, and then backfilling the transcribed text directly into the dynamic context buffer.
  * **Speaker Attribution & Semantic Cleaning**: Appended speaker names to embeddings (e.g. `User Name said: content`) and stripped the `[Voice Transcribed]:` prefix from strings before vectorization.
* **DO NOT**: Never separate the message database and vector database.
* **RISK**: High-resolution image uploads can still trigger out-of-memory errors on small visual models. Mitigated by applying image resizing boundaries.

### April 20, 2026 — Studio-Grade Speech (Kokoro-82M & Pedalboard)
* **WHY**: Raw TTS outputs (like Piper fallback) sounded dry, robotic, or cut off abruptly.
* **HOW**:
  * Integrated the **Kokoro-82M** TTS engine for high-fidelity speech synthesis.
  * Integrated **Pedalboard** mastering chain: high-pass filters to remove low-end rumble, dynamic range compression, and dithered room reverb to prevent abrupt audio tail clipping.
  * Preserved Piper TTS as a lightweight fallback, resolving a Type Error issue by removing the unneeded `length_scale` keyword argument from its synthesize calls.

### April 13, 2026 — Local Whisper STT Integration
* **WHY**: To enable voice-to-voice interaction without relying on heavy cloud APIs or leaking conversation audio outside the host computer.
* **HOW**:
  * Integrated local **Faster-Whisper** parsing for local Discord voice note transcription.

### April 05, 2026 — Initial Release
* **WHY**: Initial establishment of the local Ollama Discord Assistant.
* **HOW**:
  * Seeded the basic Discord bot listener, command handlers, and default system prompt configs.

---

### June 11, 2026 — GPT-SoVITS Process Unification & Active Scrolling Context
* **WHY**: Spawning voice engines in separate terminal windows was error-prone and caused process leaks. Additionally, loading fixed message sizes (e.g., 24 messages) in the history context caused attention dilution and high processing latency on small models (SLMs) with narrow 4K context bounds.
* **HOW**:
  * **GPT-SoVITS Subprocess Management**: Integrated async process spawning (`asyncio.create_subprocess_exec`) inside `main.py` setup hooks to launch `api_v2.py` from the voice engine root directory, routing output and cleaning log noise into the main console. Wired termination hooks inside bot `close()`.
  * **V2 Audio Integration**: Added `/tts` API endpoint calling for zero-shot cloning with relative sibling references (`../AI-Vtuber/voice_ref/...`) to ensure zero absolute path disclosure. Applied Pedalboard dynamic mastering filters to generated voice bytes.
  * **Active Scrolling Window Context**: Refactored `session_manager.py` memory block creation to calculate text length dynamically, scrolling backward from the newest message until reaching a strict character budget (e.g. 1500 characters for `lean` mode), flat-lining token consumption at a predictable footprint.
  * **Plug-and-Play Fallback**: Programmed `audio_manager.py` to automatically fallback to native Kokoro/Piper if the GPT-SoVITS server is offline or not installed, dynamically resampling all audio arrays (Kokoro at 24k, Piper at 22.05k, CPUFast at 32k, and GPU at 48k) to a unified **48000 Hz** target, preventing pitch mismatch bugs (slow/deep male voices) and ensuring seamless playback on Discord's 48kHz audio gateway.
  * **Pedalboard Mastering Control**: Configured `audio_manager.py` to bypass Pedalboard studio mastering for successful GPT-SoVITS voice synthesis to prevent signal distortion on premium cloned voices (while keeping mastering active for native Kokoro/Piper fallbacks).
  * **Dynamic precision toggle & isolated GPU Env**: Spawns the GPU engine with isolated `GPT-SoVITS/sovits-gpu-env` Python interpreter (with dynamic runtime updates to `tts_infer.yaml` configuring `is_half = True` for half precision).
  * **Local Embeddings**: Set default `EMBEDDING_ENGINE` to local Ollama (`nomic-embed-text`) to eliminate external HuggingFace connection 401 warnings on fresh setups.
  * **Dynamic RAG Gate & Memory Honesty Protocol**: Developed `rag_policy.py` to classify user inputs into tiers (`RAG_NONE` for casual/meaningless text, `RAG_LIGHT` for continuity fallback/ambiguous inputs, and `RAG_FULL` for explicit memory queries). Integrated dynamic token budgeting (NONE=0, LIGHT=1 memory, FULL=3 memories). Implemented an **Absent Memory Guardrail** that injects strict prompts when memories are missing, instructing the model not to invent prior details and to ask the user for clarification.
  * **Markdown Cleanup for TTS**: Enhanced `audio_manager.py` text pre-processing to strip markdown symbols (`*`, `**`, `_`, `~`, `` ` ``, `#`, `>`, `-`) prior to speech synthesis, preventing vocal distortion or pause anomalies while keeping original intonation punctuation intact.
* **DO NOT**: Avoid hardcoding absolute directory structures. Keep paths fully relative and configured.
* **RISK**: High-latency inference could occur if GPT-SoVITS server takes time to load model weights on startup. Mitigated by adding a 5-second warmup sleep during process initialization.

---

## 🏁 PRE-MERGE CHECKLIST
Before committing or deploying code, verify:
- [x] Pytest or manual testing runs without syntax/compilation errors.
- [x] No absolute directory paths exist in configuration parameters or code files.
- [x] Temporary files created in `temp_audio/` are correctly deleted in `finally` blocks.
- [x] PostgreSQL table changes are reflected in `schema.sql` and `setup_db.py`.
- [x] All embeddings continue to use 768 dimensions (`nomic-embed-text` standard).
