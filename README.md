# Discord AI Personal Assistant (Sentient Agent)

An elite, Discord assistant powered by **Ollama** for local AI inference. This agent is designed for native audio intelligence, unified long-term semantic memory, and proactive human-like engagement. 

Optimized for both high-end rigs and "potato PCs", it allows small models (like Qwen-4B) to perform complex tasks without hallucinations.

### 🕒 Latest Updates
* **May 02, 2026**: **The Grand Architecture Rework**. Migrated entirely from MySQL + ChromaDB to a unified **PostgreSQL + pgvector** database. Introduced **"Lean Mode"** context feeding and Anti-Hallucination truncation to make small LLMs (<4B) incredibly stable and focused. Voice messages are now normalized in the RAG pipeline with proper speaker attribution.
* **April 20, 2026**: Integrated **Kokoro-82M** for studio-grade TTS. Added **Dithered Tail Recovery** and **Audiophile Mastering** via Pedalboard. 
* **April 13, 2026**: Implemented **Faster-Whisper** for local STT.
* **April 05, 2026**: Initial release with **Ollama** integration.

---

## 🚀 Key Features

### 🧠 Unified Episodic Memory (RAG via pgvector)
Powered by **PostgreSQL and pgvector (HNSW Indexing)**. The AI utilizes lightning-fast semantic vector search to recall past interactions from weeks or months ago. 
* **Single Source of Truth**: Chat logs and semantic embeddings share the exact same database row, drastically reducing RAM usage and eliminating desync issues.
* **Speaker Attribution**: Voice notes and texts are directly attributed to your display name, allowing the AI to flawlessly remember *who* said *what*.

### ⚡ Small Model Optimization (Anti-Hallucination)
* **Dynamic Lean Mode**: Automatically strips away heavy, verbose system instructions when using smaller context windows, preventing "Attention Dilution" in 4B-8B models.
* **Assistant Truncation**: Prevents "Context Anchoring" by dynamically shortening the AI's own past verbose responses in the context window.
* **Focused Vision Processing**: Vision caching is optimized so the AI only evaluates images precisely when they are uploaded, avoiding visual context hijacking.

### 🎙️ Native Audiophile Intelligence
The AI features local "ears" and a "voice," running entirely on your CPU/GPU to keep VRAM balanced.
* **Speech-to-Text (STT)**: Uses **Faster-Whisper** to transcribe Discord voice notes instantly.
* **Text-to-Speech (TTS)**: Features a dual-engine setup with **Kokoro-82M** (high-fidelity) and **Piper TTS** (high-performance).
* **Studio Mastering**: A built-in **Pedalboard** chain applies dynamic range compression and dithered reverb to ensure every response sounds like a professional broadcast.

### 🎭 Realistic Human Interaction
* **Burst Mode**: Simulates natural human messaging by splitting long responses into rapid-fire, concise bursts.
* **Hybrid Emotional Tags**: Recognizes tags like `[laugh]` or `[hmm]` to inject real human audio assets or mathematical pitch-shifted hums into synthesized speech.

### 🕒 Proactive AFK & Room Awareness
* **Dynamic AFK Pings**: Proactively reaches out if the conversation goes silent for too long.
* **NLP Reminders**: Intelligently parses intents like "remind me in 10 mins" to schedule automated follow-ups.

---

## 🛠 Prerequisites

* **Python 3.12** (Strictly recommended for stability)
* **Ollama** (Recommended: `qwen3-vl:4b-instruct` or `gemma:4b` for LLM, and `nomic-embed-text` for embeddings)
* **PostgreSQL 15+** (Must have the `pgvector` extension installed/enabled)
* **FFmpeg** (Required for audio processing)

---

## 📦 Installation

1.  **Clone the Repository**
    ```sh
    git clone [https://github.com/SapiOwO/Discord-AI-Personal-Assistant.git](https://github.com/SapiOwO/Discord-AI-Personal-Assistant.git)
    cd Discord-AI-Personal-Assistant
    ```

2.  **Environment Setup**
    Create a virtual environment using Python 3.12:
    ```sh
    py -3.12 -m venv bot-env
    # Windows:
    bot-env\Scripts\activate
    # Linux/Mac:
    source bot-env/bin/activate
    ```

3.  **Install Dependencies**
    ```sh
    pip install -r requirements.txt
    ```

4.  **Configuration**
    * Rename `.env.example` to `.env`.
    * Provide your Discord Token and PostgreSQL Database credentials.
    * Make sure you pull the embedding model via terminal: `ollama pull nomic-embed-text`.

5.  **Automated Database Setup**
    Run the setup script. It will automatically connect to your PostgreSQL database, enable the `vector` extension, and create all necessary tables and HNSW indexes:
    ```sh
    python setup_db.py
    ```

6.  **Run the Agent**
    ```sh
    python main.py
    ```

---

## 📄 License
Licensed under the GNU GPLv3 License. Built for the AI developer community.