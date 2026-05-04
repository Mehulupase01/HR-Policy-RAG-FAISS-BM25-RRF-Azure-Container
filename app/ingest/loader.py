"""Load raw HR policy corpus files with explicit source attribution."""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

from app.ingest.models import DocumentFormat, RawDocument, Source


OPENGOV_FILES = frozenset(
    {
        "about-and-values.md",
        "equal-employment-policy.md",
        "harassment-policy.pdf",
        "reporting-violations-policy.md",
        "drug-and-alcohol-policy.md",
        "conflict-of-interest-policy.md",
        "professional-conduct-policy.md",
        "media-contact-policy.md",
        "payroll-policy.md",
        "health-insurance-coverage.md",
        "performance-assessments.md",
        "raises-and-bonuses.md",
        "expense-reimbursement-policy.pdf",
        "professional-development-policy.md",
        "work-schedule-policy.md",
        "vacation-and-leave-policy.md",
        "sick-leave-policy.md",
        "email-and-password-policy.md",
        "calendar-policy.md",
        "meetings-policy.md",
        "tools-and-services.md",
    }
)

MADETECH_FILES = frozenset(
    {
        "parental-leave-policy.pdf",
        "holiday-policy.pdf",
        "hybrid-working-policy.pdf",
        "flexible-working-policy.md",
        "sick-leave-procedures.md",
        "leave-types-overview.md",
        "raising-an-issue.md",
        "whistleblowing-policy.pdf",
        "pension-scheme.md",
        "equipment-and-work-ready-budget.pdf",
    }
)

SKIP_FILES = frozenset({"opengov-handbook-consolidated.pdf"})


class UnknownSourceError(ValueError):
    """Raised when a corpus file is not present in the explicit source mapping."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        super().__init__(f"Unknown corpus source for file: {self.path}")


class EmptyDocumentError(ValueError):
    """Raised when a known corpus file has no extractable text."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        super().__init__(f"No extractable text found in corpus file: {self.path}")


class CorpusLoader:
    """Load markdown and PDF corpus files from a local directory."""

    def __init__(self, corpus_root: Path | str) -> None:
        self.corpus_root = Path(corpus_root)

    def load_all(self) -> Iterator[RawDocument]:
        for path in sorted(self.corpus_root.iterdir(), key=lambda item: item.name):
            if not path.is_file():
                continue
            if path.name in SKIP_FILES:
                continue

            source = self._source_for(path)
            document_format = self._format_for(path)
            content = self._read_content(path, document_format)

            if not content.strip():
                raise EmptyDocumentError(path)

            yield RawDocument(
                file_path=path.relative_to(self.corpus_root),
                source=source,
                format=document_format,
                content=content,
            )

    def _source_for(self, path: Path) -> Source:
        if path.name in OPENGOV_FILES:
            return "opengov"
        if path.name in MADETECH_FILES:
            return "madetech"
        raise UnknownSourceError(path)

    def _format_for(self, path: Path) -> DocumentFormat:
        match path.suffix.lower():
            case ".md":
                return "md"
            case ".pdf":
                return "pdf"
            case _:
                raise UnknownSourceError(path)

    def _read_content(self, path: Path, document_format: DocumentFormat) -> str:
        match document_format:
            case "md":
                return path.read_text(encoding="utf-8")
            case "pdf":
                return self._read_pdf(path)

    def _read_pdf(self, path: Path) -> str:
        try:
            primary_text = self._read_pdf_with_pypdf(path)
        except Exception:
            primary_text = ""
        if primary_text.strip():
            return primary_text

        try:
            fallback_text = self._read_pdf_with_pdfminer(path)
        except Exception as exc:
            raise EmptyDocumentError(path) from exc
        if fallback_text.strip():
            return fallback_text

        raise EmptyDocumentError(path)

    def _read_pdf_with_pypdf(self, path: Path) -> str:
        from pypdf import PdfReader

        reader = PdfReader(path)
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    def _read_pdf_with_pdfminer(self, path: Path) -> str:
        from pdfminer.high_level import extract_text

        return extract_text(path)
