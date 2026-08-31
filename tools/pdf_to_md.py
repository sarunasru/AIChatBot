"""Extract text from a PDF into a scrape-style .md so clean_scrape.py can chunk it.

Usage: python tools/pdf_to_md.py <input.pdf> <output.md> "<Title>" "<source url>"
"""

import sys
from pathlib import Path

from pypdf import PdfReader


def main() -> None:
    src, out, title, url = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
    reader = PdfReader(src)
    parts = []
    for page in reader.pages:
        text = page.extract_text() or ""
        text = text.strip()
        if text:
            parts.append(text)
    body = "\n\n".join(parts)

    header = f"---\nurl: {url}\ntitle: {title}\nlang: lt\ntype: pdf\n---\n\n# {title}\n\n"
    Path(out).write_text(header + body, encoding="utf-8")
    print(f"Pages: {len(reader.pages)}  chars: {len(body)}  -> {out}")


if __name__ == "__main__":
    main()
