# AI-Discord Bot — AI Handoff Status

This document summarizes the current implementation state, architectural direction, and non-negotiable guidelines for the next AI assistant collaborating on the `AI-Discord` bot.

---

## 1. Product Direction & Scope

The `AI-Discord` bot is a local-first, privacy-respecting personal companion AI. It is designed to run entirely on consumer-grade hardware ("potato PCs" and laptops) without requiring expensive GPU upgrades or compromising user privacy.

### Core Architecture Intent
* **Zero Cloud Costs**: The bot relies entirely on local models run via Ollama (e.g., `qwen3-vl:2b-instruct`, `gemma3:1b-it-qat`) and local audio engines.
* **Unified Database**: Chat logs and semantic embeddings reside in a unified PostgreSQL database using the `pgvector` extension.
* **SLM Optimizations**: Since small language models (≤4B parameters) are highly sensitive to "Attention Dilution," the prompt pipeline uses tiered context budgets ("Lean Mode") to strip instructions and protect context size.
* **Studio-Grade Voice**: The voice pipeline synthesizes audio locally using Kokoro-82M (or Piper fallback) and master-processes it using Pedalboard to sound professional and warm.
* **Dynamic Awareness**: The bot maintains a rolling RAM buffer of recent messages, seamlessly blending text and transcribed voice notes.

---

## 2. Current Bot State & Features

The bot is fully functional on the `dev` branch with the following capabilities:
* **Unified Memory (pgvector)**: The `vector_memories` table has been deprecated. All message history and 768-dimensional embeddings share the exact same row in the `messages` table.
* **CPU Embedding Generation**: Embeddings are computed on the CPU using `sentence-transformers` (`nomic-embed-text-v1.5`) via a lazy-loaded thread pool in `memory_manager.py`. This prevents embedding generation from competing for GPU resources with active LLM inference. An Ollama API fallback is preserved.
* **Keep-Alive Caching**: Ollama calls request a `keep_alive="30m"` configuration, keeping active models cached in memory to eliminate initial response lag.
* **Lean Mode System Prompts**: `session_manager.py` dynamically compiles instructions based on model context limits (`lean`, `standard`, and `full` modes).
* **Audio Mastering Chain**: `audio_manager.py` hosts a professional **Pedalboard** mastering setup (Noise Gate -> High-Pass Filter -> Compressor -> Room Reverb) for warm, natural speech.
* **RAM Context Backfilling**: Transcribed voice notes are backfilled directly into the 5-message context buffer once Faster-Whisper finishes transcribing, preventing the bot from becoming blind to spoken user turns.
* **Image Compression Budget**: Vision models parse images scaled to hard resolution budgets (like 480p or 720p) to keep visual attention clear.

---

## 3. Core File Map

* [main.py](main.py): Discord events loop, message routers, typing burst generator, and dynamic context backfill listeners.
* [db.py](db.py): PostgreSQL pgvector connectivity, conversational logs, profile settings, and HNSW cosine similarity search queries.
* [schema.sql](schema.sql): Table definitions, indexing, and cleanup constraints.
* [session_manager.py](session_manager.py): Tiered prompt assembly (Lean/Standard/Full) and context window packing.
* [memory_manager.py](memory_manager.py): Local CPU sentence-transformers vector generation and fallback handlers.
* [audio_manager.py](audio_manager.py): Local STT (Faster-Whisper), TTS (Kokoro/Piper), and Pedalboard mastering chains.
* [config.py](config.py): Environment settings, default persona card (Zen ChromaQ-Tπ), and features capability flags.

---

## 4. Planned & Future Work (Next Actions)

1. **Active Window Scrolling Context (Sliding Window)**:
   * Improve the sliding window history logic. Rather than just relying on the Lean Mode system prompts, implement an active scrolling context strategy that dynamically trims and summarizes past conversation cycles to maintain maximum clarity in the 4K context window of models like `gemma3:1b-it-qat`.
2. **LTS (Long Term Support) Updates**:
   * Implement library updates, robust error checking, and schema migrations to ensure the bot can run unattended for months without database pool failures or package depreciation.
3. **Benchmarking SLM Capability**:
   * Run benchmark metrics on Qwen-4B and Gemma3-1B to measure the hallucination rate under different context truncation thresholds.

---

## 5. Non-Negotiable Rules for the Next AI

* **Never Split the Database**: Do not separate chat history database and vector memory storage. They must remain unified in the `messages` table on the same row.
* **No Hardcoded Absolute Paths or Keys**: All configuration variables, paths, and API keys must be loaded via `config.py` or `.env`. No absolute local folder paths (e.g. `C:\Users\developer\...`) may be committed.
* **Manage Temp Files**: All audio transformations in `temp_audio/` must occur in `try...finally` blocks to guarantee file unlinking.
* **Ensure Local CPU/GPU Separation**: Keep embedding computations on the CPU (using `sentence-transformers`) to prevent Ollama GPU starvation.
* **Update documentation**: Always record your changes and plans in `docs/UPDATE.md` and keep this handoff status current.
