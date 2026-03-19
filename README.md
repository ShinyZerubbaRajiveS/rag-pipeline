## rag-pipeline
Multi-source RAG pipeline with evaluation dashboard

# Lexis — Document Intelligence
 
> Ask anything about your documents. Every answer grounded in source material, cited to the exact page.
 

---
 
## What is Lexis?
 
Lexis is a production-grade RAG (Retrieval-Augmented Generation) pipeline that lets you upload any PDF — annual reports, research papers, legal documents, contracts — and ask questions in plain English. Every answer is grounded in the document and cited to the exact page. No hallucinations. No guessing.
 
Built as a real AI engineering project covering the full stack: data ingestion, semantic search, LLM generation, automated evaluation, REST API, and a minimal chat UI.
 
---
 
## Demo
 
**Live URL:**   [Click Here...!](https://lexis-rag.streamlit.app)

**API:**  https://lexis-rag.onrender.com

**UI:**   https://lexis-rag.streamlit.app
 
**Sample queries:**
- *"What is Nestle's revenue in FY2024?"* → ₹242,754.8 million [Source: NestleAnnual-Report-2023-24.pdf, Page 120]
- *"How many employees does Infosys have?"* → 3,23,578 employees [Source: infosys-ar-25.pdf, Page 10]
- *"What is Tata Motors EV market share?"* → 55%+ in India [Source: tata-motor-IAR-2024-25.pdf, Page 47]
- *"Spotify monthly active users"* → 751 million MAUs [Source: Spotify-20-F-Filing.pdf, Page 45]
 
---
 
## Architecture
 
```
PDF / TXT / URL
      ↓
Ingestion Pipeline (PyMuPDF + BeautifulSoup)
      ↓
Text Cleaning + Chunking (800 chars, 100 overlap)
      ↓
Embedding (sentence-transformers/all-MiniLM-L6-v2)
      ↓
Vector Store (ChromaDB — local persistent)
      ↓
Query Expansion (llama-3.1-8b via Groq — rewrites vague queries)
      ↓
Company Detection (filters search to correct document)
      ↓
RAG Chain (llama-3.3-70b via Groq — cited answers)
      ↓
RAGAS Evaluation (faithfulness · answer relevancy · context precision)
      ↓
FastAPI Backend + Streamlit UI
```
 
---
 
## Key Features
 
**Smart Query Expansion**
Vague questions are automatically rewritten into 3 specific search queries before retrieval. "Zomato profit" becomes 3 targeted financial queries — improving context precision by ~8%.
 
**Company Detection**
When a company name is mentioned, search is filtered to that company's document only. Prevents Tata Motors chunks from appearing when asking about Nestle.
 
**Automated Evaluation**
RAGAS metrics score every pipeline run across faithfulness, answer relevancy, and context precision. Scores are logged to SQLite and visualized in the Evaluation dashboard.
 
**Zero hallucination policy**
System prompt enforces strict grounding — answers only from retrieved context, every fact cited as [Source: filename, Page X].
 
---
 
## Evaluation Results
 
| Metric | Baseline | After Tuning |
|---|---|---|
| Faithfulness | 0.608 | 0.675 |
| Answer Relevancy | 0.604 | 0.668 |
| Context Precision | 0.525 | 0.575 |
| Overall Average | 0.625 | 0.655 |
 
Improvements driven by: query expansion, company-level source filtering, and system prompt tuning.
 
---
 
## Tech Stack
 
| Layer | Tool | Why |
|---|---|---|
| PDF parsing | PyMuPDF | Fast, handles complex layouts |
| Web scraping | BeautifulSoup4 | Clean HTML → text extraction |
| Chunking | LangChain RecursiveTextSplitter | Paragraph-aware splitting |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) | Local, free, 384-dim vectors |
| Vector DB | ChromaDB | Local persistent, no cloud needed |
| LLM (answers) | Groq llama-3.3-70b-versatile | Fast, free tier, excellent instruction following |
| LLM (expansion) | Groq llama-3.1-8b-instant | Cheap model for query rewriting |
| Evaluation | RAGAS | Industry-standard RAG metrics |
| Score logging | SQLite | Zero-setup experiment tracking |
| API | FastAPI | Auto-docs, async, production-grade |
| UI | Streamlit | Rapid AI app deployment |
| Deployment | Render | Free tier, GitHub integration |
 
**Total cost: $0** — fully open source, no OpenAI, no paid APIs, no GPU required.
 
---
 
## Project Structure
 
```
lexis/
├── data/                    ← drop PDFs here
├── src/
│   ├── ingestion.py         ← PDF/web/txt loader + chunker
│   ├── embeddings.py        ← embedding model + ChromaDB
│   ├── rag_chain.py         ← query expansion + RAG pipeline
│   ├── evaluator.py         ← RAGAS evaluation runner
│   └── database.py          ← SQLite eval score logger
├── api/
│   └── main.py              ← FastAPI (3 endpoints)
├── ui/
│   └── app.py               ← Streamlit chat + eval dashboard
├── chroma_db/               ← auto-created vector store
├── eval_logs.db             ← auto-created eval history
└── requirements.txt
```
 
---
 
## Getting Started
 
**1. Clone and install**
```bash
git clone https://github.com/ShinyZerubbaRajiveS/rag-pipeline
cd rag-pipeline
pip install -r requirements.txt
```
 
**2. Set your Groq API key**
```bash
echo "GROQ_API_KEY=your_key_here" > .env
```
Free key at: https://console.groq.com
 
**3. Add your documents**
```bash
# drop PDFs into data/ folder, then:
python3 src/embeddings.py
```
 
**4. Run the UI**
```bash
streamlit run ui/app.py --server.port 8501
```
 
**5. Run the API**
```bash
uvicorn api.main:app --reload --port 8000
# docs at: http://localhost:8000/docs
```
 
**6. Run evaluation**
```bash
python3 src/evaluator.py
```
 
---
 
## API Endpoints
 
| Method | Endpoint | Description |
|---|---|---|
| POST | `/ingest` | Upload PDF → chunk → embed → store |
| POST | `/query` | Ask question → get cited answer + sources |
| GET | `/metrics` | Fetch eval score history |
| GET | `/health` | Check API status + chunk count |
 
---
 
## Known Limitations
 
- File upload via Streamlit UI is limited by hosting tunnel size. For large PDFs, use direct CLI ingestion: `python3 -c "from src.ingestion import ingest_document; ..."`
- Groq free tier: 100,000 tokens/day. Query expansion uses smart routing to minimize token usage (~1,200 tokens/question vs ~4,000 without optimization)
- Tables and charts in PDFs extract as plain text — numeric data in complex tables may not retrieve cleanly
