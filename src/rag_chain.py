"""
rag_chain.py  —  Day 3
-----------------------
Job : Wire everything together.
      Question → retrieve chunks → format prompt → Groq LLM → cited answer.

This is the core of the entire project.
One function you'll call from everywhere:
    ask(question)  →  { "answer": "...", "sources": [...] }
"""

import os
from dotenv import load_dotenv
from groq import Groq
from embeddings import retrieve   # our Day 2 retrieval function

# ──────────────────────────────────────────────────────────
# SETUP — load API key + connect to Groq
# ──────────────────────────────────────────────────────────

load_dotenv()   # reads your .env file and loads GROQ_API_KEY

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise ValueError(
        "GROQ_API_KEY not found!\n"
        "Make sure your .env file has:  GROQ_API_KEY=your_key_here"
    )

# Groq client — this is what talks to the LLM
client = Groq(api_key=GROQ_API_KEY)

# We use mixtral-8x7b — fast, free, excellent at following instructions
MODEL = "llama-3.3-70b-versatile"


# ──────────────────────────────────────────────────────────
# STEP 1 — SYSTEM PROMPT
# This tells the LLM exactly how to behave.
# The most important part of RAG — controls hallucination.
# ──────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a financial document analyst specializing in Indian company annual reports.

Your job is to answer questions using ONLY the context provided below.

STRICT RULES you must follow:
1. Answer ONLY from the context. Never use outside knowledge.
2. Cite every fact like this: [Source: filename, Page X]
3. If the answer is not in the context, say exactly:
   "I don't have enough information in the provided documents to answer this."
4. Be concise and professional.
5. Never make up numbers, dates, or facts.

These rules are absolute. Follow them for every response."""


# ──────────────────────────────────────────────────────────
# STEP 2 — FORMAT CONTEXT
# Take retrieved chunks and format them into a clean block
# that gets injected into the prompt.
# ──────────────────────────────────────────────────────────

def format_context(chunks: list) -> str:
    """
    Turn a list of chunk dicts into a formatted string for the prompt.

    Example output:
        [Source: infosys-ar-25.pdf, Page 12]
        Revenue grew 21% year-on-year...

        [Source: infosys-ar-25.pdf, Page 13]
        Operating margins improved to 21.3%...
    """
    if not chunks:
        return "No relevant context found."

    formatted = []
    for chunk in chunks:
        entry = f"[Source: {chunk['source']}, Page {chunk['page']}]\n{chunk['text']}"
        formatted.append(entry)

    return "\n\n".join(formatted)


# ──────────────────────────────────────────────────────────
# STEP 3 — CONVERSATION MEMORY
# Store chat history so follow-up questions work.
# "What about last year?" only makes sense with history.
# ──────────────────────────────────────────────────────────

# Simple list that stores the last N messages
# Each item: {"role": "user"/"assistant", "content": "..."}
conversation_history = []
MAX_HISTORY = 6   # keep last 3 exchanges (3 user + 3 assistant)


def add_to_history(role: str, content: str):
    """Add a message to conversation history, trim if too long."""
    conversation_history.append({"role": role, "content": content})

    # keep only last MAX_HISTORY messages
    if len(conversation_history) > MAX_HISTORY:
        conversation_history.pop(0)


def clear_history():
    """Start a fresh conversation."""
    conversation_history.clear()
    print("Conversation history cleared.")


# ──────────────────────────────────────────────────────────
# STEP 4 — THE MAIN ASK FUNCTION
# This is the full RAG pipeline in one function:
# question → retrieve → format → prompt → LLM → answer
# ──────────────────────────────────────────────────────────

def ask(question: str, top_k: int = 8) -> dict:
    """
    Ask any question about your documents.

    Steps inside:
    1. Retrieve top_k relevant chunks from ChromaDB
    2. Format chunks into context block
    3. Build messages array (system + history + new question)
    4. Send to Groq LLM
    5. Return answer + sources

    Args:
        question : plain English question
        top_k    : how many chunks to retrieve (default 8)

    Returns:
        {
            "answer"  : "Zomato's revenue was ₹12,114 crores... [Source: ...]",
            "sources" : [
                {"source": "Zomato_Annual_Report.pdf", "page": "47", "score": 0.89},
                ...
            ],
            "question": "What was Zomato's revenue?"
        }
    """

    # ── 1. Retrieve relevant chunks ──
    chunks = retrieve(question, top_k=top_k)

    if not chunks:
        return {
            "answer"  : "No relevant documents found. Please ingest some documents first.",
            "sources" : [],
            "question": question
        }

    # ── 2. Format context ──
    context = format_context(chunks)

    # ── 3. Build the user message with context injected ──
    user_message = f"""Context from annual reports:
{context}

