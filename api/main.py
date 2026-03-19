# """
# main.py  —  Day 5
# ------------------
# Job : Wrap everything into a REST API with 3 endpoints.

# Endpoints:
#     POST /ingest   → upload a PDF, get chunks back
#     POST /query    → ask a question, get cited answer
#     GET  /metrics  → get eval score history from DB

# Run:  uvicorn api.main:app --reload --port 8000
# Docs: http://localhost:8000/docs  (auto-generated!)
# """

# import os
# import sys
# import shutil
# import tempfile
# from typing import Optional

# from fastapi import FastAPI, UploadFile, File, HTTPException
# from fastapi.middleware.cors import CORSMiddleware
# from pydantic import BaseModel

# # add src/ to path so we can import our modules
# sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# from ingestion  import ingest_document
# from embeddings import store_chunks, retrieve, collection
# from rag_chain  import ask, clear_history
# from database   import init_db, get_all_results, get_average_scores

# # ──────────────────────────────────────────────────────────
# # APP SETUP
# # ──────────────────────────────────────────────────────────

# app = FastAPI(
#     title       = "RAG Pipeline API",
#     description = "Multi-source RAG pipeline with evaluation dashboard",
#     version     = "1.0.0"
# )

# # CORS — allows the Streamlit UI to talk to this API
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins     = ["*"],
#     allow_credentials = True,
#     allow_methods     = ["*"],
#     allow_headers     = ["*"],
# )

# # initialise database on startup
# init_db()
# @app.on_event("startup")
# async def startup_event():
#     """Auto-ingest data/ folder on every startup."""
#     import sys
#     sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
#     from ingestion import ingest_folder
#     from embeddings import store_chunks
#     data_path = os.path.join(os.path.dirname(__file__), "..", "data")
#     print("Auto-ingesting documents on startup...")
#     chunks = ingest_folder(data_path)
#     store_chunks(chunks)
#     print(f"Startup ingestion complete — {len(chunks)} chunks ready")

# # ──────────────────────────────────────────────────────────
# # REQUEST / RESPONSE MODELS
# # Pydantic models define the shape of JSON in/out.
# # FastAPI uses these to auto-validate requests.
# # ──────────────────────────────────────────────────────────

# class QueryRequest(BaseModel):
#     question : str
#     top_k    : Optional[int] = 8

#     class Config:
#         json_schema_extra = {
#             "example": {
#                 "question" : "What was Zomato's revenue in FY2024?",
#                 "top_k"    : 8
#             }
#         }


# class QueryResponse(BaseModel):
#     question : str
#     answer   : str
#     sources  : list
#     status   : str = "success"


# class IngestResponse(BaseModel):
#     filename    : str
#     chunks_added: int
#     total_chunks: int
#     status      : str = "success"


# class MetricsResponse(BaseModel):
#     avg_scores   : dict
#     total_evals  : int
#     results      : list
#     status       : str = "success"


# # ──────────────────────────────────────────────────────────
# # ENDPOINT 1 — POST /ingest
# # Upload a PDF → ingest → embed → store in ChromaDB
# # ──────────────────────────────────────────────────────────

# @app.post("/ingest", response_model=IngestResponse)
# async def ingest_file(file: UploadFile = File(...)):
#     """
#     Upload a PDF or TXT file to add it to the knowledge base.

#     - Saves file temporarily
#     - Runs ingestion pipeline
#     - Embeds and stores chunks in ChromaDB
#     - Returns chunk count
#     """

#     # only allow PDF and TXT
#     allowed = [".pdf", ".txt"]
#     ext     = os.path.splitext(file.filename)[1].lower()

#     if ext not in allowed:
#         raise HTTPException(
#             status_code = 400,
#             detail      = f"File type '{ext}' not supported. Use PDF or TXT."
#         )

#     # save uploaded file to a temp location
#     with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
#         shutil.copyfileobj(file.file, tmp)
#         tmp_path = tmp.name

