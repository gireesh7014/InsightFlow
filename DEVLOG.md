# DEVLOG — InsightFlow Build Decisions

> Recording every technical decision for interview prep. Each entry answers: "Walk me through a technical decision you made."

---

## Day 1 — Project Setup & Architecture

**What I built:** Project skeleton — FastAPI backend, Next.js frontend, SQLite database.

**Decision: SQLite over PostgreSQL for Week 1.**  
PostgreSQL needs installation, configuration, and a running server. SQLite is a single file — zero setup. This let me write actual features instead of debugging database connections on Day 1. I'll upgrade to PostgreSQL in Week 4 when I need pgvector for embeddings.

**Decision: FastAPI over Flask.**  
Flask is simpler but FastAPI gives me: auto-generated Swagger docs (huge for testing), built-in request validation with Pydantic, and async support for later. The 30 minutes of extra learning pays off immediately when I can test my API without writing a single line of frontend code.

**Decision: Rule engine before ML.**  
I wrote 20 hardcoded insight rules (missing data checks, correlation detection, skewness alerts) before touching any ML. Why? Rules are: (1) explainable — I can tell an interviewer exactly why each rule exists, (2) fast — no model loading or inference time, (3) reliable — no randomness. The rule engine alone makes the project look intelligent. ML adds depth in Week 3, but the rules are the foundation.

**Decision: Server-side charts (matplotlib) + Client-side charts (Recharts).**  
Statistical plots like correlation heatmaps and KDE curves look much better in matplotlib/seaborn. But they're static images. For interactive exploration (hovering to see values, selecting different columns), Recharts on the frontend is better. Using both gives the best of both worlds.

**What failed:** Nothing major today — but I almost fell into the overengineering trap. Considered adding Docker + Redis + JWT before I had a working endpoint. Caught myself and cut scope. Ship first, optimize later.

**What I'd do differently:** I'd start with the sample CSV before writing any code. Understanding your data first helps you write better rules.

---
