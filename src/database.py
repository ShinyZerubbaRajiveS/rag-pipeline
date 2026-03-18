"""
database.py  —  Day 4 (Part 1)
-------------------------------
Job : Create and manage the SQLite database that logs every
      eval run with its RAGAS scores.

This is your experiment tracker — every time you run the
evaluator, scores get saved here. The UI reads from this
to show score history charts on Day 6.
"""

import sqlite3
import os
from datetime import datetime

# database file lives in the project root
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "eval_logs.db")


def get_connection():
    """Open a connection to the SQLite database."""
    return sqlite3.connect(DB_PATH)


def init_db():
    """
    Create the eval_results table if it doesn't exist.
    Safe to call multiple times — won't duplicate the table.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS eval_results (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id              TEXT,
            timestamp           TEXT,
            question            TEXT,
            answer              TEXT,
            faithfulness        REAL,
            answer_relevancy    REAL,
            context_precision   REAL,
            avg_score           REAL,
            sources             TEXT
        )
    """)

    conn.commit()
    conn.close()
    print(f"Database ready at: {DB_PATH}")


def log_eval_result(
    run_id: str,
    question: str,
    answer: str,
    faithfulness: float,
    answer_relevancy: float,
    context_precision: float,
    sources: str = ""
):
    """
    Save one eval result to the database.

    Args:
        run_id            : identifier for this eval run (e.g. "run_001")
        question          : the question that was asked
        answer            : the answer the RAG chain gave
        faithfulness      : RAGAS faithfulness score (0-1)
        answer_relevancy  : RAGAS answer relevancy score (0-1)
        context_precision : RAGAS context precision score (0-1)
        sources           : comma-separated source filenames
    """
    avg = round((faithfulness + answer_relevancy + context_precision) / 3, 3)

    conn   = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO eval_results
        (run_id, timestamp, question, answer, faithfulness,
         answer_relevancy, context_precision, avg_score, sources)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        run_id,
        datetime.now().isoformat(),
        question,
        answer,
        round(faithfulness,       3),
        round(answer_relevancy,   3),
        round(context_precision,  3),
        avg,
        sources
    ))

    conn.commit()
    conn.close()


def get_all_results() -> list:
    """
    Fetch all eval results from the database.
    Returns list of dicts — used by the UI on Day 6.
    """
    conn   = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT run_id, timestamp, question, answer,
               faithfulness, answer_relevancy,
               context_precision, avg_score, sources
        FROM eval_results
        ORDER BY timestamp ASC
    """)

    rows    = cursor.fetchall()
    columns = ["run_id", "timestamp", "question", "answer",
               "faithfulness", "answer_relevancy",
               "context_precision", "avg_score", "sources"]

    conn.close()
    return [dict(zip(columns, row)) for row in rows]


def get_average_scores() -> dict:
    """
    Get the average of each score across all runs.
    Used for the summary metrics panel in the UI.
    """
    conn   = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            ROUND(AVG(faithfulness),       3),
            ROUND(AVG(answer_relevancy),   3),
            ROUND(AVG(context_precision),  3),
            ROUND(AVG(avg_score),          3),
            COUNT(*)
        FROM eval_results
    """)

    row = cursor.fetchone()
    conn.close()

    return {
        "avg_faithfulness"      : row[0] or 0,
        "avg_answer_relevancy"  : row[1] or 0,
        "avg_context_precision" : row[2] or 0,
        "avg_overall"           : row[3] or 0,
        "total_evals"           : row[4] or 0
    }


def clear_results():
    """Wipe all eval results — useful for fresh test runs."""
    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM eval_results")
    conn.commit()
    conn.close()
    print("All eval results cleared.")


# ── quick test ──
if __name__ == "__main__":
    init_db()

    # insert a dummy row to test
    log_eval_result(
        run_id            = "test_run",
        question          = "What was Zomato revenue?",
        answer            = "Zomato revenue was ₹12,114 crores [Source: Page 47]",
        faithfulness      = 0.85,
        answer_relevancy  = 0.78,
        context_precision = 0.72,
        sources           = "Zomato_Annual_Report_2023-24.pdf"
    )

    results = get_all_results()
    print(f"\nRows in database: {len(results)}")
    print(f"Sample: {results[0]}")

    scores = get_average_scores()
    print(f"\nAverage scores: {scores}")
    print("\n✓ database.py works!")