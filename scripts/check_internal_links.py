from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote, urlparse


LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)|(?:href|src)=[\"']([^\"']+)[\"']", re.IGNORECASE)
IGNORED_DIRECTORIES = {".venv", "outputs", ".pytest_cache", "__pycache__"}
IGNORED_RELATIVE_TREES = {
    Path("datasets/benchmarks/raw"),
    Path("datasets/benchmarks/derived"),
    Path("datasets/benchmarks/work"),
}


def iter_document_links(root: Path):
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        ignored_tree = any(
            relative == tree or tree in relative.parents
            for tree in IGNORED_RELATIVE_TREES
        )
        if (
            IGNORED_DIRECTORIES & set(relative.parts)
            or ignored_tree
            or not path.is_file()
        ):
            continue
        if path.suffix.lower() not in {".md", ".html", ".htm"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in LINK_RE.finditer(text):
            link = match.group(1) or match.group(2)
            yield path, link.strip()


def is_internal(link: str) -> bool:
    parsed = urlparse(link)
    return parsed.scheme == "" and not link.startswith("#")


def target_exists(source: Path, link: str) -> bool:
    clean = unquote(link.split("#", 1)[0])
    if not clean:
        return True
    target = (source.parent / clean).resolve()
    return target.exists()


def main() -> int:
    root = Path.cwd()
    broken = []
    checked = 0
    skipped_external = 0

    for source, link in iter_document_links(root):
        if not is_internal(link):
            skipped_external += 1
            continue
        checked += 1
        if not target_exists(source, link):
            broken.append((source, link))

    print(f"Internal links checked: {checked}")
    print(f"External/non-file links skipped: {skipped_external}")
    print(f"Broken internal links: {len(broken)}")
    for source, link in broken:
        print(f"BROKEN\t{source}\t{link}")
    return 1 if broken else 0


if __name__ == "__main__":
    raise SystemExit(main())
