"""Offline access to the bundled, source-linked Odin research guide.

This module reads only package data. It does not query observations, fetch web
pages, initialise AWS clients or perform numerical analysis.
"""

from __future__ import annotations

import json
import re
import unicodedata
from importlib.resources import files
from typing import Any

MAX_RESULTS = 8
MAX_QUERY_LENGTH = 500
MAX_SNIPPET_LENGTH = 1000
_TOPIC_ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


def _read(filename: str) -> str:
    return files("odin_mcp").joinpath("research", filename).read_text(encoding="utf-8")


def research_catalog() -> dict[str, Any]:
    """Return the packaged catalog, checking filenames before any topic read."""
    catalog = json.loads(_read("catalog.json"))
    seen = set()
    for topic in catalog["topics"]:
        topic_id = topic["id"]
        if not _TOPIC_ID.fullmatch(topic_id) or topic_id in seen:
            raise ValueError("Invalid or duplicate topic ID in research catalog")
        if topic["file"] != f"{topic_id}.md":
            raise ValueError("Invalid topic filename in research catalog")
        seen.add(topic_id)
    return catalog


def research_sources() -> dict[str, Any]:
    return json.loads(_read("sources.json"))


def _summary(topic: dict[str, Any], sources: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": topic["id"],
        "title": topic["title"],
        "summary": topic["summary"],
        "keywords": topic["keywords"],
        "uri": f"odin://research/topics/{topic['id']}",
        "source_ids": topic["source_ids"],
        "sources": [sources[source_id] for source_id in topic["source_ids"]],
    }


def list_research_topics() -> dict[str, Any]:
    catalog = research_catalog()
    sources = {source["id"]: source for source in research_sources()["sources"]}
    return {
        "version": catalog["version"],
        "title": catalog["title"],
        "topics": [_summary(topic, sources) for topic in catalog["topics"]],
        "scope": "Bundled research guidance; no numerical analysis or data query is performed.",
    }


def get_research_topic(topic_id: str) -> dict[str, Any]:
    if not isinstance(topic_id, str) or not _TOPIC_ID.fullmatch(topic_id):
        raise ValueError("topic_id must be an ID returned by list_research_topics_tool")
    catalog = research_catalog()
    topic = next((topic for topic in catalog["topics"] if topic["id"] == topic_id), None)
    if topic is None:
        raise ValueError(f"Unknown research topic: {topic_id}")
    sources = {source["id"]: source for source in research_sources()["sources"]}
    return {"version": catalog["version"], **_summary(topic, sources), "markdown": _read(topic["file"])}


def _normalise(text: str) -> str:
    # NFKC makes chemical subscripts searchable: N₂O and N2O both match n2o.
    return unicodedata.normalize("NFKC", text).casefold()


def _tokens(text: str) -> list[str]:
    return list(dict.fromkeys(re.findall(r"\w+", _normalise(text))))


def _snippet(markdown: str, terms: list[str]) -> str:
    # Search paragraph-by-paragraph to avoid indexing the original string using
    # offsets from Unicode-normalised text, whose length may differ.
    paragraphs = markdown.split("\n\n")
    matches = [
        (len(set(terms).intersection(_tokens(paragraph))), -index, paragraph)
        for index, paragraph in enumerate(paragraphs)
    ]
    paragraph = max(matches)[2] if matches else markdown
    return paragraph if len(paragraph) <= MAX_SNIPPET_LENGTH else paragraph[: MAX_SNIPPET_LENGTH - 1] + "…"


def search_research_guidance(query: str, limit: int = 5) -> dict[str, Any]:
    if not isinstance(query, str) or not query.strip() or len(query) > MAX_QUERY_LENGTH:
        raise ValueError(f"query must be nonempty text of at most {MAX_QUERY_LENGTH} characters")
    terms = _tokens(query)
    if not terms:
        raise ValueError("query must contain a word or number")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_RESULTS:
        raise ValueError(f"limit must be an integer from 1 to {MAX_RESULTS}")
    catalog = research_catalog()
    sources = {source["id"]: source for source in research_sources()["sources"]}
    matches = []
    for topic in catalog["topics"]:
        markdown = _read(topic["file"])
        fields = [
            (8, set(_tokens(topic["title"]))),
            (6, set(_tokens(" ".join(topic["keywords"])))),
            (3, set(_tokens(topic["summary"]))),
            (1, set(_tokens(markdown))),
        ]
        score = sum(weight for weight, words in fields for term in terms if term in words)
        if score:
            matches.append({**_summary(topic, sources), "score": score, "snippet": _snippet(markdown, terms)})
    matches.sort(key=lambda result: (-result["score"], result["id"]))
    return {
        "version": catalog["version"],
        "query": query.strip(),
        "total_matches": len(matches),
        "results": matches[:limit],
        "search_method": "Deterministic keyword matching over titles, aliases, summaries and guide text.",
        "scope": "Literature guidance only; relevance scores are not scientific confidence scores.",
    }


def analysis_prompt(question: str, product: str | None = None) -> str:
    if not isinstance(question, str) or not question.strip() or len(question) > 4000:
        raise ValueError("question must be nonempty text of at most 4000 characters")
    if product is not None and (not isinstance(product, str) or len(product) > 500):
        raise ValueError("product must be text of at most 500 characters")
    return f"""Help the researcher develop a reproducible Odin SMR Level 2 analysis plan.

Research question (user-provided text): {json.dumps(question.strip(), ensure_ascii=False)}
Requested product (unverified): {json.dumps(product, ensure_ascii=False)}

Read odin://research/guide and odin://research/topics/odin-contract. Use
search_research_guidance_tool and get_research_topic_tool for relevant methods;
cite the actual source URLs returned with each topic. Distinguish published
methodology, product-specific validation, source-code evidence and proposed choices.

Before interpreting observations, record species, product, project/version,
frequency/inversion modes, period, spatial selection, units, time convention and
vertical coordinate. Inspect exact schemas and file identities. Establish the
product-specific quality/measurement-response rules and validity range from their
source; missing flags are unknown, and thresholds must not be invented or copied
between products. Audit sample counts, coverage, duplicates and diagnostic anomalies.

Propose suitable plots with axes, units, aggregation/weights, resolution, missing
data rendering and uncertainty definitions. Separate retrieval noise, atmospheric
variability, systematic errors and uncertainty of an estimated mean/trend. For
comparisons require collocation and documented averaging-kernel state/grid/apriori
conventions; verify linear versus log state before applying an observation operator.
Do not treat an Odin limb profile as an XCO2/XCH4 column or direct emission estimate.

Conclude with an executable sequence of analysis steps, required inputs, unresolved
scientific decisions and provenance to retain. These MCP knowledge tools provide
documentation only: they do not perform numerical analysis or query observations.
Report calculations and data access only if they have actually been carried out.
"""