#     try:
#         # rename temp file to original filename for correct metadata
#         named_path = os.path.join(tempfile.gettempdir(), file.filename)
#         os.rename(tmp_path, named_path)

#         # run ingestion pipeline
#         chunks = ingest_document(named_path)

#         if not chunks:
#             raise HTTPException(
#                 status_code = 422,
#                 detail      = "Could not extract text from file."
#             )

#         # embed + store in ChromaDB
#         store_chunks(chunks)

#         return IngestResponse(
#             filename     = file.filename,
#             chunks_added = len(chunks),
#             total_chunks = collection.count(),
#         )

#     finally:
#         # clean up temp file
#         if os.path.exists(named_path):
#             os.remove(named_path)


# # ──────────────────────────────────────────────────────────
# # ENDPOINT 2 — POST /query
# # Ask a question → RAG chain → cited answer + sources
# # ──────────────────────────────────────────────────────────

# @app.post("/query", response_model=QueryResponse)
# async def query(request: QueryRequest):
#     """
#     Ask any question about your ingested documents.

#     Returns:
#     - answer with citations [Source: file, Page N]
#     - list of source chunks used
#     - status
#     """

#     if not request.question.strip():
#         raise HTTPException(
#             status_code = 400,
#             detail      = "Question cannot be empty."
#         )

#     if collection.count() == 0:
#         raise HTTPException(
#             status_code = 404,
#             detail      = "No documents ingested yet. Upload a PDF first."
#         )

#     # run the full RAG chain
#     result = ask(
#         question = request.question,
#         top_k    = request.top_k
#     )

#     return QueryResponse(
#         question = result["question"],
#         answer   = result["answer"],
#         sources  = result["sources"],
#     )


# # ──────────────────────────────────────────────────────────
# # ENDPOINT 3 — GET /metrics
# # Return eval score history from SQLite
# # ──────────────────────────────────────────────────────────

# @app.get("/metrics", response_model=MetricsResponse)
# async def get_metrics():
#     """
#     Get evaluation score history from the database.

#     Returns:
#     - average scores across all runs
#     - total number of evaluations
#     - full history of per-question results
#     """
#     avg_scores = get_average_scores()
#     results    = get_all_results()

#     return MetricsResponse(
#         avg_scores  = avg_scores,
#         total_evals = avg_scores["total_evals"],
#         results     = results,
#     )


# # ──────────────────────────────────────────────────────────
# # BONUS ENDPOINTS — useful extras
# # ──────────────────────────────────────────────────────────

# @app.get("/health")
# async def health_check():
#     """Quick check that the API is running."""
#     return {
#         "status"      : "healthy",
#         "chunks_in_db": collection.count(),
#         "version"     : "1.0.0"
#     }


# @app.post("/clear-history")
# async def clear_conversation():
#     """Clear conversation memory — start fresh chat."""
#     clear_history()
#     return {"status": "success", "message": "Conversation history cleared."}


# @app.get("/")
# async def root():
#     """Root endpoint — shows API info."""
#     return {
#         "name"       : "RAG Pipeline API",
#         "version"    : "1.0.0",
#         "docs"       : "/docs",
#         "endpoints"  : {
#             "ingest"       : "POST /ingest",
#             "query"        : "POST /query",
#             "metrics"      : "GET  /metrics",
#             "health"       : "GET  /health",
#             "clear_history": "POST /clear-history",
#         }
#     }


# # ──────────────────────────────────────────────────────────
# # DAY 5 CHECKPOINT
# # Run: uvicorn api.main:app --reload --port 8000
# # Then open: http://localhost:8000/docs
# # ──────────────────────────────────────────────────────────

# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(
#         "main:app",
#         host    = "0.0.0.0",
#         port    = 8000,
#         reload  = True
#     )

"""
main.py — Final version
Render-compatible: binds port immediately, loads model in background
"""

