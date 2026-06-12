# Discord AI Personal Assistant — Documentation

This directory contains the core specifications, architecture guides, security boundaries, and development journals for the `AI-Discord` project.

---

## 📚 READ ORDER & DOCUMENT INDEX

To maintain architectural stability, database consistency, and prevent performance regressions (especially for smaller models like Qwen-4B), all developers and AI assistants must refer to these documents in the following order:

### 1. [ARCHITECTURE.md](ARCHITECTURE.md)
* **Core Technical Design**: Details the PostgreSQL + pgvector database schema, the dynamic "Lean Mode" system prompt compiler, the studio audio and TTS/STT pipelines, and the image resizing budgets.

### 2. [AI_ASSISTANT_RULES.md](AI_ASSISTANT_RULES.md)
* **AI Coding Assistant Rules**: Outlines strict coding limits, anti-hallucination protocols for small models, safety bounds, and constraints on third-party libraries and local loopbacks.

### 3. [UPDATE.md](UPDATE.md)
* **Changelog & Validation Checklist**: Houses the timeline of critical design decisions, major updates, and the final *Pre-Merge Verification Checklist* to complete before starting or committing code.

### 4. [HANDOFF_STATUS.md](HANDOFF_STATUS.md)
* **Current Handoff State**: Summary of current implementation details, key file structures, planned future tasks (like sliding window scrolling context & LTS), and operational rules for the next AI assistant.

### 5. [CODEBASE_REVIEW.md](CODEBASE_REVIEW.md)
* **Codebase Reference & Review Guide**: Detailed file-by-file analysis of the bot's codebase, explaining exactly **why** and **how** every module (such as main.py context buffering, CPU embeddings, and Pedalboard audio mastering) is implemented.

### 6. [CASE_STUDY_CONTEXT_ENGINEERING.md](CASE_STUDY_CONTEXT_ENGINEERING.md)
* **Case Study — Context Engineering & Memory Optimization**: Comprehensive engineering case study documenting the transition to PostgreSQL + pgvector, active scrolling window context, hardcoded tool budgets, and hybrid temporal retrieval strategies for portfolio presentation.
