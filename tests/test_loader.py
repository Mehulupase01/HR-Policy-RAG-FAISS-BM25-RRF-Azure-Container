from __future__ import annotations

from pathlib import Path

import pytest

from app.ingest.loader import (
    MADETECH_FILES,
    OPENGOV_FILES,
    SKIP_FILES,
    CorpusLoader,
    UnknownSourceError,
)
from app.ingest.models import RawDocument


CORPUS_ROOT = Path(__file__).resolve().parents[1] / "corpus"


def load_by_name() -> dict[str, RawDocument]:
    return {document.file_path.name: document for document in CorpusLoader(CORPUS_ROOT).load_all()}


def test_load_all_returns_expected_document_count() -> None:
    documents = list(CorpusLoader(CORPUS_ROOT).load_all())

    assert len(documents) == 31
    assert "opengov-handbook-consolidated.pdf" not in {doc.file_path.name for doc in documents}
    assert all(not document.file_path.is_absolute() for document in documents)


def test_source_attribution_for_spot_checked_markdown_and_pdf_files() -> None:
    documents = load_by_name()

    assert documents["sick-leave-policy.md"].source == "opengov"
    assert documents["harassment-policy.pdf"].source == "opengov"
    assert documents["sick-leave-procedures.md"].source == "madetech"
    assert documents["holiday-policy.pdf"].source == "madetech"


def test_explicit_source_mapping_matches_real_corpus_files() -> None:
    corpus_files = {path.name for path in CORPUS_ROOT.iterdir() if path.is_file()}
    mapped_files = OPENGOV_FILES | MADETECH_FILES

    assert OPENGOV_FILES.isdisjoint(MADETECH_FILES)
    assert SKIP_FILES == frozenset({"opengov-handbook-consolidated.pdf"})
    assert corpus_files == mapped_files | SKIP_FILES
    assert mapped_files <= corpus_files


def test_unknown_file_raises_unknown_source_error(tmp_path: Path) -> None:
    (tmp_path / "mystery-policy.md").write_text("# Mystery\n", encoding="utf-8")

    with pytest.raises(UnknownSourceError) as exc_info:
        list(CorpusLoader(tmp_path).load_all())

    assert exc_info.value.path == tmp_path / "mystery-policy.md"


def test_every_loaded_pdf_yields_non_trivial_content() -> None:
    pdf_documents = [
        document for document in CorpusLoader(CORPUS_ROOT).load_all() if document.format == "pdf"
    ]

    assert len(pdf_documents) == 7
    for document in pdf_documents:
        assert len(document.content.strip()) > 100


def test_pdf_reader_falls_back_when_primary_extraction_is_empty(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "harassment-policy.pdf"
    pdf_path.write_bytes(b"%PDF placeholder")

    monkeypatch.setattr(CorpusLoader, "_read_pdf_with_pypdf", lambda self, path: "")
    monkeypatch.setattr(
        CorpusLoader,
        "_read_pdf_with_pdfminer",
        lambda self, path: "fallback extracted policy text",
    )

    document = next(CorpusLoader(tmp_path).load_all())

    assert document.source == "opengov"
    assert document.format == "pdf"
    assert document.content == "fallback extracted policy text"


def test_pdf_reader_falls_back_when_primary_extraction_raises(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "holiday-policy.pdf"
    pdf_path.write_bytes(b"%PDF placeholder")

    def raise_primary_error(self: CorpusLoader, path: Path) -> str:
        raise RuntimeError("primary extraction failed")

    monkeypatch.setattr(CorpusLoader, "_read_pdf_with_pypdf", raise_primary_error)
    monkeypatch.setattr(
        CorpusLoader,
        "_read_pdf_with_pdfminer",
        lambda self, path: "fallback extracted holiday policy text",
    )

    document = next(CorpusLoader(tmp_path).load_all())

    assert document.source == "madetech"
    assert document.file_path == Path("holiday-policy.pdf")
    assert document.content == "fallback extracted holiday policy text"
