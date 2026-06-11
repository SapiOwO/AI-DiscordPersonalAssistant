# Case Study — Context Engineering & Memory Optimization (SLM Edge AI)

This document presents a technical case study detailing the memory architecture transitions, context engineering strategies, and local-first performance optimizations implemented in the `AI-Discord` bot. This case study highlights how a consumer-grade system can run stable, low-latency, and highly contextual personal assistants under a strict 4K token constraint.

---

## 💎 1. The Core Challenge: The Context Bloat Problem

Early iterations of the Discord AI assistant suffered from **Attention Dilution**, high response latencies, and frequent hallucinations when using Small Language Models (SLMs) such as Qwen-4B or `gemma3:1b-it-qat`. 

The primary cause was **Context Bloat**:
* Feeding raw channel names, channel biographies, user display names, absolute timestamps, and server metadata blindly on every query.
* Packing standard conversation history (e.g. 24 turns of 520 characters each) blindly into the prompt, consuming up to ~3,100 tokens out of a maximum 4,096 tokens.
* Letting tool outputs (such as massive web search results or full database scans) flood the system prompt.
* Relying on a fragmented MySQL + ChromaDB split-database architecture, which caused synchronization lag, duplicate data paths, and high VRAM overhead on local nodes.

---

## 🔄 2. The Architectural Evolutions

To build a high-performance local AI companion, we executed three primary architectural shifts:

### A. Unified Database Schema (PostgreSQL + pgvector)
* **Old Way**: SQLite/MySQL for message logging, paired with ChromaDB for vector memory. This split caused database drift, duplicate vector memory blocks, and elevated RAM usage.
* **New Way**: A unified PostgreSQL database using the `pgvector` extension with an **HNSW (Hierarchical Navigable Small World)** index. The raw text and its 768-dimensional embedding share the exact same physical row in the `messages` table.
* **Result**: Zero data drift, reduced database transaction complexity, and sub-millisecond similarity lookups.

```sql
-- Unified Row Schema
CREATE TABLE IF NOT EXISTS messages (
    id BIGSERIAL PRIMARY KEY,
    bot_id BIGINT NOT NULL,
    channel_id BIGINT NOT NULL,
    username VARCHAR(255),
    role VARCHAR(20) CHECK (role IN ('system', 'user', 'assistant')),
    content TEXT,
    embedding vector(768),  -- nomic-embed-text dimensions
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### B. Active Scrolling Window Context
* **Old Way**: Feeding a fixed count of past messages (e.g. 24 turns). This would frequently hit the model's 4K token ceiling, prompting Ollama to discard system instructions, which led to hallucinations.
* **New Way**: A budget-aware, reverse-chronological scrolling compiler.
  * In **Lean Mode**, the total history character count is capped at **1,500 characters** (~375 tokens).
  * The compiler loops backward from the newest message, accumulating turns until the budget is saturated.
  * If older history was excluded, a `...` indicator is prepended to represent context truncation.
* **Result**: The history footprint stays flat and predictable, keeping processing latencies low and protecting system directives.

### C. Hardcoded Tool Context Budgets (Context-Aware Allocation)
* **Philosophy**: Do not let the AI choose or retrieve arbitrary amounts of context. The backend must enforce hard, non-negotiable budgets on every tool input and output.
* **Implementation**:
  * **RAG / Memory Tool**: Budgets are limited to `max_memory_chars = 1400` (~350 tokens).
  * **Web Search Tool**: Capped at **3 results** and **280 characters** per result snippet.
  * **Vision Tool**: Compresses and scales images dynamically down to **480p** (in Lean Mode) or **720p** (in Standard Mode).
  * **Metadata Allocation**: Metadata is treated as a selective block with a capped budget of **200–400 characters**, preventing system variables from overwhelming the prompt.

---

## 🧠 3. Hybrid Memory Retrieval: The "5 Days Ago" Temporal Challenge

A common limitation of pure Vector/Semantic search is that semantic similarity calculations (e.g. cosine distance) struggle with precise temporal requests. If a user asks: *"What did my chat 5 days ago contain?"*, a pure vector search for "5 days ago" will return results containing the semantic words "5 days ago" rather than messages actually created on that calendar date.

To solve this, we implemented **Hybrid Memory Retrieval**:

```mermaid
graph TD
    User([User Prompt: 'Chat 5 days ago']) --> Parser{Temporal Parser}
    
    Parser -->|Temporal Intent Detected| RelDate[1. Compute target absolute date]
    Parser -->|Semantic Intent Detected| VecSearch[2. Calculate cosine similarity]
    
    RelDate --> SQLQuery[PostgreSQL Filter: created_at BETWEEN start AND end]
    SQLQuery --> PromptCompiler[Prompt Compiler]
    VecSearch --> PromptCompiler
    
    PromptCompiler --> SLM[SLM Inference (4K Window)]
```

### Flow Control:
1. **Temporal Filtering**: The backend detects relative time references (e.g., "yesterday," "5 days ago").
2. **Metadata Lookup**: It queries PostgreSQL directly using precise timestamp ranges (`WHERE created_at BETWEEN start_of_day AND end_of_day`).
3. **Semantic Hybrid Integration**: If a topic is specified (e.g., *"What did we talk about regarding model models 5 days ago?"*), it overlays a pgvector search filtered by that date range.
4. **Context Assembly**: The parsed database records are summarized and fed to the active scrolling context, preserving memory integrity without flooding the short-term window.

---

## 📈 4. Architectural Summary

| Memory Tier | Storage / Layer | Purpose | Context Budget |
| :--- | :--- | :--- | :--- |
| **Short-Term Context** | Memory / `deque` RAM Buffer | Immediate conversation flow | Capped strictly at 1,500 chars (Lean Mode) |
| **Long-Term Memory** | PostgreSQL Raw Logs | Precise temporal filtering & history metadata | Queried selectively (WHERE constraints) |
| **Semantic Recall** | pgvector HNSW Index | Meaning similarity & topic association | Capped strictly at 1,400 chars |
| **Tool Inputs** | API Controllers | Search and vision constraints | Capped strictly at source (e.g. 480p, 3 results) |

By implementing this **Context Allocation & Allocation Framework**, the bot delivers a highly personalized, contextual experience with rich long-term recall, while running smoothly on lightweight local models on standard consumer hardware.
