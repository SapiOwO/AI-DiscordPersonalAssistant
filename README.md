# Discord AI Personal Assistant (Sentient Multipurpose Agent)

An elite, sentient-inspired Discord bot powered by **Ollama** for local AI inference. Designed for users who demand high privacy, cross-server memory synchronization, and proactive human-like interactions.

> **Status:** 🚧 **W.I.P (Work In Progress)** - Active Development
> **Latest Update:** April 13, 2026

## 🚀 Key Sentient Features

### 🧠 Episodic Long-Term Memory (RAG)

Powered by **ChromaDB**. The AI doesn't just read the current chat; it recalls past interactions from weeks or months ago using semantic vector search. It remembers your preferences, hobbies, and past specs without needing to be reminded.

### 🎭 Sentient-Like Interaction

- **Burst Typing Mode**: Simulates human messaging patterns by breaking long responses into rapid-fire, short messages.
- **Presence Automation**: Automatically switches to **Idle (🌙)** status when inactive and wakes up to **Online (🟢)** or **Streaming (🟣)** when engaged.

### 🕒 Proactive AFK & Room Awareness

- **Dynamic AFK Pings**: AI proactively reaches out if you go silent.
- **Room Awareness**: The AI distinguishes between a solo conversation (where it pings you directly) and a group hangout (where it makes general remarks to the room without tagging anyone).
- **Smart Reminders**: Deterministic NLP parsing to handle "brb", "wait 10 mins", or "wake me up at 8 AM" with high precision.

### 🌌 Omnipresent Logic

Synchronized memory architecture for Owners. Whether you are in a private DM or a shared server, the AI maintains a consistent persona and knowledge base of who you are.

---

## 🛠 Prerequisites

- **Python 3.10+**
- **Ollama** (Gemma 4 / Llama 3 recommended)
- **MySQL Server** (Running via Laragon/XAMPP)
- **ChromaDB** (Local Vector Storage)
- **FFmpeg** (For Music & Audio processing)

## 📦 Quick Installation

1. **Clone & Enter**

   ```sh
   git clone [https://github.com/SapiOwO/Discord-AI-Personal-Assistant.git](https://github.com/SapiOwO/Discord-AI-Personal-Assistant.git)
   cd Discord-AI-Personal-Assistant
   ```

2. **Environment Setup**

   ```sh
   python -m venv bot-env
   # Activate: bot-env\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Database**
   Import `schema.sql` to MySQL. The bot will automatically handle `dynamic_settings` table creation on first run.

4. **Run**

   ```sh
   python main.py
   ```

## 📄 License

Licensed under the GNU GPLv3 License. Built with ❤️ for the AI Community.
