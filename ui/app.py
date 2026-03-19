# """
# app.py  —  Day 6
# -----------------
# Job : Build the chat interface + eval dashboard.

# Two tabs:
#     Tab 1 — Chat    : upload PDFs, ask questions, see cited answers
#     Tab 2 — Metrics : eval score charts from Day 4


# """
# app.py  —  Final version
# -------------------------
# Fixes applied:
# 1. Sidebar shows ALL files from ChromaDB (not just session uploads)
# 2. File upload saves to data/ folder first — bypasses 413 tunnel limit
# 3. After upload, sidebar refreshes automatically
# 4. Works the same on local AND deployed version
# """

# import sys
# import os
# import streamlit as st
# import tempfile
# import shutil

# sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# from ingestion  import ingest_document
# from embeddings import store_chunks, collection
# from rag_chain  import ask, clear_history
# from database   import get_all_results, get_average_scores, init_db

# # ──────────────────────────────────────────────────────────
# # PAGE CONFIG
# # ──────────────────────────────────────────────────────────

# st.set_page_config(
#     page_title = "RAG Pipeline — Financial Reports",
#     page_icon  = "📊",
#     layout     = "wide"
# )

# init_db()

# # ──────────────────────────────────────────────────────────
# # SESSION STATE
# # ──────────────────────────────────────────────────────────

# if "messages"       not in st.session_state:
#     st.session_state.messages       = []

# if "ingested_files" not in st.session_state:
#     st.session_state.ingested_files = []


# # ──────────────────────────────────────────────────────────
# # HELPER — get all files currently in ChromaDB
# # This is the fix for showing ALL files, not just session ones
# # ──────────────────────────────────────────────────────────

# def get_files_in_db() -> list:
#     """
#     Read all unique source filenames from ChromaDB.
#     Works even after restart — reads from disk, not session.
#     """
#     try:
#         if collection.count() == 0:
#             return []
#         metadatas = collection.get(include=["metadatas"])["metadatas"]
#         unique    = sorted(set(m["source"] for m in metadatas))
#         return unique
#     except Exception:
#         return []


# # ──────────────────────────────────────────────────────────
# # HELPER — save uploaded file to data/ folder
# # Saving to disk first bypasses the Codespaces 413 tunnel limit
# # On deployed Render server this works perfectly for any size
# # ──────────────────────────────────────────────────────────

# DATA_FOLDER = os.path.join(os.path.dirname(__file__), "..", "data")

# def save_uploaded_file(uploaded_file) -> str:
#     """
#     Save a Streamlit uploaded file to the data/ folder.
#     Returns the full path to the saved file.
#     """
#     os.makedirs(DATA_FOLDER, exist_ok=True)
#     save_path = os.path.join(DATA_FOLDER, uploaded_file.name)

#     with open(save_path, "wb") as f:
#         f.write(uploaded_file.getbuffer())

#     return save_path


# # ──────────────────────────────────────────────────────────
# # SIDEBAR
# # ──────────────────────────────────────────────────────────

# with st.sidebar:
#     st.title("📂 Knowledge Base")
#     st.caption("Upload PDFs to add them to the RAG pipeline")

#     # file uploader
#     uploaded_files = st.file_uploader(
#         "Upload PDF or TXT files",
#         type                  = ["pdf", "txt"],
#         accept_multiple_files = True,
#         help                  = "Upload annual reports, research papers, or any document"
#     )

#     # process uploaded files
#     if uploaded_files:
#         for uploaded_file in uploaded_files:

#             # check if already in ChromaDB
#             existing = get_files_in_db()
#             if uploaded_file.name in existing:
#                 st.info(f"'{uploaded_file.name}' already in knowledge base.")
#                 continue

#             with st.spinner(f"Processing {uploaded_file.name}..."):
#                 try:
#                     # save to data/ folder (fixes 413 issue)
#                     save_path = save_uploaded_file(uploaded_file)

#                     # ingest + embed
#                     chunks = ingest_document(save_path)
#                     store_chunks(chunks)

#                     st.success(f"✓ {uploaded_file.name} — {len(chunks)} chunks added")
#                     st.rerun()   # refresh sidebar to show new file

#                 except Exception as e:
#                     st.error(f"Failed: {e}")

#     st.divider()

