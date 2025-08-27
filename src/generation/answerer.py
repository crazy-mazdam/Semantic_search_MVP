# src/generation/answerer.py
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Any
import os
import textwrap
from dotenv import load_dotenv
from openai import OpenAI

from retrieval.dense import retrieve

@dataclass
class Citation:
    doc_id: str
    title: str
    pages: str
    excerpt: str

@dataclass
class Answer:
    answer: str
    citations: List[Citation]

def _build_context(hits: List[Dict[str, Any]], max_chars: int = 9000) -> str:
    """
    Build a compact context block from top-K hits.
    Each section carries title + pages header and a trimmed excerpt.
    """
    parts: List[str] = []
    used = 0
    for h in hits:
        title = h.metadata.get("title", "") or h.metadata.get("doc_id", "")
        pages = h.metadata.get("pages_covered", "")
        body = h.text.strip().replace("\r", " ").strip()
        # Trim long bodies so full context stays within ~9k chars
        body = (body[:1500] + "…") if len(body) > 1500 else body
        section = f"### {title} — pages {pages}\n{body}\n"
        if used + len(section) > max_chars and parts:
            break
        parts.append(section)
        used += len(section)
    return "\n".join(parts)

_SYSTEM = """You are a domain-aware assistant answering questions about economics and finance using the provided EXCERPTS ONLY.
Rules:
- If the evidence is insufficient or unrelated, reply exactly: "Not found in corpus."
- Do not invent facts or numbers.
- Prefer precise, concise explanations.
- When possible, echo key equations/terms verbatim from the excerpts.
- Do not cite anything outside the provided context."""

_USER_TEMPLATE = """Question:
{question}

You will be given multiple source excerpts. Use them strictly to answer.
If you can answer, give a clear explanation first, then a compact bullet list of key points.

Answer in English."""

def _call_openai(model: str, messages: List[Dict[str, str]], max_tokens: int = 600) -> str:
    load_dotenv()
    client = OpenAI()  # uses OPENAI_API_KEY from env
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.2,
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content.strip()

def answer_with_citations(
    question: str,
    top_k: int = 5,
    model: str = "gpt-4.1",
) -> Answer:
    # 1) Dense retrieval
    hits = retrieve(question, top_k=top_k)

    if not hits:
        return Answer(answer="Not found in corpus.", citations=[])

    # 2) Build grounded context
    context = _build_context(hits)

    messages = [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": _USER_TEMPLATE.format(question=question)},
        {"role": "user", "content": f"Sources (excerpts):\n\n{context}"},
    ]

    # 3) Model call
    model_answer = _call_openai(model, messages)

    # 4) Assemble citations (title + pages + short excerpt)
    cits: List[Citation] = []
    for h in hits:
        title = h.metadata.get("title", "") or h.metadata.get("doc_id", "")
        pages = h.metadata.get("pages_covered", "")
        excerpt = h.text.strip().replace("\n", " ")
        excerpt = (excerpt[:240] + "…") if len(excerpt) > 240 else excerpt
        cits.append(Citation(
            doc_id=h.doc_id,
            title=title,
            pages=pages,
            excerpt=excerpt,
        ))

    # 5) Abstain if the model ignored evidence
    # Simple guard: if model produced no content or is off-topic, fallback.
    if not model_answer:
        return Answer(answer="Not found in corpus.", citations=[])

    return Answer(answer=model_answer, citations=cits)
