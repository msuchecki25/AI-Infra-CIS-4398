
"""Normalize extracted document text before chunking."""

from dataclasses import dataclass
import re
import unicodedata


class EmptyExtractedText(ValueError):
    """Raised when no readable text was extracted."""


@dataclass(frozen=True)
class CleanedPage:
    page_number: int | None
    text: str
    source_lines: tuple[int, ...]


@dataclass(frozen=True)
class CleaningResult:
    pages: tuple[CleanedPage, ...]
    warnings: tuple[str, ...]


def clean_pages(
    pages: list[tuple[int | None, str]],
) -> CleaningResult:
    """Clean text while preserving page and line references."""

    cleaned_pages = []
    warnings = []

    for page_number, original in pages:
        # Normalize Unicode and line endings.
        normalized = unicodedata.normalize("NFC", original)
        normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
        normalized = normalized.replace("\u2028", "\n")
        normalized = normalized.replace("\u2029", "\n")
        normalized = normalized.replace("\x0c", "\n")

        # Remove invisible formatting characters.
        normalized = re.sub(
            r"[\ufeff\u200b\u2060]", "", normalized
        )

        # Normalize Unicode space characters.
        normalized = re.sub(
            r"[\u00a0\u2000-\u200a\u202f\u205f\u3000]",
            " ",
            normalized,
        )

        # Remove control characters without deleting punctuation.
        normalized = re.sub(
            r"[\x00-\x08\x0b\x0e-\x1f\x7f]",
            "",
            normalized,
        )

        output = []
        source_lines = []

        for line_number, source_line in enumerate(
            normalized.split("\n"), start=1
        ):
            line = source_line.rstrip(" \t")

            # Preserve indentation in code, tables, and lists.
            structured = (
                line.startswith(("    ", "\t"))
                or "|" in line
                or "\t" in line
                or bool(
                    re.match(
                        r"^\s*(?:[-*+]\s|\d+[.)]\s)",
                        line,
                    )
                )
            )

            if not structured:
                line = re.sub(r"[ \t]{2,}", " ", line).strip()

            # Preserve one blank line between paragraphs.
            if not line.strip():
                if output and output[-1] != "":
                    output.append("")
                    source_lines.append(line_number)
                continue

            output.append(line)
            source_lines.append(line_number)

        # Remove trailing blank lines.
        while output and output[-1] == "":
            output.pop()
            source_lines.pop()

        cleaned_text = "\n".join(output)

        if cleaned_text != original:
            location = (
                f"page {page_number}"
                if page_number is not None
                else "unpaginated text"
            )
            warnings.append(
                f"Normalized formatting in {location}."
            )

        cleaned_pages.append(
            CleanedPage(
                page_number=page_number,
                text=cleaned_text,
                source_lines=tuple(source_lines),
            )
        )

    # Reject an entire document with no readable content.
    if not any(
        any(char.isalnum() for char in page.text)
        for page in cleaned_pages
    ):
        raise EmptyExtractedText(
            "No readable text was extracted from the document."
        )

    return CleaningResult(
        pages=tuple(cleaned_pages),
        warnings=tuple(warnings),
    )