import os
import sys
import shutil
import tempfile
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# ── global state ──
app_ready = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load everything after server starts — port binds immediately."""
    global app_ready
    import asyncio

    async def load_in_background():
        global app_ready
        try:
            print("Loading embedding model and ChromaDB...")
            from embeddings import collection
            from database import init_db
            init_db()

            # auto-ingest data/ folder
            data_path = os.path.join(os.path.dirname(__file__), "..", "data")
            if os.path.exists(data_path):
                from ingestion import ingest_folder
                from embeddings import store_chunks
                chunks = ingest_folder(data_path)
                store_chunks(chunks)
                print(f"Auto-ingestion complete — {collection.count()} chunks ready")

            app_ready = True
            print("Lexis API ready!")
        except Exception as e:
            print(f"Startup error: {e}")
            app_ready = True  # still mark ready so health check works

    asyncio.create_task(load_in_background())
    yield


app = FastAPI(
    title       = "Lexis — Document Intelligence API",
    description = "Multi-source RAG pipeline with evaluation dashboard",
    version     = "1.0.0",
    lifespan    = lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["*"],
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)


# ── request/response models ──
class QueryRequest(BaseModel):
    question : str
    top_k    : Optional[int] = 8

class QueryResponse(BaseModel):
    question : str
    answer   : str
    sources  : list
    status   : str = "success"

class IngestResponse(BaseModel):
    filename     : str
    chunks_added : int
    total_chunks : int
    status       : str = "success"

class MetricsResponse(BaseModel):
    avg_scores  : dict
    total_evals : int
    results     : list
    status      : str = "success"


# ── endpoints ──

@app.get("/")
async def root():
    return {
        "name"     : "Lexis — Document Intelligence",
        "version"  : "1.0.0",
        "status"   : "ready" if app_ready else "loading",
        "docs"     : "/docs",
        "endpoints": {
            "ingest"       : "POST /ingest",
            "query"        : "POST /query",
            "metrics"      : "GET  /metrics",
            "health"       : "GET  /health",
        }
    }


@app.get("/health")
async def health():
    try:
        from embeddings import collection
        chunks = collection.count()
    except:
        chunks = 0
    return {
        "status"      : "ready" if app_ready else "loading",
        "chunks_in_db": chunks,
        "version"     : "1.0.0"
    }


@app.post("/ingest", response_model=IngestResponse)
async def ingest_file(file: UploadFile = File(...)):
    allowed = [".pdf", ".txt"]
    ext     = os.path.splitext(file.filename)[1].lower()

    if ext not in allowed:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        named_path = os.path.join(tempfile.gettempdir(), file.filename)
        os.rename(tmp_path, named_path)

        from ingestion  import ingest_document
        from embeddings import store_chunks, collection

        chunks = ingest_document(named_path)
        if not chunks:
            raise HTTPException(status_code=422, detail="Could not extract text.")

        store_chunks(chunks)

        return IngestResponse(
            filename     = file.filename,
            chunks_added = len(chunks),
            total_chunks = collection.count(),
        )
    finally:
        for p in [tmp_path, named_path]:
            try:
                if os.path.exists(p): os.remove(p)
            except: pass


@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    from embeddings import collection
    if collection.count() == 0:
        raise HTTPException(status_code=404, detail="No documents ingested yet.")

    from rag_chain import ask
    result = ask(request.question, top_k=request.top_k)

    return QueryResponse(
        question = result["question"],
        answer   = result["answer"],
        sources  = result["sources"],
    )


@app.get("/metrics", response_model=MetricsResponse)
async def get_metrics():
    from database import get_average_scores, get_all_results
    avg     = get_average_scores()
    results = get_all_results()
    return MetricsResponse(
        avg_scores  = avg,
        total_evals = avg["total_evals"],
        results     = results,
    )


@app.post("/clear-history")
async def clear_conversation():
    from rag_chain import clear_history
    clear_history()
    return {"status": "success", "message": "Conversation cleared."}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)