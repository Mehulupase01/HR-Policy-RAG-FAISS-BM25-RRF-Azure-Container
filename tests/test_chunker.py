from __future__ import annotations

from pathlib import Path

import re

import tiktoken

from app.ingest.chunker import (
    MAX_TOKENS,
    OVERLAP_TOKENS,
    chunk_document,
    chunk_documents,
    token_count,
)
from app.ingest.loader import CorpusLoader
from app.ingest.models import RawDocument


CORPUS_ROOT = Path(__file__).resolve().parents[1] / "corpus"
ENCODING = tiktoken.get_encoding("cl100k_base")


def raw_markdown(content: str, file_path: str = "policy.md") -> RawDocument:
    return RawDocument(
        file_path=Path(file_path),
        source="opengov",
        format="md",
        content=content,
    )


def raw_pdf(content: str, file_path: str = "policy.pdf") -> RawDocument:
    return RawDocument(
        file_path=Path(file_path),
        source="madetech",
        format="pdf",
        content=content,
    )


def test_tiny_file_produces_exactly_one_chunk() -> None:
    chunks = list(chunk_document(raw_markdown("# Handbook\n\nTiny but useful policy text.")))

    assert len(chunks) == 1
    assert chunks[0].chunk_idx == 0
    assert chunks[0].breadcrumb == "Handbook"
    assert chunks[0].page_marker is None
    assert len(chunks[0].chunk_id) == 32
    assert re.fullmatch(r"[0-9a-f]{32}", chunks[0].chunk_id)


def test_chunk_ids_are_deterministic_for_same_document() -> None:
    document = raw_markdown("# Handbook\n\nDeterministic policy text.")

    first_run = list(chunk_document(document))
    second_run = list(chunk_document(document))

    assert [chunk.chunk_id for chunk in first_run] == [chunk.chunk_id for chunk in second_run]


def test_long_markdown_h2_sections_preserve_breadcrumbs() -> None:
    time_off_text = " ".join(f"timeoff{i}" for i in range(950))
    sick_leave_text = " ".join(f"sickleave{i}" for i in range(120))
    document = raw_markdown(
        f"# HR Manual\n\n## Time Off\n\n{time_off_text}\n\n## Sick Leave\n\n{sick_leave_text}"
    )

    chunks = list(chunk_document(document))

    assert len(chunks) >= 2
    assert any(chunk.breadcrumb == "HR Manual > Time Off" for chunk in chunks)
    assert any(chunk.breadcrumb == "HR Manual > Sick Leave" for chunk in chunks)


def test_tiny_markdown_section_attaches_to_next_sibling_with_heading_context() -> None:
    main_policy_text = " ".join(f"mainpolicy{i}" for i in range(260))
    document = raw_markdown(
        "# HR Manual\n\n"
        "## Intro\n\n"
        "Tiny bridge text.\n\n"
        "## Main Policy\n\n"
        f"{main_policy_text}"
    )

    chunks = list(chunk_document(document))
    first_chunk = chunks[0]

    assert first_chunk.breadcrumb == "HR Manual > Main Policy"
    assert "HR Manual > Intro" in first_chunk.text
    assert "Tiny bridge text." in first_chunk.text
    assert "HR Manual > Main Policy" in first_chunk.text


def test_adjacent_chunks_in_same_markdown_section_share_overlap_text() -> None:
    long_text = " ".join(f"overlapword{i}" for i in range(1800))
    document = raw_markdown(f"# HR Manual\n\n## Very Long Section\n\n{long_text}")

    chunks = list(chunk_document(document))
    first_section_chunks = [
        chunk for chunk in chunks if chunk.breadcrumb == "HR Manual > Very Long Section"
    ]

    assert len(first_section_chunks) >= 2
    overlap_text = ENCODING.decode(
        ENCODING.encode(first_section_chunks[0].text)[-OVERLAP_TOKENS:]
    ).strip()

    assert overlap_text in first_section_chunks[1].text


def test_no_real_corpus_chunk_exceeds_max_tokens() -> None:
    chunks = list(chunk_documents(CorpusLoader(CORPUS_ROOT).load_all()))

    assert chunks
    assert all(chunk.token_count <= MAX_TOKENS for chunk in chunks)


def test_real_corpus_chunks_preserve_required_metadata_invariants() -> None:
    chunks = list(chunk_documents(CorpusLoader(CORPUS_ROOT).load_all()))

    assert chunks
    for chunk in chunks:
        assert re.fullmatch(r"[0-9a-f]{32}", chunk.chunk_id)
        assert not chunk.file_path.is_absolute()
        assert chunk.chunk_idx >= 0
        assert chunk.text.strip()
        assert chunk.token_count == token_count(chunk.text)

        if chunk.file_path.suffix == ".md":
            assert chunk.page_marker is None
        elif chunk.file_path.suffix == ".pdf":
            assert chunk.breadcrumb is None
            assert chunk.page_marker is not None


def test_pdf_chunks_have_page_markers() -> None:
    page_one = "\n\n".join(" ".join(f"pageone{i}_{j}" for j in range(80)) for i in range(8))
    page_two = "\n\n".join(" ".join(f"pagetwo{i}_{j}" for j in range(80)) for i in range(8))
    chunks = list(chunk_document(raw_pdf(f"{page_one}\f{page_two}")))

    assert chunks
    assert all(chunk.page_marker is not None for chunk in chunks)
    assert {chunk.page_marker for chunk in chunks} >= {1, 2}
    assert all(chunk.breadcrumb is None for chunk in chunks)


def test_chunk_idx_resets_for_each_source_file() -> None:
    documents = [
        raw_markdown("# First\n\nA small policy.", file_path="first.md"),
        raw_pdf("A small PDF policy.", file_path="second.pdf"),
    ]

    chunks = list(chunk_documents(documents))

    assert [chunk.chunk_idx for chunk in chunks] == [0, 0]
    assert [chunk.file_path for chunk in chunks] == [Path("first.md"), Path("second.pdf")]
