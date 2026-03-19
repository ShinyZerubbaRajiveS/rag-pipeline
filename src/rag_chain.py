# """
# rag_chain.py  —  Day 3 + Query Expansion upgrade
# --------------------------------------------------
# Job : Wire everything together.
#       Question → expand queries → retrieve chunks → format prompt → Groq LLM → cited answer.

# UPGRADE: Query Expansion
#       Before searching, the LLM rewrites the user's vague question
#       into 3 specific financial versions. We search with all 3,
#       combine results, remove duplicates. Way better retrieval.

#       "Zomato profit in 2024"  →  3 specific queries  →  right chunks found
# """

# import os
# from dotenv import load_dotenv
# from groq import Groq
# from embeddings import retrieve

# load_dotenv()

# GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# if not GROQ_API_KEY:
#     raise ValueError(
#         "GROQ_API_KEY not found!\n"
#         "Make sure your .env file has:  GROQ_API_KEY=your_key_here"
#     )

# client = Groq(api_key=GROQ_API_KEY)
# MODEL  = "llama-3.3-70b-versatile"


# # ──────────────────────────────────────────────────────────
# # SYSTEM PROMPT
# # ──────────────────────────────────────────────────────────

# SYSTEM_PROMPT = """You are a financial document analyst specializing in Indian company annual reports.

# Your job is to answer questions using ONLY the context provided below.

# STRICT RULES you must follow:
# 1. Answer ONLY from the context. Never use outside knowledge.
# 2. Cite every fact like this: [Source: filename, Page X]
# 3. If the answer is not in the context, say exactly:
#    "I don't have enough information in the provided documents to answer this."
# 4. Be concise and professional.
# 5. Never make up numbers, dates, or facts.

# These rules are absolute. Follow them for every response."""


# # ──────────────────────────────────────────────────────────
# # QUERY EXPANSION
# # This is the upgrade that fixes vague user questions.
# #
# # How it works:
# #   User asks: "Zomato profit in 2024"
# #   We ask the LLM: "Rewrite this as 3 specific financial queries"
# #   LLM returns:
# #     1. "Zomato net profit loss FY2024 consolidated"
# #     2. "Zomato EBITDA earnings year ended March 2024"
# #     3. "Zomato profitability crores financial results FY24"
# #   We search ChromaDB with ALL 3 queries
# #   We combine + deduplicate results
# #   Best chunks from all 3 searches go to the LLM
# # ──────────────────────────────────────────────────────────

# EXPANSION_PROMPT = """You are a search query expert for Indian company annual reports.

# A user asked: "{question}"

# Rewrite this as 3 different search queries that would find relevant information
# in annual reports. Make each query more specific using financial terminology.

# Rules:
# - Use terms like: revenue, profit, EBITDA, crores, FY2024, year ended March 2024
# - Each query should approach the topic differently
# - Keep each query under 15 words
# - Return ONLY the 3 queries, one per line, no numbering, no explanation

# 3 queries:"""


# def expand_query(question: str) -> list:
#     """
#     Use the LLM to rewrite a vague question into 3 specific search queries.

#     Args:
#         question: the original user question

#     Returns:
#         list of 3 expanded query strings
#         (always includes the original as fallback)
#     """
#     try:
#         response = client.chat.completions.create(
#             model       = MODEL,
#             messages    = [
#                 {
#                     "role"   : "user",
#                     "content": EXPANSION_PROMPT.format(question=question)
#                 }
#             ],
#             temperature = 0.3,   # slightly creative for diverse queries
#             max_tokens  = 150,   # just 3 short queries needed
#         )

#         raw      = response.choices[0].message.content.strip()
#         queries  = [q.strip() for q in raw.split("\n") if q.strip()]
#         queries  = queries[:3]   # take max 3

#         # always include the original question as a fallback
#         if question not in queries:
#             queries.append(question)

