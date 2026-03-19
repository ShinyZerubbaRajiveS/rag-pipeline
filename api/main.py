import os, sys
from typing import Optional
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

app = FastAPI(title="Lexis API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

class QueryRequest(BaseModel):
    question: str
    top_k: Optional[int] = 8

@app.get("/")
async def root():
    return {"name": "Lexis", "status": "live", "docs": "/docs"}

@app.get("/health")
async def health():
    return {"status": "live", "version": "1.0.0"}

@app.post("/query")
async def query(request: QueryRequest):
    from database import init_db
    init_db()
    from rag_chain import ask
    result = ask(request.question, top_k=request.top_k)
    return {"question": result["question"], "answer": result["answer"], "sources": result["sources"], "status": "success"}

@app.post("/ingest")
async def ingest(file: UploadFile = File(...)):
    import shutil, tempfile
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in [".pdf", ".txt"]:
        raise HTTPException(status_code=400, detail="PDF or TXT only")
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
    shutil.copyfileobj(file.file, tmp)
    tmp.close()
    named = os.path.join(tempfile.gettempdir(), file.filename)
    os.rename(tmp.name, named)
    from ingestion import ingest_document
    from embeddings import store_chunks, collection
    chunks = ingest_document(named)
    store_chunks(chunks)
    os.remove(named)
    return {"filename": file.filename, "chunks_added": len(chunks), "total_chunks": collection.count(), "status": "success"}

@app.get("/metrics")
async def metrics():
    from database import init_db, get_average_scores, get_all_results
    init_db()
    avg = get_average_scores()
    return {"avg_scores": avg, "total_evals": avg["total_evals"], "results": get_all_results(), "status": "success"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
