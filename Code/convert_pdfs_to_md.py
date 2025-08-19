import sys
from pathlib import Path
from typing import Iterable

try:
    from markitdown import MarkItDown
except ImportError as import_error:  # pragma: no cover
    message = (
        "MarkItDown is not installed. Install it with: pip install 'markitdown[all]'\n"
        "On Windows PowerShell (recommended in a venv):\n"
        "  python -m venv .venv\n  .\\.venv\\Scripts\\Activate.ps1\n  pip install 'markitdown[all]'\n"
    )
    raise SystemExit(message) from import_error


def tidy_markdown(raw_markdown: str) -> str:
    """Improve organization/readability of Markdown converted from PDFs.

    - Joins mid-sentence hard line breaks into paragraphs
    - Normalizes bullet symbols to standard '- '
    - Preserves headings, lists, code fences, and tables
    """
    import re

    lines = raw_markdown.splitlines()

    normalized: list[str] = []
    in_code_fence = False

    bullet_start_pattern = re.compile(r"^\s{0,3}([\-*+]|\d+[.)])\s+")

    for line in lines:
        # Normalize common bullet symbols from copy/paste (e.g., •, ◦, ▪)
        stripped = line.lstrip()
        if stripped.startswith("• ") or stripped.startswith("· ") or stripped.startswith("◦ ") or stripped.startswith("▪ ") or stripped.startswith("‣ "):
            line = (" " * (len(line) - len(stripped))) + "- " + stripped[2:]

        # Track fenced code blocks
        if line.strip().startswith("```"):
            in_code_fence = not in_code_fence
            normalized.append(line)
            continue

        # Do not alter content inside code fences
        if in_code_fence:
            normalized.append(line)
            continue

        # Keep structural lines as-is
        is_heading = line.lstrip().startswith("#")
        is_table = line.lstrip().startswith("|")
        is_blockquote = line.lstrip().startswith(">")
        is_list_item = bool(bullet_start_pattern.match(line))

        if is_heading or is_table or is_blockquote or is_list_item or line.strip() == "":
            normalized.append(line)
            continue

        # Paragraph merge: if previous line is a plain paragraph line, join
        if normalized and normalized[-1].strip() and not normalized[-1].lstrip().startswith(("#", ">", "|")) and not bullet_start_pattern.match(normalized[-1]):
            prev = normalized[-1].rstrip()
            curr = line.lstrip()
            # If previous ends with a hyphen (likely hyphenation), merge without extra space
            if prev.endswith("-") and curr[:1].islower():
                joined = prev[:-1] + curr
            else:
                joined = prev + " " + curr
            normalized[-1] = joined
        else:
            normalized.append(line)

    # Collapse 3+ blank lines into at most 2 for readability
    collapsed: list[str] = []
    blank_run = 0
    for ln in normalized:
        if ln.strip() == "":
            blank_run += 1
        else:
            blank_run = 0
        if blank_run <= 2:
            collapsed.append(ln)

    return "\n".join(collapsed).strip() + "\n"


def iter_files(directory: Path, recursive: bool = True) -> Iterable[Path]:
    """Yield files under directory. If recursive, traverses subdirectories."""
    if recursive:
        for entry in directory.rglob("*"):
            if entry.is_file():
                yield entry
    else:
        for entry in directory.iterdir():
            if entry.is_file():
                yield entry


def main() -> int:
    project_root = Path(__file__).resolve().parent
    input_dir = project_root / "assets"
    output_dir = project_root / "markdown"

    if not input_dir.exists():
        print(f"Input directory not found: {input_dir}")
        print("Create an 'assets' folder in the project root and add files to convert.")
        return 1

    output_dir.mkdir(parents=True, exist_ok=True)

    # Initialize MarkItDown with default settings; it will handle supported types internally
    converter = MarkItDown()

    converted_count = 0
    failed_files: list[tuple[Path, str]] = []

    for source_path in iter_files(input_dir, recursive=True):
        # Mirror the relative path under output_dir
        relative_path = source_path.relative_to(input_dir)
        destination_dir = output_dir / relative_path.parent
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination_path = destination_dir / f"{source_path.stem}.md"
        try:
            result = converter.convert(str(source_path))
            text_content: str = getattr(result, "text_content", "") or ""

            # Post-process for better organization
            improved_md = tidy_markdown(text_content)

            # Add simple YAML front matter for organization
            from datetime import datetime, timezone

            front_matter = (
                "---\n"
                f"title: {source_path.stem}\n"
                f"source: {source_path.name}\n"
                f"converted: {datetime.now(timezone.utc).isoformat()}\n"
                "---\n\n"
            )

            destination_path.write_text(front_matter + improved_md, encoding="utf-8", newline="\n")
            converted_count += 1
            print(f"Converted: {source_path.name} -> {destination_path.relative_to(project_root)}")
        except Exception as error:  # pragma: no cover
            failed_files.append((source_path, str(error)))

    print(f"\nDone. Converted {converted_count} file(s).")
    if failed_files:
        print("The following file(s) failed to convert:")
        for failed_path, error_message in failed_files:
            print(f" - {failed_path.name}: {error_message}")

    # Exit code 0 if at least one file converted successfully and none failed; 1 otherwise
    return 0 if converted_count > 0 and not failed_files else (1 if failed_files else 0)


if __name__ == "__main__":
    sys.exit(main())


