from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


INCLUDED_CATEGORIES = ("before", "basic", "advanced", "job", "topic", "duty")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
FRONTMATTER_RE = re.compile(r"\A---\s*\n.*?\n---\s*\n", re.DOTALL)
COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
IMAGE_RE = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
HTML_IMAGE_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
COMPONENT_WITH_NAME_RE = re.compile(
    r"<(?:Role|Action|Status|Item|Quest|Pos)\b[^>]*?\bname=[\"']([^\"']+)[\"'][^>]*/?>",
    re.IGNORECASE,
)
HTML_TAG_RE = re.compile(r"<[^>]+>")
URL_RE = re.compile(r"https?://\S+")
DIRECTIVE_RE = re.compile(r"^(?:::{3}|;;;|<FloatTOC\s*/?>).*$", re.MULTILINE)
MARKUP_RE = re.compile(r"(?:==|\*\*|__|~~|`)")
SPACE_RE = re.compile(r"[ \t]+")
BLANK_RE = re.compile(r"\n{3,}")


def clean_markdown(value: str) -> str:
    value = FRONTMATTER_RE.sub("", value.replace("\r\n", "\n"))
    value = COMMENT_RE.sub("", value)
    value = COMPONENT_WITH_NAME_RE.sub(lambda match: match.group(1), value)
    value = IMAGE_RE.sub(lambda match: match.group(1), value)
    value = HTML_IMAGE_RE.sub("", value)
    value = HTML_TAG_RE.sub("", value)
    value = URL_RE.sub("", value)
    value = DIRECTIVE_RE.sub("", value)
    value = MARKUP_RE.sub("", value)
    value = re.sub(r"^\s*[-*+]\s+", "- ", value, flags=re.MULTILINE)
    value = re.sub(r"^\s*\d+[.)]\s+", "- ", value, flags=re.MULTILINE)
    value = SPACE_RE.sub(" ", value)
    value = BLANK_RE.sub("\n\n", value)
    return value.strip()


def split_sections(markdown: str) -> tuple[str, list[tuple[str, str]]]:
    matches = list(HEADING_RE.finditer(markdown))
    title = "Untitled"
    if matches:
        title = clean_markdown(matches[0].group(2)) or title

    sections: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        heading = clean_markdown(match.group(2)) or title
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown)
        body = clean_markdown(markdown[start:end])
        if body:
            sections.append((heading, body))
    if not sections:
        body = clean_markdown(markdown)
        if body:
            sections.append((title, body))
    return title, sections


def chunk_text(value: str, limit: int = 1800) -> list[str]:
    paragraphs = [part.strip() for part in value.split("\n\n") if part.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        pieces = [paragraph[index : index + limit] for index in range(0, len(paragraph), limit)]
        for piece in pieces:
            candidate = f"{current}\n\n{piece}".strip() if current else piece
            if current and len(candidate) > limit:
                chunks.append(current)
                current = piece
            else:
                current = candidate
    if current:
        chunks.append(current)
    return chunks


def build_payload(source_root: Path, commit: str) -> dict[str, object]:
    chunks: list[dict[str, str]] = []
    for category in INCLUDED_CATEGORIES:
        category_root = source_root / "docs" / category
        if not category_root.exists():
            continue
        for path in sorted(category_root.rglob("*.md")):
            relative = path.relative_to(source_root).as_posix()
            document_id = relative.removesuffix(".md")
            title, sections = split_sections(path.read_text(encoding="utf-8"))
            for section_index, (heading, body) in enumerate(sections):
                for part_index, text in enumerate(chunk_text(body)):
                    chunks.append(
                        {
                            "id": f"{document_id}:{section_index}:{part_index}",
                            "document_id": document_id,
                            "title": title,
                            "heading": heading,
                            "category": category,
                            "text": text,
                        }
                    )
    return {
        "source": {
            "repository": "thewakingsands/novice-network",
            "commit": commit,
        },
        "settings": {"max_chunks": 4, "max_chars": 4500},
        "chunks": chunks,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the local FF14 knowledge index.")
    parser.add_argument("source_root", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--commit", required=True)
    args = parser.parse_args()
    payload = build_payload(args.source_root, args.commit)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"Built {len(payload['chunks'])} knowledge chunks at {args.output}")


if __name__ == "__main__":
    main()
