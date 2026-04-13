# Discord AI Personal Assistant (Sentient Multipurpose Agent)

An elite, sentient-inspired Discord bot powered by **Ollama** for local AI inference. Designed for high privacy, cross-server memory synchronization, and proactive human-like interactions.

> **Status:** 🚧 **W.I.P (Work In Progress)** - Active Development
> **Latest Update:** April 13, 2026 (Local Audio Intelligence Update)

---

## 🚀 Key Sentient Features

### 🎙️ Native Two-Way Audio (STT & TTS)

The AI now has ears and a voice, running **100% locally** on your CPU to preserve GPU VRAM for LLM inference.

- **Speech-to-Text (STT)**: Powered by **Faster-Whisper**. Send a Voice Note, and the AI will transcribe and understand your voice instantly.
- **Text-to-Speech (TTS)**: Powered by **Piper TTS** with high-fidelity models (`hfc_female`). The AI responds with voice messages, featuring natural prosody and shorthand expansion (e.g., "lol" -> "haha").
- **Voice-Note Integration**: Responds directly with Discord-native Voice Notes for a seamless conversational experience.

### 🧠 Episodic Long-Term Memory (RAG)

Powered by **ChromaDB**. The AI recalls past interactions from weeks or months ago using semantic vector search. It remembers your preferences and past conversations without being reminded.

### 🎭 Sentient-Like Interaction

- **Burst Typing Mode**: Simulates human messaging patterns by breaking long responses into rapid-fire, short messages.
- **Persona Enforcement**: Advanced regex filtering ensures the AI stays in character and doesn't leak internal analytical thoughts.

### 🕒 Proactive AFK & Room Awareness

- **Dynamic AFK Pings**: AI proactively reaches out if you go silent.
- **Smart Reminders**: NLP parsing handles "brb", "wait 10 mins", or "wake me up at 8 AM" with high precision.

---

## 🛠 Prerequisites

- **Python 3.10+** (Python 3.14 compatible)
- **Ollama** (Gemma 4 / Llama 3 recommended)
- **MySQL Server** (Via Laragon/XAMPP)
- **ChromaDB** (Local Vector Storage)
- **FFmpeg** (Crucial for Audio & Voice features)

## 📦 Quick Installation

1. **Clone & Enter**

   ```sh
   git clone [https://github.com/SapiOwO/Discord-AI-Personal-Assistant.git](https://github.com/SapiOwO/Discord-AI-Personal-Assistant.git)
   cd Discord-AI-Personal-Assistant
   ```

2. **Environment Setup**

   ```sh
   python -m venv bot-env
   # Windows: bot-env\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Audio Setup**
   Ensure **FFmpeg** is installed and its path is correctly set in the `.env` file. The bot will automatically download the necessary STT and TTS models on its first run (~150MB total).

4. **Database**
   Import `schema.sql` to MySQL. The bot handles `dynamic_settings` table creation automatically.

5. **Run**

   ```sh
   python main.py
   ```

---

## 📄 License

Licensed under the GNU GPLv3 License. Built with ❤️ for the AI Community.
