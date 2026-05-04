"""Header-aware markdown chunking and paragraph-aware PDF chunking."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Iterable, Iterator

import tiktoken

from app.ingest.models import Chunk, RawDocument


max_tokens = 800
overlap_tokens = 100
min_tokens = 50
tiny_file_threshold = 400

MAX_TOKENS = max_tokens
OVERLAP_TOKENS = overlap_tokens
MIN_TOKENS = min_tokens
TINY_FILE_THRESHOLD = tiny_file_threshold

HEADING_RE = re.compile(r"^(#{1,3})\s+(.+?)\s*$")

_ENCODING = tiktoken.get_encoding("cl100k_base")
_CHUNK_ID_NAMESPACE = uuid.UUID("8b38b79e-0fb5-4c41-9f5a-cb1223ccf1bf")


@dataclass(frozen=True)
class _Section:
    breadcrumb: str | None
    text: str


@dataclass(frozen=True)
class _TextUnit:
    text: str
    page_marker: int | None = None


@dataclass(frozen=True)
class _PackedText:
    text: str
    page_marker: int | None = None


def token_count(text: str) -> int:
    return len(_ENCODING.encode(text))


def chunk_documents(documents: Iterable[RawDocument]) -> Iterator[Chunk]:
    for document in documents:
        yield from chunk_document(document)


def chunk_document(document: RawDocument) -> Iterator[Chunk]:
    match document.format:
        case "md":
            packed = _chunk_markdown(document)
        case "pdf":
            packed = _chunk_pdf(document)

    for idx, packed_chunk in enumerate(packed):
        text = packed_chunk.text.strip()
        if not text:
            continue
        yield Chunk(
            chunk_id=_chunk_id(document, idx, text),
            source=document.source,
            file_path=document.file_path,
            chunk_idx=idx,
            breadcrumb=packed_chunk.breadcrumb,
            text=text,
            token_count=token_count(text),
            page_marker=packed_chunk.page_marker,
        )


def _chunk_id(document: RawDocument, chunk_idx: int, text: str) -> str:
    name = "\n".join(
        (
            document.source,
            document.file_path.as_posix(),
            str(chunk_idx),
            text,
        )
    )
    return uuid.uuid5(_CHUNK_ID_NAMESPACE, name).hex


@dataclass(frozen=True)
class _PreparedChunk:
    text: str
    breadcrumb: str | None
    page_marker: int | None


def _chunk_markdown(document: RawDocument) -> list[_PreparedChunk]:
    content = document.content.strip()
    breadcrumb = _first_breadcrumb(content)

    if token_count(content) <= TINY_FILE_THRESHOLD:
        return [
            _PreparedChunk(
                text=_compose_markdown_text(breadcrumb, content),
                breadcrumb=breadcrumb,
                page_marker=None,
            )
        ]

    prepared_chunks: list[_PreparedChunk] = []
    for section in _merge_small_sections(_parse_markdown_sections(content)):
        prefix = _markdown_prefix(section.breadcrumb)
        available_body_tokens = max(1, MAX_TOKENS - token_count(prefix))
        section_text = section.text.strip()
        section_with_breadcrumb = _compose_markdown_text(section.breadcrumb, section_text)

        if token_count(section_with_breadcrumb) <= MAX_TOKENS:
            prepared_chunks.append(
                _PreparedChunk(
                    text=section_with_breadcrumb,
                    breadcrumb=section.breadcrumb,
                    page_marker=None,
                )
            )
            continue

        paragraphs = [_TextUnit(text=paragraph) for paragraph in _split_paragraphs(section_text)]
        for packed in _pack_text_units(paragraphs, available_body_tokens):
            prepared_chunks.append(
                _PreparedChunk(
                    text=_compose_markdown_text(section.breadcrumb, packed.text),
                    breadcrumb=section.breadcrumb,
                    page_marker=None,
                )
            )

    return prepared_chunks


def _chunk_pdf(document: RawDocument) -> list[_PreparedChunk]:
    content = document.content.strip()
    if token_count(content) <= TINY_FILE_THRESHOLD:
        return [_PreparedChunk(text=content, breadcrumb=None, page_marker=1)]

    prepared_chunks: list[_PreparedChunk] = []
    for packed in _pack_text_units(_pdf_text_units(content), MAX_TOKENS):
        prepared_chunks.append(
            _PreparedChunk(
                text=packed.text,
                breadcrumb=None,
                page_marker=packed.page_marker or 1,
            )
        )
    return prepared_chunks


def _parse_markdown_sections(content: str) -> list[_Section]:
    heading_stack: dict[int, str] = {}
    current_breadcrumb: str | None = None
    current_lines: list[str] = []
    sections: list[_Section] = []

    def flush() -> None:
        text = "\n".join(current_lines).strip()
        if text:
            sections.append(_Section(breadcrumb=current_breadcrumb, text=text))

    for line in content.splitlines():
        heading_match = HEADING_RE.match(line)
        if heading_match:
            flush()
            current_lines = []
            level = len(heading_match.group(1))
            title = heading_match.group(2).strip()
            heading_stack = {
                existing_level: existing_title
                for existing_level, existing_title in heading_stack.items()
                if existing_level < level
            }
            heading_stack[level] = title
            current_breadcrumb = " > ".join(
                heading_stack[key] for key in sorted(heading_stack)
            )
            continue

        current_lines.append(line)

    flush()
    return sections


def _merge_small_sections(sections: list[_Section]) -> list[_Section]:
    merged_sections: list[_Section] = []
    pending_small_texts: list[str] = []

    for idx, section in enumerate(sections):
        section_text = section.text.strip()
        if not section_text:
            continue

        candidate_text = "\n\n".join([*pending_small_texts, section_text])
        candidate = _Section(breadcrumb=section.breadcrumb, text=candidate_text)
        is_last_section = idx == len(sections) - 1

        if (
            not is_last_section
            and token_count(_compose_markdown_text(candidate.breadcrumb, candidate.text)) < MIN_TOKENS
        ):
            pending_small_texts.append(_compose_markdown_text(section.breadcrumb, section_text))
            continue

        merged_sections.append(candidate)
        pending_small_texts = []

    if pending_small_texts:
        merged_sections.append(
            _Section(
                breadcrumb=None,
                text="\n\n".join(pending_small_texts),
            )
        )

    return merged_sections


def _first_breadcrumb(content: str) -> str | None:
    heading_stack: dict[int, str] = {}
    for line in content.splitlines():
        heading_match = HEADING_RE.match(line)
        if not heading_match:
            continue
        level = len(heading_match.group(1))
        title = heading_match.group(2).strip()
        heading_stack = {
            existing_level: existing_title
            for existing_level, existing_title in heading_stack.items()
            if existing_level < level
        }
        heading_stack[level] = title
        return " > ".join(heading_stack[key] for key in sorted(heading_stack))
    return None


def _split_paragraphs(text: str) -> list[str]:
    return [paragraph.strip() for paragraph in re.split(r"\n\s*\n", text) if paragraph.strip()]


def _pdf_text_units(content: str) -> list[_TextUnit]:
    units: list[_TextUnit] = []
    current_parts: list[str] = []
    current_page = 1
    paragraph_page = 1

    def flush() -> None:
        text = "".join(current_parts).strip()
        if text:
            units.append(_TextUnit(text=text, page_marker=paragraph_page))

    parts = re.split(r"(\f|\n\s*\n)", content)
    for part in parts:
        if not part:
            continue
        if part == "\f":
            flush()
            current_parts = []
            current_page += 1
            paragraph_page = current_page
            continue
        if re.fullmatch(r"\n\s*\n", part):
            flush()
            current_parts = []
            paragraph_page = current_page
            continue
        if not current_parts:
            paragraph_page = current_page
        current_parts.append(part)

    flush()
    return units


def _pack_text_units(units: list[_TextUnit], max_body_tokens: int) -> list[_PackedText]:
    packed_chunks: list[_PackedText] = []
    current_text = ""
    current_page_marker: int | None = None

    def flush_current() -> None:
        nonlocal current_text, current_page_marker
        if current_text.strip():
            packed_chunks.append(
                _PackedText(text=current_text.strip(), page_marker=current_page_marker)
            )
        current_text = ""
        current_page_marker = None

    for unit in units:
        unit_text = unit.text.strip()
        if not unit_text:
            continue

        if token_count(unit_text) > max_body_tokens:
            flush_current()
            packed_chunks.extend(
                _split_oversized_unit(unit_text, max_body_tokens, unit.page_marker)
            )
            continue

        if (
            current_text
            and current_page_marker is not None
            and unit.page_marker is not None
            and unit.page_marker != current_page_marker
        ):
            flush_current()

        candidate_text = _join_text(current_text, unit_text)
        if not current_text or token_count(candidate_text) <= max_body_tokens:
            current_text = candidate_text
            if current_page_marker is None:
                current_page_marker = unit.page_marker
            continue

        previous_text = current_text
        previous_page_marker = current_page_marker
        flush_current()

        overlap_text = _tail_tokens(previous_text, OVERLAP_TOKENS)
        current_text = _join_text(overlap_text, unit_text)
        current_page_marker = previous_page_marker if overlap_text else unit.page_marker

        if token_count(current_text) > max_body_tokens:
            available_overlap_tokens = max(0, max_body_tokens - token_count(unit_text) - 2)
            overlap_text = _tail_tokens(previous_text, available_overlap_tokens)
            current_text = _join_text(overlap_text, unit_text)
            current_page_marker = previous_page_marker if overlap_text else unit.page_marker

        if token_count(current_text) > max_body_tokens:
            current_text = unit_text
            current_page_marker = unit.page_marker

    flush_current()
    return packed_chunks


def _split_oversized_unit(
    text: str,
    max_body_tokens: int,
    page_marker: int | None,
) -> list[_PackedText]:
    token_ids = _ENCODING.encode(text)
    chunks: list[_PackedText] = []
    start = 0
    step = max(1, max_body_tokens - OVERLAP_TOKENS)

    while start < len(token_ids):
        window = token_ids[start : start + max_body_tokens]
        chunks.append(
            _PackedText(
                text=_ENCODING.decode(window).strip(),
                page_marker=page_marker,
            )
        )
        if start + max_body_tokens >= len(token_ids):
            break
        start += step

    return chunks


def _tail_tokens(text: str, count: int) -> str:
    if count <= 0:
        return ""
    return _ENCODING.decode(_ENCODING.encode(text)[-count:]).strip()


def _join_text(first: str, second: str) -> str:
    if first.strip() and second.strip():
        return f"{first.strip()}\n\n{second.strip()}"
    return first.strip() or second.strip()


def _markdown_prefix(breadcrumb: str | None) -> str:
    return f"{breadcrumb.strip()}\n\n" if breadcrumb else ""


def _compose_markdown_text(breadcrumb: str | None, text: str) -> str:
    return f"{_markdown_prefix(breadcrumb)}{text.strip()}".strip()
