# Client & UI Solutions Architecture Guide

This document outlines the optimal client architecture and implementation strategies for building an intuitive, non-technical drag-and-drop reporting interface for non-developer team members and business users.

---

## 1. User Scenario & Core Requirements

* **Primary Persona:** Non-technical user (e.g. account manager, creator coordinator).
* **Input:** Drag-and-drop one or multiple social media screenshots (PNG, JPG, WEBP) or an entire asset folder.
* **Processing Pipeline:**
  ```
  [Screenshots Dropped] 
         ↓
  [Multimodal Vision LLM] (Extracts structured JSON: Views, Reach, Likes, etc.)
         ↓
  [Deterministic Python Engine] (calculate_metrics.py: Audits discrepancies & calculates ER)
         ↓
  [Interactive UI / Report Output] (Markdown preview + PDF/CSV export)
  ```
* **Critical Design Mandate:** **Do NOT let LLMs perform mathematical calculations directly.** LLMs suffer from arithmetic hallucination and rounding errors (e.g. turning `1,225` into `1,100`). The LLM must be used strictly for **Vision Extraction & Narrative Synthesis**, while `calculate_metrics.py` handles 100% of mathematical computation.

---

## 2. Technical Evaluation: Do We Need RAG?

**No, RAG (Retrieval-Augmented Generation) is NOT appropriate for this workflow.**

| Architecture | Why it fits / Why it doesn't |
| :--- | :--- |
| **RAG (Vector DB + Chunking)** | ❌ **Overkill and Counterproductive.** RAG is designed for searching across millions of text tokens in large knowledge bases. For a campaign audit, all context comes from 2–10 specific screenshots provided directly in the request. Chunking screenshots into vector embeddings destroys spatial number relationships and causes OCR errors. |
| **Multimodal Vision + Deterministic Code Pipeline** | ✅ **Optimal Architecture.** Feed images directly to a high-fidelity Vision Language Model (e.g. Gemini 2.0 Flash / Claude 3.5 Sonnet / GPT-4o) with a JSON schema constraint, pipe the JSON into our standard `calculate_metrics.py`, and render the audited Markdown. |

---

## 3. Comparison of Open-Source UI Solutions

### Option A: Streamlit Desktop / Local WebApp (Recommended ⭐⭐⭐⭐⭐)
* **What it is:** A lightweight, pure-Python web UI framework.
* **Architecture:** A single file `clients/streamlit_app.py` (~150 lines) that directly imports `calculate_metrics.py` and calls the Vision LLM API.
* **User Experience:**
  - Drag-and-drop file uploader box (supports multiple files).
  - Thumbnail gallery of uploaded screenshots.
  - Interactive metric summary cards (Total Views, Reach, Lower Bound ER).
  - Live editable Markdown report with "Download Report (.md / .pdf)" buttons.
* **Deployment Options:**
  - **Local One-Click App:** Run via `streamlit run clients/streamlit_app.py` or packaged into a double-clickable macOS desktop `.app` using Platypus or Automator.
  - **Free Cloud WebApp:** Deploy to [Streamlit Community Cloud](https://streamlit.io/cloud) in 1 click connected to your private/public GitHub repo with a password gate.
* **Verdict:** **Best overall balance of simplicity, speed, and zero infrastructure overhead.**

---

### Option B: Dify Workflow (Best for Enterprise & No-Code Teams)
* **What it is:** The leading open-source LLM app development and workflow orchestration platform.
* **Architecture in Dify:**
  1. **Start Node:** Enable "File Upload" (Image type, multiple).
  2. **LLM Node (Vision):** Model: Claude 3.5 Sonnet or Gemini 1.5/2.0 Flash. Prompt: Enforce JSON extraction matching `DATA_MODEL.md`.
  3. **Code Node (Python 3):** Embed the logic of `calculate_metrics.py` directly into Dify's Python execution sandbox to compute deterministic engagement and verify discrepancies.
  4. **Template Transform Node:** Inject audited variables into `REPORT_FORMAT.md`.
  5. **End Node:** Output Markdown report and structured JSON.
* **User Experience:** Dify automatically generates a standalone WebApp URL that can be shared with your teammate or saved as a PWA on their desktop/phone.
* **Pros:** Enterprise RBAC, audit logs, model switching without code changes.
* **Cons:** Requires running Docker Compose with Redis, PostgreSQL, and Celery (~4GB RAM local footprint).

---

### Option C: Gradio
* Similar to Streamlit, but with layout components oriented towards machine learning benchmarking. Less customizable for executive report presentation than Streamlit.

---

### Option D: Desktop AI Clients (Cherry Studio / Chatbox)
* Excellent native UI for chatting with images, but **cannot run custom deterministic Python code** without building a dedicated local MCP server.

---

## 4. Quickstart: Running the Streamlit Client

The repository includes a ready-to-run client in `clients/streamlit_app.py`.

```bash
# 1. Install lightweight UI dependencies
pip install streamlit google-genai pillow

# 2. Run the application
streamlit run clients/streamlit_app.py
```
Open `http://localhost:8501`, drag your screenshots into the upload zone, and receive an audited campaign report in seconds.
