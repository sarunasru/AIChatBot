"""Clean and chunk the raw scraped pages in knowledge/temp/ for retrieval.

Dev/build tool (not imported by the app). It strips the consistent scrape noise,
splits each page into heading-based chunks, and writes them to
knowledge/site_chunks.jsonl (one JSON object per chunk).

Run:  python tools/clean_scrape.py
"""

import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
# Both scrape folders: temp/ has the location/service pages (café, rooms, rules),
# temp2/ has the subject-librarian/research/staff pages. Together they're complete.
SRC_DIRS = [BASE_DIR / "knowledge" / "temp", BASE_DIR / "knowledge" / "temp2"]
OUT_FILE = BASE_DIR / "knowledge" / "site_chunks.jsonl"

# Whole lines that are pure scrape scaffolding and carry no content.
NOISE_LINES = {
    "article", "aside", "video", "// video", "event", "// event",
    "footer", "//footer", "//article", "start: sliders", "end: sliders",
    "​",  # stray zero-width / non-breaking artifacts
}

# Substrings that mark a redacted / useless fragment.
EMAIL_PLACEHOLDER = "Šis el. pašto adresas yra apsaugotas nuo šlamšto"

MIN_CHUNK_CHARS = 40    # drop near-empty chunks (bare headings, etc.)
MAX_CHUNK_CHARS = 1600  # split larger sections so retrieval stays focused/cheap


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Split leading '--- ... ---' YAML-ish frontmatter from the body."""
    meta: dict[str, str] = {}
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            block = text[3:end]
            for line in block.splitlines():
                if ":" in line:
                    key, _, val = line.partition(":")
                    meta[key.strip()] = val.strip()
            text = text[end + 4 :]
    return meta, text


def _clean_line(line: str) -> str | None:
    """Return a cleaned line, or None if it should be dropped."""
    stripped = line.strip()
    if not stripped:
        return ""  # keep blank lines for paragraph separation
    if stripped.lower() in NOISE_LINES:
        return None
    if EMAIL_PLACEHOLDER in stripped:
        stripped = stripped.replace(EMAIL_PLACEHOLDER, "").strip(" ,")
        if not stripped:
            return None
    # Drop navigation bullets: a list item that is essentially just a link to
    # another page (the repeated "Vietos/Paslaugos/Apie" sidebar on every page).
    if re.match(r"^[-*]\s*\[[^\]]+\]\([^)]*\)\s*$", stripped):
        return None
    # Convert markdown links [text](url) -> "text (url)"; keep both text and url.
    stripped = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r"\1 (\2)", stripped)
    # Drop non-http links (anchors, mailto artifacts) keeping just their text.
    stripped = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", stripped)
    # Strip emphasis markers.
    stripped = stripped.replace("**", "").replace("__", "")
    return stripped


# Headings that are just the sidebar nav sections, not real page content.
NAV_HEADINGS = {"vietos", "paslaugos", "apie", "ištekliai", "mokslinei veiklai", "naujienos"}


def _is_mostly_links(block: str) -> bool:
    lines = [l for l in block.splitlines() if l.strip()]
    if len(lines) <= 1:
        return False
    linky = sum(1 for l in lines if "http" in l or re.match(r"^[-*]\s", l))
    return linky / len(lines) > 0.6


def _clean_body(body: str) -> str:
    out_lines = []
    for line in body.splitlines():
        cleaned = _clean_line(line)
        if cleaned is not None:
            out_lines.append(cleaned)
    text = "\n".join(out_lines)
    text = re.sub(r"\n{3,}", "\n\n", text)  # collapse blank runs
    return text.strip()


def _split_long(block: str) -> list[str]:
    """Split an over-long block into <=MAX_CHUNK_CHARS pieces at paragraph breaks."""
    if len(block) <= MAX_CHUNK_CHARS:
        return [block]
    pieces: list[str] = []
    current = ""
    for para in block.split("\n\n"):
        if current and len(current) + len(para) + 2 > MAX_CHUNK_CHARS:
            pieces.append(current.strip())
            current = ""
        # A single paragraph longer than the cap is kept whole (rare); flush it alone.
        current = f"{current}\n\n{para}" if current else para
    if current.strip():
        pieces.append(current.strip())
    return pieces


def _chunk_page(title: str, body: str) -> list[str]:
    """Split a cleaned page into chunks at markdown headings."""
    chunks: list[str] = []
    current: list[str] = []

    def flush() -> None:
        block = "\n".join(current).strip()
        if len(block) < MIN_CHUNK_CHARS:
            return
        heading = current[0].strip().lower() if current else ""
        if heading in NAV_HEADINGS:
            return
        if _is_mostly_links(block):
            return
        # Prepend the page title so a chunk is self-contained context.
        prefix = f"{title}\n" if title and title.lower() not in block.lower()[:80] else ""
        for piece in _split_long(block):
            chunks.append((prefix + piece).strip())

    for line in body.splitlines():
        if re.match(r"^#{1,6}\s", line):
            flush()
            current = [re.sub(r"^#{1,6}\s*", "", line)]
        else:
            current.append(line)
    flush()
    return chunks


def _location_tag(filename: str) -> str:
    """Derive building keywords from the source filename so building queries match.

    Many pages spell out the building name in full but never the abbreviation the
    user types (e.g. "MKIC"); tagging injects both so keyword search lands right.
    """
    if "mkic" in filename:
        return "MKIC Mokslinės komunikacijos ir informacijos centras Saulėtekis"
    if "centrine-biblioteka" in filename:
        return "CB Centrinė biblioteka Universiteto gatvė"
    if "siauliu-akademijos" in filename:
        return "ŠAIC Šiaulių akademijos informacijos centras"
    if "fakultetu-skaityklos" in filename:
        return "fakulteto skaitykla"
    return ""


def main() -> None:
    # Gather pages from every source folder, de-duplicating by filename (a page
    # scraped into both temp/ and temp2/ is only processed once).
    files: list[Path] = []
    seen_names: set[str] = set()
    for src in SRC_DIRS:
        if not src.exists():
            continue
        for path in sorted(src.glob("*.md")):
            if path.name in seen_names:
                continue
            seen_names.add(path.name)
            files.append(path)
    if not files:
        raise SystemExit(f"No source files in: {', '.join(str(d) for d in SRC_DIRS)}")

    all_chunks = []
    for path in files:
        raw = path.read_text(encoding="utf-8")
        meta, body = _parse_frontmatter(raw)
        title = meta.get("title", "").strip()
        cleaned = _clean_body(body)
        tag = _location_tag(path.name)
        for chunk in _chunk_page(title, cleaned):
            text = f"[{tag}]\n{chunk}" if tag else chunk
            all_chunks.append({
                "source": path.name,
                "title": title,
                "url": meta.get("url", ""),
                "text": text,
            })

    with OUT_FILE.open("w", encoding="utf-8") as f:
        for c in all_chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    total_chars = sum(len(c["text"]) for c in all_chunks)
    print(f"Pages processed: {len(files)}")
    print(f"Chunks produced: {len(all_chunks)}")
    print(f"Total chunk chars: {total_chars} (~{total_chars // 4} tokens)")
    print(f"Avg chunk chars: {total_chars // max(len(all_chunks), 1)}")
    print(f"Written to: {OUT_FILE}")


if __name__ == "__main__":
    main()
