"""
ingestion.py  —  Day 1
----------------------
Job: Take raw PDF documents and turn them into clean,
bite-sized chunks ready to be embedded on Day 2.

Each chunk is a plain Python dict:
{
    "text":      "...the actual text...",
    "source":    "infosys_ar.pdf",
    "page":      4,
    "chunk_id":  "infosys_ar.pdf_page4_chunk2"
}
"""

import os
import re
import fitz                          # PyMuPDF — reads PDFs
import requests                      # fetches web pages
from bs4 import BeautifulSoup        # cleans HTML
from langchain_text_splitters import RecursiveCharacterTextSplitter


# ─────────────────────────────────────────────
# STEP 1 — LOADERS
# Each loader returns a list of (text, page_number) tuples.
# ─────────────────────────────────────────────

def load_pdf(file_path: str) -> list:
    """
    Read a PDF file and extract text page by page.
    Returns: [("page text here", 1), ("next page text", 2), ...]
    """
    pages = []

    # fitz.open() opens the PDF
    doc = fitz.open(file_path)

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text()           # extract raw text from this page

        if text.strip():                 # skip completely empty pages
            pages.append((text, page_num + 1))   # page_num+1 so pages start at 1

    doc.close()

    print(f"  [PDF] Loaded {len(pages)} pages from {os.path.basename(file_path)}")
    return pages


def load_txt(file_path: str) -> list:
    """
    Read a plain .txt file.
    Treats the whole file as one page.
    """
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()

    print(f"  [TXT] Loaded {os.path.basename(file_path)}")
    return [(text, 1)]


def load_url(url: str) -> list:
    """
    Fetch a web page and strip all HTML — keep only readable text.
    """
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # Remove script, style, nav — we don't want those
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        text = soup.get_text(separator="\n")

        print(f"  [URL] Loaded {url[:60]}...")
        return [(text, 1)]

    except Exception as e:
        print(f"  [URL] Failed to load {url}: {e}")
        return []


# ─────────────────────────────────────────────
# STEP 2 — TEXT CLEANER
# Raw extracted text is messy. This fixes it.
# ─────────────────────────────────────────────

def clean_text(text: str) -> str:
    """
    Clean messy extracted text:
    - Collapse 3+ newlines into 2
    - Collapse multiple spaces into one
    - Strip leading/trailing whitespace
    """
    text = re.sub(r'\n{3,}', '\n\n', text)    # 3+ newlines → 2 newlines
    text = re.sub(r'[ \t]{2,}', ' ', text)    # multiple spaces → single space
    text = re.sub(r'\n ', '\n', text)          # remove spaces at line starts
    text = text.strip()
    return text


# ─────────────────────────────────────────────
# STEP 3 — CHUNKER
# Split long text into smaller overlapping pieces.
# ─────────────────────────────────────────────

# Build splitter once — reuse for every document
# chunk_size=800:    each chunk is max 800 characters
# chunk_overlap=100: 100 chars of previous chunk repeated at start of next
#                    so we don't lose info at boundaries
splitter = RecursiveCharacterTextSplitter(
    chunk_size=800,
    chunk_overlap=100,
    separators=["\n\n", "\n", ".", " ", ""]
)


def chunk_pages(pages: list, source_name: str) -> list:
    """
    Take a list of (text, page_number) tuples.
    Split them into chunks with full metadata.
    """
    all_chunks = []

    for text, page_num in pages:
        cleaned = clean_text(text)

        if len(cleaned) < 50:       # skip pages with barely any text
            continue

        raw_chunks = splitter.split_text(cleaned)

        for i, chunk_text in enumerate(raw_chunks):
            chunk = {
                "text":     chunk_text,
                "source":   source_name,
                "page":     page_num,
                "chunk_id": f"{source_name}_page{page_num}_chunk{i}"
            }
            all_chunks.append(chunk)

    return all_chunks


# ─────────────────────────────────────────────
# STEP 4 — MAIN INGEST FUNCTIONS
# ─────────────────────────────────────────────

def ingest_document(source: str) -> list:
    """
    Ingest any supported document — PDF, TXT, or URL.
    Returns list of chunk dicts ready for embedding.
    """
    source_name = os.path.basename(source) if not source.startswith("http") else source

    print(f"\nIngesting: {source_name}")

    if source.startswith("http://") or source.startswith("https://"):
        pages = load_url(source)
    elif source.lower().endswith(".pdf"):
        pages = load_pdf(source)
    elif source.lower().endswith(".txt"):
        pages = load_txt(source)
    else:
        print(f"  [SKIP] Unsupported file type: {source}")
        return []

    chunks = chunk_pages(pages, source_name)
    print(f"  [DONE] {len(chunks)} chunks created")
    return chunks


def ingest_folder(folder_path: str) -> list:
    """
    Ingest every PDF and TXT file in a folder.
    Returns all chunks from all files combined.
    """
    all_chunks = []

    if not os.path.exists(folder_path):
        print(f"Folder not found: {folder_path}")
        return []

    files = os.listdir(folder_path)
    supported = [f for f in files if f.lower().endswith((".pdf", ".txt"))]

    if not supported:
        print(f"No PDF or TXT files found in {folder_path}")
        return []

    print(f"Found {len(supported)} file(s) in {folder_path}\n")

    for filename in supported:
        full_path = os.path.join(folder_path, filename)
        chunks = ingest_document(full_path)
        all_chunks.extend(chunks)

    print(f"\n{'─'*40}")
    print(f"Total chunks from all files: {len(all_chunks)}")
    return all_chunks


# ─────────────────────────────────────────────
# RUN THIS FILE DIRECTLY TO TEST
# python src/ingestion.py
# ─────────────────────────────────────────────

if __name__ == "__main__":

    print("=" * 40)
    print("DAY 1 CHECKPOINT — Ingestion Pipeline")
    print("=" * 40)

    # Get the path to data/ folder
    # __file__ is this script's path → go one level up → into data/
    data_folder = os.path.join(os.path.dirname(__file__), "..", "data")

    chunks = ingest_folder(data_folder)

    if chunks:
        print("\n--- Sample: FIRST chunk ---")
        print(f"  chunk_id : {chunks[0]['chunk_id']}")
        print(f"  source   : {chunks[0]['source']}")
        print(f"  page     : {chunks[0]['page']}")
        print(f"  text     : {chunks[0]['text'][:150]}...")

        print("\n--- Sample: LAST chunk ---")
        print(f"  chunk_id : {chunks[-1]['chunk_id']}")
        print(f"  source   : {chunks[-1]['source']}")
        print(f"  text     : {chunks[-1]['text'][:150]}...")

        print(f"\n✓ DAY 1 COMPLETE!")
        print(f"  {len(chunks)} chunks ready for embedding tomorrow.")
    else:
        print("\nNo chunks found. Make sure PDFs are in the data/ folder.")