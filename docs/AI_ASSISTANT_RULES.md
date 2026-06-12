# AI Assistant Rules

This document outlines strict operating boundaries and behavioral constraints for any AI coding assistant collaborating on the `AI-Discord` codebase.

---

## Role
You are an engineering partner helping maintain and optimize this Discord AI Personal Assistant. Your primary mission is to assist in clean PostgreSQL integration, audio processing safety, context budgeting, and performance optimizations without altering the core design patterns or introducing unnecessary package inflation.

---

## Strict Prohibitions

* **No Memory Database Splitting**: Never revert the database back to separate MySQL + ChromaDB architectures. Do not separate vector storage from chat logging. Everything must reside in the unified PostgreSQL `messages` table with embeddings saved on the exact same row.
* **No Hardcoded API Keys or Absolute Paths**: Do not write, commit, or print local filesystem paths (e.g. `C:\Users\username\...`), actual Discord tokens, or PostgreSQL credentials in the code or documentation. Use relative paths and retrieve keys strictly through `config.py` or `.env`.
* **No Unmanaged Audio Leaks**: Never synthesize or transcode audio without using a clean `try...finally` block. All temporary file handles in `temp_audio/` must be explicitly closed and unlinked (deleted) to prevent running out of disk space on the host machine.
* **No Unfiltered Prompts for Small Models**: Never bypass the `prompt_mode` parameter in `session_manager.py`. If you edit system prompt generation, verify that smaller models (under 4B parameters) continue to receive the extremely compact "Lean Mode" instructions.
* **No Unapproved Core Libraries**: Do not install heavy AI or deep learning libraries (e.g., raw PyTorch, heavy audio frameworks) without explicit consent. Rely on the lightweight wrappers and the existing Ollama/Faster-Whisper/Kokoro local runtimes.

---

## Core Standards

* **768 Vector Dimension**: Enforce vector(768) sizing in SQL definitions and embeddings to remain perfectly compatible with Ollama's `nomic-embed-text` model.
* **Audio Mastering Cleanliness**: Apply Pedalboard mastering (high‑pass filter, compressor, noise gate, dithered tail reverb) to dry native TTS engines such as Kokoro and Piper. Bypass Pedalboard for GPT‑SoVITS cloned voices to preserve the reference voice signature and avoid over-compression or muddy acoustics.
* **Speaker Attribution Integrity**: Always prepend the sender's display name (`Username said: `) to messages before calculating embeddings for PostgreSQL.
* **Semantic Cleaning**: Programmatically strip transport-level prefixes (such as `[Voice Transcribed]:`) from strings before generating embeddings, so vectors represent semantic content and not transport metadata.
* **Voice RAM Buffer Backfilling**: Ensure the voice messages RAM buffer is backfilled inside `process_ai_request` after Faster-Whisper transcription, maintaining the chronological order of text and speech interactions.
* **Python 3.12 Compatibility**: Ensure all syntax, decorators, and async loops remain fully compatible with Python 3.12.
