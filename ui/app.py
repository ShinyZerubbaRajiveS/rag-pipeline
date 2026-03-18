"""
app.py  —  Day 6
-----------------
Job : Build the chat interface + eval dashboard.

Two tabs:
    Tab 1 — Chat    : upload PDFs, ask questions, see cited answers
    Tab 2 — Metrics : eval score charts from Day 4

Run:  streamlit run ui/app.py --server.port 8501
"""

import sys
import os
import streamlit as st

# add src/ to path so we can import our modules directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from ingestion  import ingest_document
from embeddings import store_chunks, collection
from rag_chain  import ask, clear_history
from database   import get_all_results, get_average_scores, init_db

# ──────────────────────────────────────────────────────────
# PAGE CONFIG — must be first streamlit call
# ──────────────────────────────────────────────────────────

st.set_page_config(
    page_title = "RAG Pipeline — Annual Reports",
    page_icon  = "📊",
    layout     = "wide"
)

# initialise database
init_db()

# ──────────────────────────────────────────────────────────
# SESSION STATE
# Streamlit reruns the whole script on every interaction.
# session_state persists data across reruns.
# ──────────────────────────────────────────────────────────

if "messages"      not in st.session_state:
    st.session_state.messages      = []   # chat history for display

if "ingested_files" not in st.session_state:
    st.session_state.ingested_files = []  # list of uploaded filenames


# ──────────────────────────────────────────────────────────
# SIDEBAR — file uploader + status
# ──────────────────────────────────────────────────────────

with st.sidebar:
    st.title("📂 Knowledge Base")
    st.caption("Upload PDFs to add them to the RAG pipeline")

    # file uploader
    uploaded_files = st.file_uploader(
        "Upload PDF or TXT files",
        type    = ["pdf", "txt"],
        accept_multiple_files = True,
        help    = "Drop annual reports, research papers, or any document here"
    )

    # process uploaded files
    if uploaded_files:
        for uploaded_file in uploaded_files:
            if uploaded_file.name not in st.session_state.ingested_files:
                with st.spinner(f"Processing {uploaded_file.name}..."):
                    try:
                        # save to temp file
                        import tempfile
                        suffix = os.path.splitext(uploaded_file.name)[1]
                        with tempfile.NamedTemporaryFile(
                            delete = False,
                            suffix = suffix,
                            prefix = uploaded_file.name.replace(suffix, "") + "_"
                        ) as tmp:
                            tmp.write(uploaded_file.read())
                            tmp_path = tmp.name

                        # rename so metadata shows correct filename
                        named_path = os.path.join(
                            tempfile.gettempdir(), uploaded_file.name
                        )
                        os.rename(tmp_path, named_path)

                        # ingest + embed
                        chunks = ingest_document(named_path)
                        store_chunks(chunks)

                        st.session_state.ingested_files.append(uploaded_file.name)
                        st.success(f"✓ {uploaded_file.name} — {len(chunks)} chunks added")

                        # cleanup
                        if os.path.exists(named_path):
                            os.remove(named_path)

                    except Exception as e:
                        st.error(f"Failed to process {uploaded_file.name}: {e}")

    st.divider()

    # show what's currently in the knowledge base
    total_chunks = collection.count()
    st.metric("Chunks in knowledge base", total_chunks)

    if st.session_state.ingested_files:
        st.caption("Files loaded this session:")
        for f in st.session_state.ingested_files:
            st.markdown(f"  📄 {f}")
    else:
        st.caption("Using pre-loaded annual reports:")
        st.markdown("  📄 Zomato Annual Report 2023-24")
        st.markdown("  📄 Infosys Annual Report 2025")
        st.markdown("  📄 Tata Motors Annual Report 2025")

    st.divider()

    # clear conversation button
    if st.button("🗑️ Clear conversation", use_container_width=True):
        st.session_state.messages = []
        clear_history()
        st.rerun()

    # top_k slider
    top_k = st.slider(
        "Chunks to retrieve (top_k)",
        min_value = 3,
        max_value = 15,
        value     = 8,
        help      = "Higher = more context but slower. 8 is a good balance."
    )


# ──────────────────────────────────────────────────────────
# MAIN AREA — two tabs
# ──────────────────────────────────────────────────────────

tab1, tab2 = st.tabs(["💬 Chat", "📊 Eval Dashboard"])


# ══════════════════════════════════════════════════════════
# TAB 1 — CHAT
# ══════════════════════════════════════════════════════════

