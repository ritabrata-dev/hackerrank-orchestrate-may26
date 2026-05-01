import re
from html import unescape
from pathlib import Path

CORPUS_DIR = Path(__file__).resolve().parents[1] / "data"

docs = []
STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "how",
    "i",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "to",
    "was",
    "we",
    "what",
    "when",
    "where",
    "with",
    "you",
    "your",
    "site",
    "page",
    "pages",
    "issue",
    "please",
    "help",
    "none",
    "all",
    "there",
    "thanks",
    "thank",
}
METADATA_LINE_PREFIXES = (
    "title:",
    "title_slug:",
    "source_url:",
    "article_slug:",
    "last_updated",
    "article_id:",
    "breadcrumbs:",
    "---",
)


def clean_text(text):
    """Normalize text for keyword scoring."""
    normalized = text.lower()
    normalized = re.sub(r"[^\w\s]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def strip_metadata(raw_text):
    """Remove frontmatter and metadata-only lines from raw corpus text."""
    lines = []
    for line in raw_text.splitlines():
        trimmed = line.strip()
        if not trimmed:
            continue
        low = trimmed.lower()
        if low.startswith(METADATA_LINE_PREFIXES):
            continue
        if low.startswith(("final url:", "last modified:", "published:", "canonical:")):
            continue
        if re.match(r"^[a-z_]+:\s+https?://", low):
            continue
        if re.match(r"^[a-z_]+:\s+[a-z0-9\-_]+$", low):
            continue
        if low.startswith(("- ", "* ", "> ", "#")):
            continue
        if "last updated" in low:
            continue
        if low.startswith("!["):
            continue
        lines.append(trimmed)
    return " ".join(lines)


def truncate_at_sentence(text, max_chars=900):
    """Trim text without cutting in the middle of a sentence when possible."""
    if len(text) <= max_chars:
        return text

    candidate = text[:max_chars]
    last_punct = max(candidate.rfind("."), candidate.rfind("!"), candidate.rfind("?"))
    if last_punct >= int(max_chars * 0.6):
        return candidate[: last_punct + 1].strip()

    last_space = candidate.rfind(" ")
    if last_space > 0:
        return candidate[:last_space].strip() + "..."
    return candidate.strip() + "..."


def clean_chunk(raw_text, max_chars=900):
    content_only = strip_metadata(raw_text)
    content_only = unescape(content_only)
    content_only = re.sub(r"<[^>]+>", " ", content_only)
    # Remove markdown links while preserving anchor text.
    content_only = re.sub(r"\[([^\]]+)\]\((https?://[^\)]+)\)", r"\1", content_only)
    # Remove leftover URLs.
    content_only = re.sub(r"https?://\S+", " ", content_only)
    # Remove markdown emphasis/quotes/list artifacts.
    content_only = re.sub(r"[`*_>#\-\|]+", " ", content_only)
    # Remove common encoded artifacts.
    content_only = content_only.replace("\u00a0", " ").replace("Â", " ").replace("â€™", "'")
    content_only = re.sub(r"\s+", " ", content_only).strip()
    if not content_only:
        return ""

    # Keep only meaningful prose-like sentences.
    sentence_candidates = re.split(r"(?<=[\.\!\?])\s+", content_only)
    kept = []
    for sentence in sentence_candidates:
        s = sentence.strip()
        if len(s) < 45:
            continue
        if any(x in s.lower() for x in ["title slug", "source url", "article id", "breadcrumbs", "last updated"]):
            continue
        kept.append(s)
        if len(kept) == 6:
            break

    if not kept:
        return truncate_at_sentence(content_only, max_chars=max_chars)
    return truncate_at_sentence(" ".join(kept), max_chars=max_chars)


def index_corpus():
    global docs
    docs = []
    count = 0

    if not CORPUS_DIR.exists():
        return

    for company_dir in CORPUS_DIR.iterdir():
        if not company_dir.is_dir():
            continue

        files = [
            f for f in company_dir.rglob("*")
            if f.suffix in [".txt", ".md"]
        ][:80]

        for file in files:

            try:
                text = file.read_text(errors="ignore")
            except OSError:
                continue

            if not text or not text.strip():
                continue

            cleaned = clean_chunk(text, max_chars=950)
            if not cleaned:
                continue

            docs.append(
                {
                    "company": company_dir.name.lower(),
                    "text": cleaned,
                    "clean_text": clean_text(cleaned),
                }
            )
            count += 1

    print(f"Indexed {count} corpus chunks")


def retrieve(query, company=None):
    if not docs:
        index_corpus()

    query_clean = clean_text(query or "")
    if not query_clean:
        return "", 0

    query_words = {w for w in query_clean.split() if len(w) > 2 and w not in STOPWORDS}
    if not query_words:
        return "", 0
    scored = []

    for d in docs:
        if company and d["company"] != company.lower():
            continue

        text_clean = d["clean_text"]
        if not text_clean:
            continue

        doc_words = set(text_clean.split())
        overlap_words = query_words & doc_words
        overlap = len(overlap_words)
        if overlap == 0:
            continue
        informative_overlap = sum(1 for w in overlap_words if len(w) >= 5)
        if informative_overlap == 0:
            continue

        phrase_bonus = 5 if query_clean in text_clean else 0
        score = overlap + phrase_bonus
        if score < 2:
            continue

        scored.append((score, d["text"]))

    scored.sort(key=lambda x: x[0], reverse=True)
    if not scored:
        return "", 0

    top_chunks = [text for _, text in scored[:2]]
    context = "\n\n".join(top_chunks)
    top_score = scored[0][0]
    return context, top_score