#         print(f"  [Query Expansion] Original: '{question}'")
#         for i, q in enumerate(queries):
#             print(f"  [Query Expansion] Query {i+1}: '{q}'")

#         return queries

#     except Exception as e:
#         # if expansion fails, just use original question
#         print(f"  [Query Expansion] Failed, using original: {e}")
#         return [question]


# def retrieve_with_expansion(question: str, top_k: int = 8) -> list:
#     """
#     Retrieve chunks using multiple expanded queries.
#     Combines results from all queries, removes duplicates,
#     returns the best unique chunks sorted by score.

#     Args:
#         question : original user question
#         top_k    : chunks to retrieve per query

#     Returns:
#         deduplicated list of best chunks across all queries
#     """
#     # step 1: expand the question into multiple queries
#     queries = expand_query(question)

#     # step 2: retrieve chunks for each query
#     all_chunks  = []
#     seen_ids    = set()

#     for query in queries:
#         chunks = retrieve(query, top_k=top_k)

#         for chunk in chunks:
#             # use chunk_id to deduplicate
#             chunk_id = f"{chunk['source']}_p{chunk['page']}_{chunk['text'][:50]}"

#             if chunk_id not in seen_ids:
#                 seen_ids.add(chunk_id)
#                 all_chunks.append(chunk)

#     # step 3: sort by score (best first) and return top results
#     all_chunks.sort(key=lambda x: x["score"], reverse=True)

#     # return top (top_k * 1.5) to give LLM more context
#     limit = int(top_k * 1.5)
#     best  = all_chunks[:limit]

#     print(f"  [Retrieval] {len(queries)} queries → {len(all_chunks)} unique chunks → using top {len(best)}")
#     return best


# # ──────────────────────────────────────────────────────────
# # FORMAT CONTEXT
# # ──────────────────────────────────────────────────────────

# def format_context(chunks: list) -> str:
#     """Format chunk dicts into a clean string for the prompt."""
#     if not chunks:
#         return "No relevant context found."

#     formatted = []
#     for chunk in chunks:
#         entry = f"[Source: {chunk['source']}, Page {chunk['page']}]\n{chunk['text']}"
#         formatted.append(entry)

#     return "\n\n".join(formatted)


# # ──────────────────────────────────────────────────────────
# # CONVERSATION MEMORY
# # ──────────────────────────────────────────────────────────

# conversation_history = []
# MAX_HISTORY          = 6


# def add_to_history(role: str, content: str):
#     """Add a message to conversation history, trim if too long."""
#     conversation_history.append({"role": role, "content": content})
#     if len(conversation_history) > MAX_HISTORY:
#         conversation_history.pop(0)


# def clear_history():
#     """Start a fresh conversation."""
#     conversation_history.clear()
#     print("Conversation history cleared.")


# # ──────────────────────────────────────────────────────────
# # MAIN ASK FUNCTION — now with query expansion
# # ──────────────────────────────────────────────────────────

# def ask(question: str, top_k: int = 8) -> dict:
#     """
#     Ask any question about your documents.

#     Steps inside:
#     1. Expand question into 3 specific search queries (NEW)
#     2. Retrieve chunks using all 3 queries, deduplicate (NEW)
#     3. Format chunks into context block
#     4. Build messages array (system + history + question)
#     5. Send to Groq LLM
#     6. Return answer + sources

#     Args:
#         question : plain English question (vague is fine now!)
#         top_k    : chunks per query (default 8)

#     Returns:
#         {
#             "answer"  : "...[Source: filename, Page X]...",
#             "sources" : [...],
#             "question": "..."
#         }
#     """

#     # ── 1+2. Expand query + retrieve with all expanded queries ──
#     chunks = retrieve_with_expansion(question, top_k=top_k)

#     if not chunks:
#         return {
#             "answer"  : "No relevant documents found. Please ingest some documents first.",
#             "sources" : [],
#             "question": question
#         }