with tab1:
    st.header("Ask anything about the annual reports")
    st.caption("Answers include citations — every fact traced to a specific page.")

    # display chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

            # show sources for assistant messages
            if msg["role"] == "assistant" and "sources" in msg:
                with st.expander("📎 Sources used", expanded=False):
                    for src in msg["sources"]:
                        st.markdown(
                            f"**{src['source']}** — Page {src['page']} "
                            f"_(relevance: {src['score']})_"
                        )

    # chat input box — appears at bottom
    if prompt := st.chat_input("Ask a question about the annual reports..."):

        # show user message immediately
        with st.chat_message("user"):
            st.markdown(prompt)

        # add to history
        st.session_state.messages.append({
            "role"   : "user",
            "content": prompt
        })

        # get answer from RAG chain
        with st.chat_message("assistant"):
            with st.spinner("Searching documents and generating answer..."):
                try:
                    result = ask(prompt, top_k=top_k)
                    answer = result["answer"]
                    sources = result["sources"]

                    # display answer
                    st.markdown(answer)

                    # show sources in expander
                    if sources:
                        with st.expander("📎 Sources used", expanded=False):
                            for src in sources:
                                st.markdown(
                                    f"**{src['source']}** — Page {src['page']} "
                                    f"_(relevance: {src['score']})_"
                                )

                    # save to session state
                    st.session_state.messages.append({
                        "role"   : "assistant",
                        "content": answer,
                        "sources": sources
                    })

                except Exception as e:
                    err_msg = f"Error: {e}"
                    st.error(err_msg)
                    st.session_state.messages.append({
                        "role"   : "assistant",
                        "content": err_msg,
                        "sources": []
                    })

    # show example questions if no chat yet
    if not st.session_state.messages:
        st.divider()
        st.caption("Try asking:")
        cols = st.columns(3)

        example_questions = [
            "What is Zomato's mission statement?",
            "What is Tata Motors EV strategy?",
            "How many employees does Infosys have?",
            "What was Zomato's GOV in FY2024?",
            "What are Infosys key business segments?",
            "What is Blinkit and how does it relate to Zomato?",
        ]

        for i, q in enumerate(example_questions):
            with cols[i % 3]:
                if st.button(q, use_container_width=True, key=f"ex_{i}"):
                    # simulate user typing this question
                    st.session_state.messages.append({
                        "role": "user", "content": q
                    })
                    with st.spinner("Thinking..."):
                        result = ask(q, top_k=top_k)
                    st.session_state.messages.append({
                        "role"   : "assistant",
                        "content": result["answer"],
                        "sources": result["sources"]
                    })
                    st.rerun()


# ══════════════════════════════════════════════════════════
# TAB 2 — EVAL DASHBOARD
# ══════════════════════════════════════════════════════════

with tab2:
    st.header("Evaluation Dashboard")
    st.caption("RAGAS scores logged from Day 4 evaluation runs.")

    # fetch data from database
    avg_scores = get_average_scores()
    all_results = get_all_results()

    if avg_scores["total_evals"] == 0:
        st.info("No evaluation results yet. Run `python3 src/evaluator.py` to generate scores.")
    else:
        # ── summary metrics at top ──
        st.subheader("Average scores across all runs")
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric(
                "Faithfulness",
                f"{avg_scores['avg_faithfulness']:.3f}",
                help="Are answers grounded in the documents?"
            )
        with col2:
            st.metric(
                "Answer Relevancy",
                f"{avg_scores['avg_answer_relevancy']:.3f}",
                help="Do answers address the question?"
            )
        with col3:
            st.metric(
                "Context Precision",
                f"{avg_scores['avg_context_precision']:.3f}",
                help="Does retrieval find the right chunks?"
            )
        with col4:
            st.metric(
                "Overall Average",
                f"{avg_scores['avg_overall']:.3f}",
                help="Average of all 3 metrics"
            )

        st.divider()

        # ── score chart over time ──
        if len(all_results) > 1:
            st.subheader("Scores over time")
            import pandas as pd

            df = pd.DataFrame(all_results)
            df["timestamp"] = pd.to_datetime(df["timestamp"])

            st.line_chart(
                df.set_index("timestamp")[[
                    "faithfulness",
                    "answer_relevancy",
                    "context_precision"
                ]],
                height = 300
            )

        st.divider()

        # ── per question breakdown ──
        st.subheader("Per-question breakdown")

        import pandas as pd
        df_display = pd.DataFrame(all_results)[[
            "question", "faithfulness",
            "answer_relevancy", "context_precision", "avg_score"
        ]]
        df_display.columns = [
            "Question", "Faithfulness",
            "Answer Relevancy", "Context Precision", "Avg Score"
        ]

        # colour code the scores
        st.dataframe(
            df_display,
            use_container_width = True,
            hide_index          = True,
            column_config       = {
                "Faithfulness": st.column_config.ProgressColumn(
                    min_value=0, max_value=1, format="%.3f"
                ),
                "Answer Relevancy": st.column_config.ProgressColumn(
                    min_value=0, max_value=1, format="%.3f"
                ),
                "Context Precision": st.column_config.ProgressColumn(
                    min_value=0, max_value=1, format="%.3f"
                ),
                "Avg Score": st.column_config.ProgressColumn(
                    min_value=0, max_value=1, format="%.3f"
                ),
            }
        )

        st.divider()

        # ── full answer log ──
        st.subheader("Full answer log")
        for r in reversed(all_results[-5:]):   # show last 5
            with st.expander(f"Q: {r['question'][:80]}..."):
                st.markdown(f"**Answer:** {r['answer']}")
                st.markdown(f"**Sources:** {r['sources']}")
                cols = st.columns(4)
                cols[0].metric("Faithfulness",      r["faithfulness"])
                cols[1].metric("Answer Relevancy",  r["answer_relevancy"])
                cols[2].metric("Context Precision", r["context_precision"])
                cols[3].metric("Avg Score",         r["avg_score"])