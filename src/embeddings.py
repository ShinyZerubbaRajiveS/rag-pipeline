"""
embeddings.py  —  Day 2
------------------------
Job : Take the chunks from Day 1, convert each one into a vector
      using sentence-transformers, and store everything in ChromaDB.

After this file runs you can type ANY question in plain English
and get back the most relevant chunks from your PDFs.

Two functions you'll use from other modules:
    store_chunks(chunks)        →  embed + save to ChromaDB
    retrieve(question, top_k)   →  search and return top matches
"""

import os
from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.config import Settings

# ──────────────────────────────────────────────────────────
# SETUP — load embedding model + connect to ChromaDB
# These run once when the module is imported.
# ──────────────────────────────────────────────────────────

print("Loading embedding model... (first run downloads ~80MB, be patient)")

# all-MiniLM-L6-v2:
#   - tiny and fast (80MB)
#   - runs 100% locally — no API key needed
#   - converts any text into a 384-dimension vector
#   - good enough for production RAG systems
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

print("Embedding model loaded!")

# ChromaDB persistent client — saves vectors to disk
# Next time you run, it loads from disk instead of re-embedding
CHROMA_PATH = os.path.join(os.path.dirname(__file__), "..", "chroma_db")

client = chromadb.PersistentClient(path=CHROMA_PATH)

# A "collection" is like a table in a database
# get_or_create → safe to run multiple times, won't duplicate
collection = client.get_or_create_collection(
    name="annual_reports",
    metadata={"hnsw:space": "cosine"}  # cosine similarity = best for text search
)

print(f"ChromaDB connected. Collection has {collection.count()} chunks stored.")


# ──────────────────────────────────────────────────────────
# STEP 1 — STORE CHUNKS
# Take chunks from ingestion.py → embed them → save to Chroma
# ──────────────────────────────────────────────────────────

def store_chunks(chunks: list) -> None:
    """
    Embed all chunks and store in ChromaDB.
    Skips chunks that are already stored (safe to re-run).

    Args:
        chunks: list of dicts from ingestion.py
                each dict has: text, source, page, chunk_id
    """
    if not chunks:
        print("No chunks to store.")
        return

    # find which chunk_ids are already in the database
    existing = set(collection.get()["ids"])

    # filter to only NEW chunks
    new_chunks = [c for c in chunks if c["chunk_id"] not in existing]

    if not new_chunks:
        print(f"All {len(chunks)} chunks already stored. Skipping.")
        return

    print(f"\nEmbedding {len(new_chunks)} new chunks...")
    print("(This may take 1-3 minutes for large PDFs — grab a coffee!)")

    # process in batches of 100 so we don't run out of memory
    batch_size = 100
    total      = len(new_chunks)

    for start in range(0, total, batch_size):
        end   = min(start + batch_size, total)
        batch = new_chunks[start:end]

        # extract just the text strings for embedding
        texts = [c["text"] for c in batch]

        # convert texts → vectors
        # encode() returns a numpy array of shape (batch_size, 384)
        vectors = embedding_model.encode(
            texts,
            show_progress_bar=False,
            convert_to_numpy=True
        ).tolist()   # ChromaDB needs plain Python lists, not numpy arrays

        # prepare metadata — one dict per chunk
        metadatas = [
            {
                "source": c["source"],
                "page":   str(c["page"]),   # ChromaDB stores metadata as strings
            }
            for c in batch
        ]

        # store in ChromaDB
        collection.add(
            ids        = [c["chunk_id"] for c in batch],
            documents  = texts,
            embeddings = vectors,
            metadatas  = metadatas
        )

        # progress update
        print(f"  Stored {end}/{total} chunks...", end="\r")

    print(f"\n✓ Done! {len(new_chunks)} chunks stored in ChromaDB.")
    print(f"  Total in database: {collection.count()}")


# ──────────────────────────────────────────────────────────
# STEP 2 — RETRIEVE
# Given a question, find the most relevant chunks.
# This is the core of RAG — semantic search over your docs.
# ──────────────────────────────────────────────────────────

def retrieve(question: str, top_k: int = 5) -> list:
    """
    Find the top_k most relevant chunks for a given question.

    How it works:
    1. Convert the question into a vector (same model as ingestion)
    2. ChromaDB finds the stored vectors most similar to it
    3. Return those chunks with their metadata + similarity scores

    Args:
        question : plain English question
        top_k    : how many chunks to return (default 5)

    Returns:
        list of dicts:
        {
            "text"  : "...chunk content...",
            "source": "infosys-ar-25.pdf",
            "page"  : "12",
            "score" : 0.87    ← similarity score, higher = more relevant
        }
    """
    if collection.count() == 0:
        print("Database is empty! Run store_chunks() first.")
        return []

    # embed the question using the same model
    question_vector = embedding_model.encode(
        question,
        convert_to_numpy=True
    ).tolist()

    # query ChromaDB — returns top_k most similar chunks
    results = collection.query(
        query_embeddings = [question_vector],
        n_results        = top_k,
        include          = ["documents", "metadatas", "distances"]
    )

    # reformat into clean list of dicts
    chunks = []
    for i in range(len(results["documents"][0])):
        chunks.append({
            "text"  : results["documents"][0][i],
            "source": results["metadatas"][0][i]["source"],
            "page"  : results["metadatas"][0][i]["page"],
            "score" : round(1 - results["distances"][0][i], 3)
            # distance → similarity: 1 - distance
            # score of 1.0 = perfect match, 0.0 = completely unrelated
        })

    return chunks


# ──────────────────────────────────────────────────────────
# DAY 2 CHECKPOINT
# Run:  python3 src/embeddings.py
# ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    from ingestion import ingest_folder

    print("=" * 45)
    print("  DAY 2 CHECKPOINT — Embeddings + Vector Store")
    print("=" * 45)

    # ── Step 1: load chunks from data/ ──
    data_folder = os.path.join(os.path.dirname(__file__), "..", "data")
    chunks      = ingest_folder(data_folder)

    # ── Step 2: embed + store in ChromaDB ──
    store_chunks(chunks)

    # ── Step 3: test retrieval with real questions ──
    print("\n" + "─" * 45)
    print("RETRIEVAL TEST — asking questions about your PDFs")
    print("─" * 45)

    test_questions = [
        "What was Zomato's total revenue?",
        "How many employees does Infosys have?",
        "What is Tata Motors electric vehicle strategy?",
    ]

    for question in test_questions:
        print(f"\nQ: {question}")
        results = retrieve(question, top_k=3)

        for i, chunk in enumerate(results):
            print(f"\n  Result {i+1} (score: {chunk['score']})")
            print(f"  Source : {chunk['source']}  |  Page {chunk['page']}")
            print(f"  Text   : {chunk['text'][:180]}...")

    print("\n" + "=" * 45)
    print("✓ DAY 2 COMPLETE!")
    print(f"  {collection.count()} chunks indexed and searchable.")
    print("  You can now search your PDFs with plain English!")
    print("=" * 45)