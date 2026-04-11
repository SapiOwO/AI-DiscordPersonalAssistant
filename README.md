# Discord AI Personal Assistant (Multipurpose)

An elite, multi-purpose Discord bot powered by **Ollama** for local AI inference. This bot features sentient-like conversation, cross-server omnipresent memory, image analysis, and music integration.

## 🚀 Features

- **Local AI Inference**: Powered by Ollama (Gemma 4 / Llama 3).
- **Omnipresent Memory**: Cross-server and DM memory synchronization for owners.
- **Multimodal**: Supports Image analysis (Vision) and Audio ingestion.
- **Sentient-like Interaction**: Dynamic typing bursts and AFK awareness.
- **Security**: Strict whitelist-based access and automatic DB garbage collection.
- **Full Multimedia**: Meme captioning, Stable Diffusion, and Music playback.

## 🛠 Prerequisites

- [Python 3.10+](https://www.python.org/)
- [Ollama](https://ollama.com/)
- [MySQL Server](https://www.mysql.com/)
- [FFmpeg](https://ffmpeg.org/download.html) (For Music/Audio)

## 📦 Installation

1. **Clone the Repository**

   ```sh
   git clone [https://github.com/SapiOwO/Discord-AI-Personal-Assistant.git](https://github.com/SapiOwO/Discord-AI-Personal-Assistant.git)
   cd Discord-AI-Personal-Assistant
   ```

2. **Setup Virtual Environment**

   ```sh
   python -m venv bot-env
   # Windows: bot-env\Scripts\activate
   # Linux/Mac: source bot-env/bin/activate
   ```

3. **Install Dependencies**

   ```sh
   pip install -r requirements.txt
   ```

4. **Database Setup**
   Import `schema.sql` to your MySQL server to initialize the required tables.
5. **Configuration**
   Rename `.env.example` to `.env` and fill in your `DISCORD_TOKEN`, `OWNER_IDS`, and `DB_` credentials.

## 🎮 Usage

Run the bot: `python main.py`.

### Key Commands

- `/history`: View recent interaction context.
- `/reset_channel`: Clear AI memory for the current channel.
- `/reset_memory`: Clear personal cross-server memory.
- `/imagine`: Generate AI art via Stable Diffusion.

## 📄 License

Licensed under the GNU GPLv3 License.

```
