# Discord AI Personal Assistant (Sentient Agent)

An elite, Discord assistant powered by **Ollama** for local AI inference. This agent is designed for native audio intelligence, long-term semantic memory, and proactive human-like engagement.

### 🕒 Latest Updates
* **April 20, 2026**: Integrated **Kokoro-82M** for studio-grade TTS. Added **Dithered Tail Recovery** and **Audiophile Mastering** via Pedalboard. Refactored configuration into a modular `config.py` system.
* **April 13, 2026**: Implemented **Faster-Whisper** for local STT and **ChromaDB** for episodic long-term memory.
* **April 05, 2026**: Initial release with **Ollama** integration and MySQL conversation logging.

---

## 🚀 Key Features

### 🎙️ Native Audiophile Intelligence
The AI features local "ears" and a "voice," running entirely on your CPU to keep VRAM free for the LLM.
* **Speech-to-Text (STT)**: Uses **Faster-Whisper** to transcribe Discord voice notes instantly.
* **Text-to-Speech (TTS)**: Features a dual-engine setup with **Kokoro-82M** (high-fidelity) and **Piper TTS** (high-performance).
* **Studio Mastering**: A built-in **Pedalboard** chain applies dynamic range compression and dithered reverb to ensure every response sounds like a professional broadcast.

### 🧠 Episodic Long-Term Memory (RAG)
Powered by **ChromaDB**. The AI utilizes semantic vector search to recall past interactions from weeks or months ago. It understands your preferences and context without needing repeat instructions.

### 🎭 Realistic Human Interaction
* **Burst Mode**: Simulates natural human messaging by splitting long responses into rapid-fire, concise bursts.
* **Hybrid Emotional Tags**: Recognizes tags like `[laugh]` or `[hmm]` to inject real human audio assets or mathematical pitch-shifted hums into synthesized speech.
* **Markdown Sanitization**: Automatically strips Markdown symbols during speech synthesis to prevent the AI from "reading" formatting characters.

### 🕒 Proactive AFK & Room Awareness
* **Dynamic AFK Pings**: Proactively reaches out if the conversation goes silent for too long.
* **NLP Reminders**: Intelligently parses intents like "remind me in 10 mins" or "wake me up later" to schedule automated follow-ups.

---

## 🛠 Prerequisites

* **Python 3.12** (Strictly recommended for stability)
* **Ollama** (Gemma 4 or Llama 3 models)
* **MySQL Server** (Laragon or XAMPP)
* **ChromaDB**
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
    python -m venv bot-env
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
    * Rename `.env.example` to `.env` and provide your Discord Token and Database credentials.
    * Customize AI behavior and audio settings in `config.py`.

5.  **Database Migration**
    Import `schema.sql` into your MySQL instance. The bot will automatically verify and manage the `dynamic_settings` table on startup.

6.  **Run**
    ```sh
    python main.py
    ```

---

## 📄 License
Licensed under the GNU GPLv3 License. Built for the AI developer community.