#     # ── show ALL files in ChromaDB (fix for showing Spotify etc) ──
#     total_chunks = collection.count()
#     st.metric("Total chunks in knowledge base", total_chunks)

#     all_files = get_files_in_db()

#     if all_files:
#         st.caption(f"📚 {len(all_files)} document(s) loaded:")
#         for f in all_files:
#             # clean up display name
#             display = f.replace("_", " ").replace("-", " ")
#             display = os.path.splitext(display)[0]   # remove .pdf
#             st.markdown(f"  📄 {display}")
#     else:
#         st.caption("No documents loaded yet. Upload a PDF above.")

#     st.divider()

#     # clear conversation
#     if st.button("🗑️ Clear conversation", use_container_width=True):
#         st.session_state.messages = []
#         clear_history()
#         st.rerun()

#     # top_k slider
#     top_k = st.slider(
#         "Chunks to retrieve (top_k)",
#         min_value = 3,
#         max_value = 15,
#         value     = 8,
#         help      = "Higher = more context but uses more tokens. 8 is a good balance."
#     )


# # ──────────────────────────────────────────────────────────
# # MAIN AREA — two tabs
# # ──────────────────────────────────────────────────────────

# tab1, tab2 = st.tabs(["💬 Chat", "📊 Eval Dashboard"])


# # ══════════════════════════════════════════════════════════
# # TAB 1 — CHAT
# # ══════════════════════════════════════════════════════════

# with tab1:
#     st.header("Ask anything about the documents")
#     st.caption("Answers include citations — every fact traced to a specific page.")

#     # show no-documents warning
#     if collection.count() == 0:
#         st.warning("No documents loaded yet. Upload a PDF in the sidebar to get started.")

#     # display chat history
#     for msg in st.session_state.messages:
#         with st.chat_message(msg["role"]):
#             st.markdown(msg["content"])
#             if msg["role"] == "assistant" and "sources" in msg and msg["sources"]:
#                 with st.expander("📎 Sources used", expanded=False):
#                     for src in msg["sources"]:
#                         st.markdown(
#                             f"**{src['source']}** — Page {src['page']} "
#                             f"_(relevance: {src['score']})_"
#                         )

#     # chat input
#     if prompt := st.chat_input("Ask a question about the documents..."):

#         with st.chat_message("user"):
#             st.markdown(prompt)

#         st.session_state.messages.append({
#             "role"   : "user",
#             "content": prompt
#         })

#         with st.chat_message("assistant"):
#             with st.spinner("Searching documents and generating answer..."):
#                 try:
#                     result  = ask(prompt, top_k=top_k)
#                     answer  = result["answer"]
#                     sources = result["sources"]

#                     st.markdown(answer)

#                     if sources:
#                         with st.expander("📎 Sources used", expanded=False):
#                             for src in sources:
#                                 st.markdown(
#                                     f"**{src['source']}** — Page {src['page']} "
#                                     f"_(relevance: {src['score']})_"
#                                 )

#                     st.session_state.messages.append({
#                         "role"   : "assistant",
#                         "content": answer,
#                         "sources": sources
#                     })

#                 except Exception as e:
#                     err = f"Error: {e}"
#                     st.error(err)
#                     st.session_state.messages.append({
#                         "role"   : "assistant",
#                         "content": err,
#                         "sources": []
#                     })

#     # example questions when chat is empty
#     if not st.session_state.messages and collection.count() > 0:
#         st.divider()
#         st.caption("Try asking:")
#         cols = st.columns(3)

#         examples = [
#             "What is Zomato's mission statement?",
#             "Tata Motors EV market share",
#             "Infosys employees",
#             "Spotify MAU 2024",
#             "Zomato GOV FY2024",
#             "What is Blinkit?",
#         ]

#         for i, q in enumerate(examples):
#             with cols[i % 3]:
#                 if st.button(q, use_container_width=True, key=f"ex_{i}"):
#                     st.session_state.messages.append({
#                         "role": "user", "content": q
#                     })
#                     with st.spinner("Thinking..."):
#                         result = ask(q, top_k=top_k)
#                     st.session_state.messages.append({
#                         "role"   : "assistant",
#                         "content": result["answer"],
#                         "sources": result["sources"]
#                     })
#                     st.rerun()