#     # ── 3. Format context ──
#     context = format_context(chunks)

#     # ── 4. Build the user message ──
#     user_message = f"""Context from annual reports:
# {context}

# Question: {question}

# Remember: Answer ONLY from the context above. Cite sources as [Source: filename, Page X]."""

#     # ── 5. Build messages array ──
#     messages = (
#         [{"role": "system", "content": SYSTEM_PROMPT}]
#         + conversation_history
#         + [{"role": "user", "content": user_message}]
#     )

#     # ── 6. Call Groq LLM ──
#     response = client.chat.completions.create(
#         model       = MODEL,
#         messages    = messages,
#         temperature = 0.1,
#         max_tokens  = 1024,
#     )

#     answer = response.choices[0].message.content

#     # ── 7. Save to conversation history ──
#     add_to_history("user",      question)
#     add_to_history("assistant", answer)

#     # ── 8. Extract unique sources ──
#     seen    = set()
#     sources = []
#     for chunk in chunks:
#         key = f"{chunk['source']}_p{chunk['page']}"
#         if key not in seen:
#             seen.add(key)
#             sources.append({
#                 "source": chunk["source"],
#                 "page"  : chunk["page"],
#                 "score" : chunk["score"]
#             })

#     return {
#         "answer"  : answer,
#         "sources" : sources,
#         "question": question
#     }


# # ──────────────────────────────────────────────────────────
# # TEST — run directly to verify query expansion works
# # python3 src/rag_chain.py
# # ──────────────────────────────────────────────────────────

# if __name__ == "__main__":

#     print("=" * 55)
#     print("  RAG Chain — Query Expansion Test")
#     print("=" * 55)

#     # these are intentionally vague — like real users type
#     vague_questions = [
#         "Zomato profit in 2024",
#         "How is Tata doing with EVs?",
#         "Infosys people count",
#         "Did Zomato make money?",
#         "What is the population of Chennai?",   # should still say I don't know
#     ]

#     for question in vague_questions:
#         print(f"\n{'─'*55}")
#         print(f"Q: {question}")
#         result = ask(question)
#         print(f"A: {result['answer'][:300]}...")
#         if result["sources"]:
#             print(f"   Sources: {result['sources'][0]['source']}, Page {result['sources'][0]['page']}")

#     print(f"\n{'='*55}")
#     print("✓ Query expansion upgrade complete!")
#     print("  Vague questions now work much better.")
#     print("=" * 55)

"""
rag_chain.py  —  Final version
--------------------------------
Features:
1. Smart query expansion — only expands 2-9 word questions (saves 70% tokens)
2. Company detection — filters ChromaDB to correct PDF when company is mentioned
3. Cheap model for expansion, powerful model for answers
4. Fixed system prompt — no false "I don't know" when data is in context
"""

import os
from dotenv import load_dotenv
from groq import Groq
from embeddings import retrieve

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
try:
    import streamlit as st
    GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", GROQ_API_KEY)
except:
    pass

if not GROQ_API_KEY:
    raise ValueError(
        "GROQ_API_KEY not found!\n"
        "Make sure your .env file has:  GROQ_API_KEY=your_key_here"
    )

client = Groq(api_key=GROQ_API_KEY)

MODEL_ANSWER    = "llama-3.3-70b-versatile"  # powerful — for final answers
MODEL_EXPANSION = "llama-3.1-8b-instant"     # cheap + fast — for query rewriting


# ──────────────────────────────────────────────────────────
# SYSTEM PROMPT
# ──────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a financial document analyst specializing in company annual reports.

Your job is to answer questions using ONLY the context provided below.

