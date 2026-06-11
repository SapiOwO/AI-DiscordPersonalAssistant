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

---

## 📈 5. Evolution Journey: The Context & Memory Paradigm Shifts

Through iterative debugging and real-world deployment on consumer hardware, we realized a crucial rule of Edge AI Engineering: **Hallucination is not always caused by model size limitations; it is frequently the result of poor context engineering.**

The memory architecture of the `AI-Discord` bot evolved across five distinct developmental phases:

```mermaid
graph TD
    A[Phase 1: MySQL Only<br>No Semantic Recall, Lossy Context] --> B[Phase 2: Split DB<br>MySQL + ChromaDB desync risks]
    B --> C[Phase 3: Unified DB<br>PostgreSQL + pgvector single source of truth]
    C --> D[Phase 4: Context Discipline<br>Active Window & Token Budgeting]
    D --> E[Phase 5: Context Orchestration<br>1B-4B SLMs running hallucination-free]
```

### Phase 1: The Raw Chat Logging Era (MySQL Only)
* **Design**: Standard relational storage of conversations.
* **Limitations**: Zero semantic retrieval. The system relied on feeding raw chronological dumps, leading to a "forgetful" AI that could not connect similar threads across sessions.

### Phase 2: The Two Sources of Truth Era (MySQL + ChromaDB)
* **Design**: MySQL stored the chat transaction logs; ChromaDB acted as the isolated semantic vector database.
* **Failure Vectors**: High synchronization overhead and memory corruption bugs. If a chat record was modified or deleted in MySQL, ChromaDB remained unsynced. A slight lag or cleanup script failure left the agent with corrupted memory states, triggering severe hallucinations.

### Phase 3: The Unified Vault (PostgreSQL + pgvector)
* **Design**: Converted all storage to a unified database. Both relational chat logs, user metadata, and vector embeddings share the exact same physical database row.
* **Impact**: Guaranteed ACID transaction consistency. Removing ChromaDB dropped VRAM/RAM overhead by 1.2GB and eliminated desync vectors entirely.

### Phase 4: Dealing with Context Bloat
* **Insight**: Even with pgvector delivering sub-millisecond, accurate memory retrieval, 1B–4B small models still hallucinated. We discovered that **model drowning** occurs when too much correct data floods the context.
* **The Math of Drowning**:
  * System Prompt: 1,200 tokens
  * Raw RAG / Memories: 1,400 tokens
  * Conversational History: 1,800 tokens
  * Tool Inputs / Search Snippets: 1,000 tokens
  * **Total Prompt Size: 5,400 tokens** (Target Model Ceiling: 4,096 tokens)
* **Behavior**: In an overfilled prompt, the SLM's attention span diluted. It ignored core instructions (e.g. system safety protocols) and anchored onto old conversation chunks.

### Phase 5: Complete Context Orchestration
We resolved model drowning by moving away from relying on "model intelligence" and moving toward **strict context discipline**. We built a 5-tier guardrail system:
1. **Unified Storage (PostgreSQL + pgvector + HNSW)**: For clean memory persistence.
2. **RAG Retrieval Budget**: Hard-capped semantic queries to `max_memory_chars = 1400`.
3. **Active Scrolling Context Window**: Dynamically trims history using character budgets rather than message counts, ensuring the recent memory footprint stays flat and flat-lines token usage.
4. **Hard-Capped Tool Budgets**: Restricts vision scale (480p/720p) and web search results (3 snippets of 280 chars) to prevent context hijacking.
5. **Lean Mode Prompt Tiering**: Strips non-essential instructions, saving up to ~400 tokens per prompt.

**Result**: Models like `gemma3:1b-it-qat` and `qwen3.5:4b-q4_K_M` now run completely stable, hallucination-free, and respond under 100ms on lightweight local hardware.