# # ══════════════════════════════════════════════════════════
# # TAB 2 — EVAL DASHBOARD
# # ══════════════════════════════════════════════════════════

# with tab2:
#     st.header("Evaluation Dashboard")
#     st.caption("RAGAS scores from evaluation runs — measures pipeline quality.")

#     avg_scores  = get_average_scores()
#     all_results = get_all_results()

#     if avg_scores["total_evals"] == 0:
#         st.info("No evaluation results yet. Run `python3 src/evaluator.py` to generate scores.")
#     else:
#         # summary metrics
#         st.subheader("Average scores across all runs")
#         c1, c2, c3, c4 = st.columns(4)

#         c1.metric("Faithfulness",      f"{avg_scores['avg_faithfulness']:.3f}",
#                   help="Are answers grounded in documents?")
#         c2.metric("Answer Relevancy",  f"{avg_scores['avg_answer_relevancy']:.3f}",
#                   help="Do answers address the question?")
#         c3.metric("Context Precision", f"{avg_scores['avg_context_precision']:.3f}",
#                   help="Does retrieval find the right chunks?")
#         c4.metric("Overall Average",   f"{avg_scores['avg_overall']:.3f}",
#                   help="Average of all 3 metrics")

#         st.divider()

#         # score chart
#         if len(all_results) > 1:
#             st.subheader("Scores over time")
#             import pandas as pd
#             df = pd.DataFrame(all_results)
#             df["timestamp"] = pd.to_datetime(df["timestamp"])
#             st.line_chart(
#                 df.set_index("timestamp")[[
#                     "faithfulness", "answer_relevancy", "context_precision"
#                 ]],
#                 height=300
#             )
#             st.divider()

#         # per question table
#         st.subheader("Per-question breakdown")
#         import pandas as pd
#         df2 = pd.DataFrame(all_results)[[
#             "question", "faithfulness",
#             "answer_relevancy", "context_precision", "avg_score"
#         ]]
#         df2.columns = [
#             "Question", "Faithfulness",
#             "Answer Relevancy", "Context Precision", "Avg"
#         ]
#         st.dataframe(
#             df2,
#             use_container_width = True,
#             hide_index          = True,
#             column_config       = {
#                 "Faithfulness": st.column_config.ProgressColumn(
#                     min_value=0, max_value=1, format="%.3f"),
#                 "Answer Relevancy": st.column_config.ProgressColumn(
#                     min_value=0, max_value=1, format="%.3f"),
#                 "Context Precision": st.column_config.ProgressColumn(
#                     min_value=0, max_value=1, format="%.3f"),
#                 "Avg": st.column_config.ProgressColumn(
#                     min_value=0, max_value=1, format="%.3f"),
#             }
#         )

#         st.divider()

#         # last 5 answers log
#         st.subheader("Recent answers log")
#         for r in reversed(all_results[-5:]):
#             with st.expander(f"Q: {r['question'][:80]}"):
#                 st.markdown(f"**Answer:** {r['answer']}")
#                 cols = st.columns(4)
#                 cols[0].metric("Faithfulness",      r["faithfulness"])
#                 cols[1].metric("Answer Relevancy",  r["answer_relevancy"])
#                 cols[2].metric("Context Precision", r["context_precision"])
#                 cols[3].metric("Avg Score",         r["avg_score"])
"""
app.py — Lexis — Final UI
Fixes: hidden chrome, no avatars, bold muted text, clean answers
"""

import sys, os
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from ingestion  import ingest_document
from embeddings import store_chunks, collection
from rag_chain  import ask, clear_history
from database   import get_all_results, get_average_scores, init_db

st.set_page_config(
    page_title = "Lexis",
    page_icon  = "◆",
    layout     = "wide",
    initial_sidebar_state = "expanded"
)

init_db()

if "messages"       not in st.session_state: st.session_state.messages       = []
if "ingested_files" not in st.session_state: st.session_state.ingested_files = []