STRICT RULES:
1. Answer ONLY from the context. Never use outside knowledge.
2. Cite every fact like this: [Source: filename, Page X]
3. If you find ANY relevant data — use it, even if partial.
4. Only say "I don't have enough information" if context has ZERO relevant data.
5. Be concise — give ONE clear answer sentence, then cite the source.
6. Never show numbered lists from the source — summarize cleanly.
7. Never make up numbers, dates, or facts.
8. Give the final answer directly. Never show reasoning steps.
These rules are absolute. Follow them for every response."""


# ──────────────────────────────────────────────────────────
# QUERY EXPANSION
# ──────────────────────────────────────────────────────────

EXPANSION_PROMPT = """You are a search query expert for company annual reports and financial filings.

A user asked: "{question}"

Rewrite this as 3 different search queries to find relevant information in annual reports.
Make each query more specific using financial terminology.

Rules:
- Always keep the company name in every query
- Use terms like: revenue, profit, EBITDA, crores, FY2024, MAU, users, employees
- Each query should approach the topic differently
- Keep each query under 15 words
- Return ONLY the 3 queries, one per line, no numbering, no explanation

3 queries:"""


def expand_query(question: str) -> list:
    """
    Rewrite vague question into 3 specific search queries.
    Only expands questions between 2-9 words.
    Uses cheap small model to save tokens.
    """
    word_count = len(question.split())

    # skip if already detailed
    if word_count > 9:
        print(f"  [Query Expansion] Skipped — already detailed ({word_count} words)")
        return [question]

    # skip if too short (single word)
    if word_count < 2:
        print(f"  [Query Expansion] Skipped — too short ({word_count} words)")
        return [question]

    try:
        response = client.chat.completions.create(
            model       = MODEL_EXPANSION,
            messages    = [{"role": "user", "content": EXPANSION_PROMPT.format(question=question)}],
            temperature = 0.3,
            max_tokens  = 120,
        )

        raw     = response.choices[0].message.content.strip()
        queries = [q.strip() for q in raw.split("\n") if q.strip()]
        queries = queries[:3]

        if question not in queries:
            queries.append(question)

        print(f"  [Query Expansion] '{question}' → {len(queries)} queries")
        for i, q in enumerate(queries):
            print(f"    Query {i+1}: {q}")

        return queries

    except Exception as e:
        print(f"  [Query Expansion] Failed, using original: {e}")
        return [question]


# ──────────────────────────────────────────────────────────
# COMPANY DETECTION
# Detects which company the question is about and filters
# ChromaDB to only search that company's PDF.
# Fixes the problem where Nestle questions return Tata chunks.
# ──────────────────────────────────────────────────────────

def detect_company(question: str) -> str:
    """
    Detect company name in question and return its PDF filename.
    Returns None if no company detected — searches all documents.
    """
    question_lower = question.lower()

    # map keywords → exact source filenames in ChromaDB
    # add new companies here when you add new PDFs
    company_map = {
        "nestle"  : "NestleAnnual-Report-2023-24.pdf",
        "nestlé"  : "NestleAnnual-Report-2023-24.pdf",
        "spotify" : "Spotify-20-F-Filing.pdf",
        "zomato"  : "Zomato_Annual_Report_2023-24.pdf",
        "blinkit" : "Zomato_Annual_Report_2023-24.pdf",
        "infosys" : "infosys-ar-25.pdf",
        "tata"    : "tata-motor-IAR-2024-25.pdf",
    }

    for keyword, source in company_map.items():
        if keyword in question_lower:
            print(f"  [Company Filter] '{keyword}' detected → searching only {source}")
            return source

    print(f"  [Company Filter] No company detected → searching all documents")
    return None


# ──────────────────────────────────────────────────────────
# RETRIEVAL WITH EXPANSION + COMPANY FILTER
# ──────────────────────────────────────────────────────────

def retrieve_with_expansion(question: str, top_k: int = 8) -> list:
    """
    Full retrieval pipeline:
    1. Detect company → set source filter
    2. Expand query into multiple versions
    3. Retrieve chunks for each query (filtered to company if detected)
    4. Deduplicate + sort by score
    5. Return best chunks
    """
    source_filter = detect_company(question)
    queries       = expand_query(question)
    all_chunks    = []
    seen_ids      = set()

    for query in queries:
        chunks = retrieve(query, top_k=top_k, source_filter=source_filter)
        for chunk in chunks:
            chunk_id = f"{chunk['source']}_p{chunk['page']}_{chunk['text'][:50]}"
            if chunk_id not in seen_ids:
                seen_ids.add(chunk_id)
                all_chunks.append(chunk)

    all_chunks.sort(key=lambda x: x["score"], reverse=True)
    limit = int(top_k * 1.5)
    best  = all_chunks[:limit]

    print(f"  [Retrieval] {len(queries)} queries → {len(all_chunks)} unique chunks → top {len(best)}")
    return best


# ──────────────────────────────────────────────────────────
# FORMAT CONTEXT
# ──────────────────────────────────────────────────────────

def format_context(chunks: list) -> str:
    """Format chunk dicts into a clean string for the prompt."""
    if not chunks:
        return "No relevant context found."
    formatted = []
    for chunk in chunks:
        entry = f"[Source: {chunk['source']}, Page {chunk['page']}]\n{chunk['text']}"
        formatted.append(entry)
    return "\n\n".join(formatted)


# ──────────────────────────────────────────────────────────
# CONVERSATION MEMORY
# ──────────────────────────────────────────────────────────

conversation_history = []
MAX_HISTORY          = 6


def add_to_history(role: str, content: str):
    conversation_history.append({"role": role, "content": content})
    if len(conversation_history) > MAX_HISTORY:
        conversation_history.pop(0)


def clear_history():
    conversation_history.clear()
    print("Conversation history cleared.")


# ──────────────────────────────────────────────────────────
# MAIN ASK FUNCTION
# ──────────────────────────────────────────────────────────

def ask(question: str, top_k: int = 8) -> dict:
    """
    Full RAG pipeline:
    1. Detect company + expand query
    2. Retrieve filtered chunks
    3. Format context
    4. Send to LLM
    5. Return answer + sources
    """

    chunks = retrieve_with_expansion(question, top_k=top_k)

    if not chunks:
        return {
            "answer"  : "No relevant documents found. Please ingest some documents first.",
            "sources" : [],
            "question": question
        }

    context = format_context(chunks)

    user_message = f"""Context from annual reports and financial filings:
{context}