Question: {question}

Remember: Answer ONLY from the context above. Cite sources."""

    # ── 4. Build messages array for Groq ──
    # Structure: system prompt → conversation history → new question
    messages = (
        [{"role": "system", "content": SYSTEM_PROMPT}]
        + conversation_history
        + [{"role": "user", "content": user_message}]
    )

    # ── 5. Call Groq LLM ──
    response = client.chat.completions.create(
        model       = MODEL,
        messages    = messages,
        temperature = 0.1,    # low temperature = more factual, less creative
        max_tokens  = 1024,   # enough for a thorough answer
    )

    answer = response.choices[0].message.content

    # ── 6. Save to conversation history ──
    # save simplified version without the context block
    add_to_history("user",      question)
    add_to_history("assistant", answer)

    # ── 7. Extract unique sources for the response ──
    seen    = set()
    sources = []
    for chunk in chunks:
        key = f"{chunk['source']}_p{chunk['page']}"
        if key not in seen:
            seen.add(key)
            sources.append({
                "source": chunk["source"],
                "page"  : chunk["page"],
                "score" : chunk["score"]
            })

    return {
        "answer"  : answer,
        "sources" : sources,
        "question": question
    }


# ──────────────────────────────────────────────────────────
# DAY 3 CHECKPOINT
# Run:  python3 src/rag_chain.py
# ──────────────────────────────────────────────────────────

if __name__ == "__main__":

    print("=" * 50)
    print("  DAY 3 CHECKPOINT — RAG Chain")
    print("=" * 50)

    # ── Test 1: Single question ──
    print("\nTest 1: Single question")
    print("─" * 50)

    result = ask("What was Zomato's total revenue in 2024?")

    print(f"\nQ: {result['question']}")
    print(f"\nA: {result['answer']}")
    print(f"\nSources used:")
    for s in result["sources"]:
        print(f"  - {s['source']}  |  Page {s['page']}  |  Score: {s['score']}")

    # ── Test 2: Follow-up question (tests memory) ──
    print("\n" + "─" * 50)
    print("Test 2: Follow-up question (tests conversation memory)")
    print("─" * 50)

    result2 = ask("What were their main expenses?")

    print(f"\nQ: {result2['question']}")
    print(f"\nA: {result2['answer']}")

    # ── Test 3: Question about different company ──
    print("\n" + "─" * 50)
    print("Test 3: Different company")
    print("─" * 50)

    result3 = ask("How many employees does Infosys have and what is their attrition rate?")

    print(f"\nQ: {result3['question']}")
    print(f"\nA: {result3['answer']}")
    print(f"\nSources used:")
    for s in result3["sources"]:
        print(f"  - {s['source']}  |  Page {s['page']}  |  Score: {s['score']}")

    # ── Test 4: Out of context question (should say I don't know) ──
    print("\n" + "─" * 50)
    print("Test 4: Out-of-context question (should say it doesn't know)")
    print("─" * 50)

    result4 = ask("What is the population of Chennai?")
    print(f"\nQ: {result4['question']}")
    print(f"\nA: {result4['answer']}")

    print("\n" + "=" * 50)
    print("✓ DAY 3 COMPLETE!")
    print("  Full RAG chain working with cited answers.")
    print("  Conversation memory working for follow-ups.")
    print("=" * 50)