st.markdown("""
<style>

@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,600;0,700;1,400&family=DM+Sans:wght@400;500;600&family=DM+Mono:wght@400;500&display=swap');

* { font-family: 'DM Sans', sans-serif !important; }

/* ── nuke ALL streamlit chrome completely ── */
#MainMenu { display: none !important; }
header { display: none !important; }
footer { display: none !important; }
[data-testid="stToolbar"] { display: none !important; }
[data-testid="stDecoration"] { display: none !important; }
[data-testid="stStatusWidget"] { display: none !important; }
[data-testid="stHeader"] { display: none !important; }
.st-emotion-cache-1dp5vir { display: none !important; }
.st-emotion-cache-18ni7ap { display: none !important; }
section[data-testid="stSidebarNav"] { display: none !important; }

/* ── hide keyboard shortcut helper icon ── */
[data-testid="stSidebarCollapseButton"] { display: none !important; }
button[kind="header"] { display: none !important; }
.st-emotion-cache-7ym5gk { display: none !important; }

/* ── hide ALL chat avatars including Lexis bubble ── */
[data-testid="stChatMessageAvatarUser"] { display: none !important; }
[data-testid="stChatMessageAvatarAssistant"] { display: none !important; }
[data-testid="chatAvatarIcon-user"] { display: none !important; }
[data-testid="chatAvatarIcon-assistant"] { display: none !important; }
[data-testid="stChatMessage"] > div:first-child { display: none !important; }
[data-testid="stChatMessage"] > div:first-of-type > [data-testid="stImage"] { display: none !important; }
.stChatMessage [data-testid="stImage"] { display: none !important; }
[class*="avatar"] { display: none !important; }

/* ── layout ── */
.block-container { padding: 2rem 2.8rem !important; max-width: 100% !important; margin-top: 0 !important; }
.stApp { background: #09080a !important; }

/* ── sidebar ── */
[data-testid="stSidebar"] { background: #120f14 !important; border-right: 1px solid #1e1824 !important; }
[data-testid="stSidebar"] * { color: #c4a882 !important; font-weight: 500 !important; }

/* ── sidebar metrics ── */
[data-testid="stMetric"] { background: #1a1220 !important; border: 1px solid #2a1e32 !important; border-radius: 8px !important; padding: 12px 14px !important; }
[data-testid="stMetricValue"] { font-size: 1.6rem !important; font-weight: 600 !important; color: #c9877a !important; }
[data-testid="stMetricLabel"] { font-size: 0.65rem !important; letter-spacing: 0.12em !important; text-transform: uppercase !important; color: #7a5878 !important; font-weight: 600 !important; }

[data-testid="stSidebar"] { 
    min-width: 240px !important; 
    width: 240px !important;
    transform: none !important;
    visibility: visible !important;
}
[data-testid="collapsedControl"] { display: none !important; }

[data-testid="stSidebar"] {
    min-width: 280px !important;
    width: 280px !important;
}

/* ── tabs ── */
[data-testid="stTabs"] button { font-size: 0.68rem !important; letter-spacing: 0.14em !important; text-transform: uppercase !important; font-weight: 600 !important; color: #6a4868 !important; border: none !important; padding: 10px 22px !important; background: transparent !important; }
[data-testid="stTabs"] button[aria-selected="true"] { color: #c9877a !important; border-bottom: 1px solid #c9877a !important; }
[data-testid="stTabsContent"] { padding-top: 2rem !important; }

/* ── chat messages ── */
[data-testid="stChatMessage"] { background: transparent !important; border: none !important; padding: 0.3rem 0 !important; }
[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] p { font-size: 0.92rem !important; line-height: 1.85 !important; color: #c4a882 !important; font-weight: 500 !important; }
[data-testid="stChatMessage"] strong { color: #f0e0cc !important; font-weight: 600 !important; }

/* ── user bubble ── */
[data-testid="stChatMessageContent"] { background: #1e1428 !important; border: 1px solid #2e1e3a !important; border-radius: 10px !important; padding: 10px 16px !important; }

/* ── chat input ── */
[data-testid="stChatInput"] { border: 1px solid #2a1e32 !important; background: #120f14 !important; border-radius: 8px !important; }
[data-testid="stChatInput"] textarea { color: #c4a882 !important; font-size: 0.88rem !important; font-weight: 500 !important; background: transparent !important; }

/* ── buttons ── */
.stButton button { background: transparent !important; border: 1px solid #2a1e32 !important; color: #8a6878 !important; font-size: 0.7rem !important; letter-spacing: 0.06em !important; font-weight: 600 !important; border-radius: 4px !important; padding: 6px 14px !important; transition: all 0.2s !important; }
.stButton button:hover { border-color: #c9877a !important; color: #c9877a !important; }

/* ── file uploader ── */
[data-testid="stFileUploader"] { border: 1px dashed #2a1e32 !important; border-radius: 8px !important; background: #0e0c12 !important; }
[data-testid="stFileUploader"] * { color: #7a5878 !important; font-weight: 500 !important; }

/* ── expander ── */
[data-testid="stExpander"] { border: 1px solid #2a1e32 !important; border-radius: 6px !important; background: #0e0c12 !important; }
[data-testid="stExpander"] summary { font-size: 0.65rem !important; letter-spacing: 0.12em !important; text-transform: uppercase !important; color: #7a5878 !important; font-weight: 600 !important; }
[data-testid="stExpander"] p { font-size: 0.78rem !important; color: #c9877a !important; font-family: 'DM Mono', monospace !important; font-weight: 500 !important; line-height: 1.9 !important; }

/* ── dataframe ── */
[data-testid="stDataFrame"] { border: 1px solid #1e1428 !important; border-radius: 8px !important; background: #0e0c12 !important; }

/* ── divider ── */
hr { border-color: #1e1428 !important; margin: 1.2rem 0 !important; }

/* ── slider ── */
[data-baseweb="slider"] [role="slider"] { background: #c9877a !important; border-color: #c9877a !important; }

/* ── scrollbar ── */
::-webkit-scrollbar { width: 3px; }
::-webkit-scrollbar-track { background: #09080a; }
::-webkit-scrollbar-thumb { background: #2a1e32; border-radius: 2px; }

/* ── caption ── */
.stCaption { color: #7a5878 !important; font-size: 0.7rem !important; font-weight: 500 !important; }

/* ── success / error ── */
[data-testid="stSuccess"] { background: #0e1a14 !important; border: 1px solid #1a3828 !important; color: #6a9a78 !important; border-radius: 6px !important; }
[data-testid="stAlert"] { background: #120f14 !important; border: 1px solid #2a1e32 !important; border-radius: 6px !important; }
</style>
""", unsafe_allow_html=True)