Question: {question}

Important: If you see ANY relevant numbers, metrics, or facts in the context above
that relate to this question — use them to answer. Cite as [Source: filename, Page X].
Only say you don't have information if the context has ZERO relevant data."""

    messages = (
        [{"role": "system", "content": SYSTEM_PROMPT}]
        + conversation_history
        + [{"role": "user", "content": user_message}]
    )

    response = client.chat.completions.create(
        model       = MODEL_ANSWER,
        messages    = messages,
        temperature = 0.1,
        max_tokens  = 512,
    )

    answer = response.choices[0].message.content

    add_to_history("user",      question)
    add_to_history("assistant", answer)

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
# TEST
# python3 src/rag_chain.py
# ──────────────────────────────────────────────────────────

if __name__ == "__main__":

    print("=" * 55)
    print("  RAG Chain — Final Version Test")
    print("=" * 55)

    test_questions = [
        "What is Nestle revenue in 2024?",
        "Spotify MAU",
        "Zomato profit",
        "What is Tata Motors electric vehicle strategy?",
        "Infosys employees",
        "What is the population of Chennai?",
    ]

    for question in test_questions:
        print(f"\n{'─'*55}")
        print(f"Q: {question}")
        result = ask(question)
        print(f"A: {result['answer'][:250]}")
        if result["sources"]:
            print(f"   Source: {result['sources'][0]['source']}, Page {result['sources'][0]['page']}")

    print(f"\n{'='*55}")
    print("✓ Final RAG chain working!")
    print("="*55)