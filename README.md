# Discord AI Personal Assistant (Sentient Multipurpose Agent)

An elite, sentient-inspired Discord bot powered by **Ollama** for local AI inference. Built for high privacy, cross-server memory synchronization, and proactive human-like interactions.

> **Status:** 🚧 **W.I.P (Work In Progress)**
> **Latest Update:** April 20, 2026 (Audiophile Voice Intelligence Update)

---

## 🚀 Key Sentient Features

### 🎙️ Native Audio Intelligence (STT & TTS)
The AI runs **100% locally** on your hardware, preserving VRAM for the LLM while delivering studio-grade audio.

* **Speech-to-Text (STT)**: Powered by **Faster-Whisper**. Processes Discord voice notes into text instantly.
* **Text-to-Speech (TTS)**: Dual-engine support featuring **Kokoro-82M** (high-fidelity) and **Piper TTS** (performance).
* **Studio Mastering Chain**: Integrates **Pedalboard** for professional post-processing. Features include:
    * **Dithered Tail Recovery**: Prevents reverb cut-offs for a natural finish.
    * **Dynamic Range Compression**: Ensures whispers and high-pitch responses are crisp and audible.
    * **Binaural Reverb**: Creates an intimate, non-robotic studio vocal profile.

### 🧠 Episodic Long-Term Memory (RAG)
Powered by **ChromaDB**. The AI recalls past interactions using semantic vector search. It maintains context from previous weeks without manual reminders, creating a continuous "shared history" with the user.

### 🎭 Realistic Interaction Logic
* **Burst Typing Mode**: Simulates human messaging by sending responses in rapid-fire short bursts.
* **Hybrid Parsing**: Supports emotional tags like `[laugh]`, `[hmm]`, or `[hum:up]` to inject real human audio assets or musical hums into synthesized speech.
* **Command Control**: Includes `/tts` for direct voice generation, bypassing the AI brain for testing and utility.

### 🕒 Proactive AFK & Room Awareness
* **Dynamic AFK Pings**: AI proactively reaches out during silences.
* **Smart Reminders**: NLP parsing handles intents like "remind me in 10 mins" or "wake me up tomorrow" naturally.

---

## 🛠 Prerequisites

* **Python 3.10+** (Python 3.14 compatible)
* **Ollama** (Gemma 4 / Llama 3 recommended)
* **MySQL Server** (Via Laragon/XAMPP)
* **ChromaDB** (Local Vector Storage)
* **FFmpeg** (Required for Audio/Voice features)

## 📦 Quick Installation

1.  **Clone & Enter**
    ```sh
    git clone [https://github.com/SapiOwO/Discord-AI-Personal-Assistant.git](https://github.com/SapiOwO/Discord-AI-Personal-Assistant.git)
    cd Discord-AI-Personal-Assistant
    ```

2.  **Environment Setup**
    ```sh
    python -m venv bot-env
    # Windows: bot-env\Scripts\activate
    pip install -r requirements.txt
    ```

3.  **Configuration**
    * Rename `.env.example` to `.env` and fill in your Discord Token and Database credentials.
    * Rename `config.py_example` to `config.py` to customize the AI persona and audio settings.

4.  **Database Setup**
    * Import `schema.sql` to your MySQL instance. The bot handles dynamic setting table verification on boot.

5.  **Run**
    ```sh
    python main.py
    ```

---

## 📄 License
Licensed under the GNU GPLv3 License. Built for the AI Community.