# ── HELPERS ──
DATA_FOLDER = os.path.join(os.path.dirname(__file__), "..", "data")

def get_files_in_db():
    try:
        if collection.count() == 0: return []
        metas = collection.get(include=["metadatas"])["metadatas"]
        return sorted(set(m["source"] for m in metas))
    except: return []

def save_uploaded_file(uf):
    os.makedirs(DATA_FOLDER, exist_ok=True)
    p = os.path.join(DATA_FOLDER, uf.name)
    with open(p, "wb") as f: f.write(uf.getbuffer())
    return p

def clean_name(f):
    return os.path.splitext(f)[0].replace("_"," ").replace("-"," ").title()


# ── SIDEBAR ──
with st.sidebar:
    st.markdown("""
    <div style='padding:1.4rem 0 1.2rem;'>
        <div style='font-size:4.3rem;font-weight:900;color:#f5ede0;letter-spacing:-0.01em;'>
            Le<span style='color:#c9877a;'>xis</span>
        </div>
        <div style='font-size:0.62rem;color:#6a4868;letter-spacing:0.16em;
        text-transform:uppercase;margin-top:4px;font-weight:600;'>
            Document Intelligence
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    st.markdown("<div style='font-size:0.62rem;letter-spacing:0.14em;text-transform:uppercase;color:#7a5878;margin-bottom:10px;font-weight:600;'>Knowledge Base</div>", unsafe_allow_html=True)

    uploaded_files = st.file_uploader(
        "Upload",
        type=["pdf","txt"],
        accept_multiple_files=True,
        label_visibility="collapsed"
    )

    if uploaded_files:
        for uf in uploaded_files:
            if uf.name in get_files_in_db():
                st.caption("Already loaded.")
                continue
            with st.spinner("Processing..."):
                try:
                    sp     = save_uploaded_file(uf)
                    chunks = ingest_document(sp)
                    store_chunks(chunks)
                    st.success(f"{len(chunks)} chunks indexed")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed: {e}")

    st.divider()

    all_files    = get_files_in_db()
    total_chunks = collection.count()

    c1, c2 = st.columns(2)
    c1.metric("Docs",   len(all_files))
    c2.metric("Chunks", f"{total_chunks:,}")

    if all_files:
        st.markdown("<div style='font-size:0.62rem;letter-spacing:0.14em;text-transform:uppercase;color:#7a5878;margin:14px 0 8px;font-weight:600;'>Loaded</div>", unsafe_allow_html=True)
        for f in all_files:
            st.markdown(
                f"<div style='font-size:0.8rem;color:#9a7888;padding:5px 0;"
                f"border-bottom:1px solid #1a1020;display:flex;align-items:center;"
                f"gap:8px;font-weight:500;'>"
                f"<span style='width:3px;height:3px;border-radius:50%;background:#c9877a;"
                f"display:inline-block;flex-shrink:0;'></span>{clean_name(f)}</div>",
                unsafe_allow_html=True
            )

    st.divider()

    st.markdown("<div style='font-size:0.62rem;letter-spacing:0.14em;text-transform:uppercase;color:#7a5878;margin-bottom:10px;font-weight:600;'>Settings</div>", unsafe_allow_html=True)
    top_k = st.slider("Depth", 3, 15, 8, label_visibility="collapsed")
    st.caption(f"Retrieving {top_k} chunks per query")

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Clear conversation", use_container_width=True):
        st.session_state.messages = []
        clear_history()
        st.rerun()


# ── MAIN TABS ──
tab1, tab2 = st.tabs(["CHAT", "EVALUATION"])


# ══ CHAT ══
with tab1:
    st.markdown("""
    <div style='margin-bottom:2.2rem;'>
        <h1 style='font-size:2.4rem;font-weight:600;color:#f5ede0;
        letter-spacing:-0.03em;margin:0;line-height:1.05;'>
            Ask <em style='color:#c9877a;font-style:normal;'>anything.</em>
        </h1>
        <p style='font-size:0.82rem;color:#7a5878;margin-top:10px;
        letter-spacing:0.01em;font-weight:500;'>
            Every answer grounded in your documents — cited to the exact page.
        </p>
    </div>
    """, unsafe_allow_html=True)

    if collection.count() == 0:
        st.markdown("""
        <div style='border:1px solid #1e1428;border-radius:8px;
        padding:18px 22px;background:#0e0c12;'>
            <div style='font-size:0.82rem;color:#7a5878;font-weight:500;'>
                No documents loaded. Upload PDFs using the sidebar to get started.
            </div>
        </div>
        """, unsafe_allow_html=True)

    # chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg["role"] == "assistant" and msg.get("sources"):
                with st.expander("View sources"):
                    for src in msg["sources"]:
                        st.markdown(
                            f"`{clean_name(src['source'])}` · page {src['page']} · score {src['score']}"
                        )

    # suggested queries
    if not st.session_state.messages and collection.count() > 0:
        st.markdown("<div style='font-size:0.62rem;letter-spacing:0.14em;text-transform:uppercase;color:#6a4868;margin-bottom:10px;font-weight:600;'>Suggested queries</div>", unsafe_allow_html=True)
        examples = [
            "Nestle revenue FY2024",
            "Tata Motors EV market share",
            "Infosys employees headcount",
            "Spotify monthly active users",
            "Zomato mission statement",
            "What is Blinkit?",
        ]
        cols = st.columns(3)
        for i, q in enumerate(examples):
            with cols[i % 3]:
                if st.button(q, use_container_width=True, key=f"ex_{i}"):
                    st.session_state.messages.append({"role":"user","content":q})
                    with st.spinner(""):
                        r = ask(q, top_k=top_k)
                    st.session_state.messages.append({
                        "role":"assistant",
                        "content":r["answer"],
                        "sources":r["sources"]
                    })
                    st.rerun()

    # chat input
    if prompt := st.chat_input("Ask a question about your documents..."):
        with st.chat_message("user"):
            st.markdown(prompt)
        st.session_state.messages.append({"role":"user","content":prompt})

        with st.chat_message("assistant"):
            with st.spinner(""):
                try:
                    r = ask(prompt, top_k=top_k)
                    st.markdown(r["answer"])
                    if r["sources"]:
                        with st.expander("View sources"):
                            for src in r["sources"]:
                                st.markdown(
                                    f"`{clean_name(src['source'])}` · page {src['page']} · score {src['score']}"
                                )
                    st.session_state.messages.append({
                        "role":"assistant",
                        "content":r["answer"],
                        "sources":r["sources"]
                    })
                except Exception as e:
                    st.error(f"Error: {e}")
                    st.session_state.messages.append({
                        "role":"assistant","content":f"Error: {e}","sources":[]
                    })


# ══ EVALUATION ══
with tab2:
    st.markdown("""
    <div style='margin-bottom:2.2rem;'>
        <h1 style='font-size:2.4rem;font-weight:600;color:#f5ede0;
        letter-spacing:-0.03em;margin:0;'>
            Eval<em style='color:#c9877a;font-style:normal;'>uation.</em>
        </h1>
        <p style='font-size:0.82rem;color:#7a5878;margin-top:10px;font-weight:500;'>
            RAGAS metrics — faithfulness, answer relevancy, context precision.
        </p>
    </div>
    """, unsafe_allow_html=True)

    avg  = get_average_scores()
    rows = get_all_results()

    if avg["total_evals"] == 0:
        st.markdown("""
        <div style='border:1px solid #1e1428;border-radius:8px;
        padding:18px 22px;background:#0e0c12;'>
            <div style='font-size:0.82rem;color:#7a5878;font-weight:500;'>
                No evaluation data yet. Run
                <code style='color:#c9877a;font-family:DM Mono,monospace;'>
                python3 src/evaluator.py</code> to generate scores.
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        c1,c2,c3,c4 = st.columns(4)
        c1.metric("Faithfulness",      f"{avg['avg_faithfulness']:.3f}")
        c2.metric("Answer Relevancy",  f"{avg['avg_answer_relevancy']:.3f}")
        c3.metric("Context Precision", f"{avg['avg_context_precision']:.3f}")
        c4.metric("Overall",           f"{avg['avg_overall']:.3f}")

        st.divider()

        if len(rows) > 1:
            st.markdown("<div style='font-size:0.62rem;letter-spacing:0.14em;text-transform:uppercase;color:#7a5878;margin-bottom:10px;font-weight:600;'>Score history</div>", unsafe_allow_html=True)
            import pandas as pd
            df = pd.DataFrame(rows)
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            st.line_chart(
                df.set_index("timestamp")[[
                    "faithfulness","answer_relevancy","context_precision"
                ]],
                height=200
            )
            st.divider()

        st.markdown("<div style='font-size:0.62rem;letter-spacing:0.14em;text-transform:uppercase;color:#7a5878;margin-bottom:10px;font-weight:600;'>Per-question breakdown</div>", unsafe_allow_html=True)
        import pandas as pd
        df2 = pd.DataFrame(rows)[[
            "question","faithfulness","answer_relevancy","context_precision","avg_score"
        ]]
        df2.columns = ["Question","Faithfulness","Answer Relevancy","Context Precision","Avg"]
        st.dataframe(
            df2, use_container_width=True, hide_index=True,
            column_config={
                "Faithfulness":      st.column_config.ProgressColumn(min_value=0,max_value=1,format="%.3f"),
                "Answer Relevancy":  st.column_config.ProgressColumn(min_value=0,max_value=1,format="%.3f"),
                "Context Precision": st.column_config.ProgressColumn(min_value=0,max_value=1,format="%.3f"),
                "Avg":               st.column_config.ProgressColumn(min_value=0,max_value=1,format="%.3f"),
            }
        )

        st.divider()
        st.markdown("<div style='font-size:0.62rem;letter-spacing:0.14em;text-transform:uppercase;color:#7a5878;margin-bottom:10px;font-weight:600;'>Recent evaluations</div>", unsafe_allow_html=True)
        for r in reversed(rows[-5:]):
            with st.expander(r["question"][:80]):
                st.markdown(
                    f"<div style='font-size:0.85rem;color:#9a7888;"
                    f"line-height:1.75;font-weight:500;'>{r['answer']}</div>",
                    unsafe_allow_html=True
                )
                c1,c2,c3,c4 = st.columns(4)
                c1.metric("Faithfulness",      r["faithfulness"])
                c2.metric("Answer Relevancy",  r["answer_relevancy"])
                c3.metric("Context Precision", r["context_precision"])
                c4.metric("Avg",               r["avg_score"])