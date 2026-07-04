"""
A minimal, real RAG pipeline — the kind a developer actually ships.

Stack: LangChain (orchestration) + Chroma (vector store) + local
sentence-transformer embeddings + Claude (Anthropic) for generation.

It ingests the PDFs you drop in ./data, answers the questions in
questions.txt, and logs each turn to outputs/runs.jsonl as
{question, retrieved_context, answer}.

Notice what is NOT here: no grounding check, no groundlens import.
That is the point. You audit this pipeline's grounding afterwards from
your editor with the Groundlens MCP — without touching a line of it.
See AUDIT_IN_CLAUDE_CODE.md.
"""

from __future__ import annotations

import json
import os
import pathlib
import sys

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_anthropic import ChatAnthropic

DATA = pathlib.Path("data")
DB = "chroma_db"
OUT = pathlib.Path("outputs")
OUT.mkdir(exist_ok=True)

EMB_MODEL = "sentence-transformers/all-MiniLM-L6-v2"          # local, no API key
LLM_MODEL = os.environ.get("GL_MODEL", "claude-sonnet-4-6")   # any current Claude model

PROMPT = """Answer the question using ONLY the context below.
If the answer is not in the context, say plainly that you don't know.

Context:
{context}

Question: {question}

Answer:"""


def build_or_load_index() -> Chroma:
    emb = HuggingFaceEmbeddings(model_name=EMB_MODEL)
    if pathlib.Path(DB).exists():
        return Chroma(persist_directory=DB, embedding_function=emb)

    pdfs = sorted(DATA.glob("*.pdf"))
    if not pdfs:
        sys.exit("No PDF found. Download one into ./data first — see data/README.md.")

    docs = []
    for p in pdfs:
        docs += PyPDFLoader(str(p)).load()

    chunks = RecursiveCharacterTextSplitter(
        chunk_size=1000, chunk_overlap=150
    ).split_documents(docs)

    print(f"Indexing {len(chunks)} chunks from {len(pdfs)} PDF(s)...")
    return Chroma.from_documents(chunks, emb, persist_directory=DB)


def load_questions() -> list[str]:
    if len(sys.argv) > 1:
        return [" ".join(sys.argv[1:])]
    lines = pathlib.Path("questions.txt").read_text(encoding="utf-8").splitlines()
    return [q.strip() for q in lines if q.strip() and not q.startswith("#")]


def main() -> None:
    vs = build_or_load_index()
    retriever = vs.as_retriever(search_kwargs={"k": 4})
    llm = ChatAnthropic(model=LLM_MODEL, temperature=0)  # needs ANTHROPIC_API_KEY

    runs = []
    for q in load_questions():
        hits = retriever.invoke(q)
        context = "\n\n".join(h.page_content for h in hits)
        answer = llm.invoke(PROMPT.format(context=context, question=q)).content
        print(f"\nQ: {q}\nA: {answer}\n" + "-" * 60)
        runs.append({"question": q, "retrieved_context": context, "answer": answer})

    (OUT / "runs.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in runs) + "\n",
        encoding="utf-8",
    )
    print(f"\nLogged {len(runs)} answers to {OUT / 'runs.jsonl'}.")
    print("Now audit their grounding from Claude Code — see AUDIT_IN_CLAUDE_CODE.md.")


if __name__ == "__main__":
    main()
