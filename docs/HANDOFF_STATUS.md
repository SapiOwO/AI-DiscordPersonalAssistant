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
* **CPU Embedding Generation (Fallback)**: Embeddings default to local Ollama `nomic-embed-text` for zero-friction setup. SentenceTransformers CPU inference is available as an optional advanced mode via a lazy-loaded thread pool in `memory_manager.py` to prevent embedding generation from competing for GPU resources with active LLM inference.
* **Keep-Alive Caching**: Ollama calls request a `keep_alive="30m"` configuration, keeping active models cached in memory to eliminate initial response lag.
* **Lean Mode System Prompts**: `session_manager.py` dynamically compiles instructions based on model context limits (`lean`, `standard`, and `full` modes).
* **Audio Mastering Chain**: `audio_manager.py` hosts a professional **Pedalboard** mastering setup (Noise Gate -> High-Pass Filter -> Compressor -> Room Reverb) for warm, natural speech.
* **RAM Context Backfilling**: Transcribed voice notes are backfilled directly into the 5-message context buffer once Faster-Whisper finishes transcribing, preventing the bot from becoming blind to spoken user turns.
* **Image Compression Budget**: Vision models parse images scaled to hard resolution budgets (like 480p or 720p) to keep visual attention clear.

---

## 3. Core File Map

* [main.py](../main.py): Discord events loop, message routers, typing burst generator, and dynamic context backfill listeners.
* [db.py](../db.py): PostgreSQL pgvector connectivity, conversational logs, profile settings, and HNSW cosine similarity search queries.
* [schema.sql](../schema.sql): Table definitions, indexing, and cleanup constraints.
* [session_manager.py](../session_manager.py): Tiered prompt assembly (Lean/Standard/Full) and context window packing.
* [memory_manager.py](../memory_manager.py): Local CPU sentence-transformers vector generation and fallback handlers.
* [audio_manager.py](../audio_manager.py): Local STT (Faster-Whisper), TTS (Kokoro/Piper), and Pedalboard mastering chains.
* [config.py](../config.py): Environment settings, default persona card (Zen ChromaQ-Tπ), and features capability flags.

---

## 4. Completed Features

1. **Active Scrolling Window Context**:
   * Implemented in `session_manager.py` to maintain a flat, budget‑aware context window, eliminating hallucination risk for small‑model (SLM) deployments and improving relevance for larger LLMs.
   * The system trims older turns until the configured character budget (`max_chars_total`) is reached, inserting an ellipsis (`...`) when truncation occurs.
   * This feature is now **live** on the `dev` branch and marked as implemented in the handoff status.

2. **Lean Mode Prompt Builder**:
   * Tiered system prompts (`lean`, `standard`, `full`) reduce token overhead for models with ≤4K context windows.
   * Strips verbose guidelines, keeping only essential persona and safety rules, saving ~400 tokens per call.

3. **Dynamic RAG Gate & Memory Honesty Protocol**:
   * Evaluates incoming messages using `rag_policy.py` to determine RAG depth: `RAG_NONE` for casual chatter, `RAG_LIGHT` (1 result) for follow-up ambiguity, and `RAG_FULL` (3 results) for explicit memory/project cues.
   * Leverages an **Absent Memory Guardrail** that injects strict prompts (e.g. *"No long-term memory was retrieved..."*) when memories are missing, preventing the model from hallucinating false historical contexts.


---

## 5. Non-Negotiable Rules for the Next AI

* **Never Split the Database**: Do not separate chat history database and vector memory storage. They must remain unified in the `messages` table on the same row.
* **No Hardcoded Absolute Paths or Keys**: All configuration variables, paths, and API keys must be loaded via `config.py` or `.env`. No absolute local folder paths (e.g. `C:\Users\developer\...`) may be committed.
* **Manage Temp Files**: All audio transformations in `temp_audio/` must occur in `try...finally` blocks to guarantee file unlinking.
* **Ensure Local CPU/GPU Separation**: Keep embedding computations on the CPU (using `sentence-transformers` fallback or Ollama config) to prevent active LLM GPU starvation.
* **Update documentation**: Always record your changes and plans in `docs/UPDATE.md` and keep this handoff status current.
