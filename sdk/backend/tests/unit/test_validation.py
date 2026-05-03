"""Unit tests for blob upload validation."""

from blob_client.validation import MAX_FILE_SIZE_BYTES, validate_upload


def test_valid_pdf_upload():
    result = validate_upload("report.pdf", 1024, "application/pdf")
    assert result.valid is True


def test_valid_csv_upload():
    result = validate_upload("data.csv", 512, "text/csv")
    assert result.valid is True


def test_reject_oversized_file():
    result = validate_upload("huge.pdf", MAX_FILE_SIZE_BYTES + 1, "application/pdf")
    assert result.valid is False
    assert result.status_code == 413


def test_reject_unsupported_extension():
    result = validate_upload("image.png", 1024, "image/png")
    assert result.valid is False
    assert result.status_code == 415


def test_reject_unsupported_content_type():
    result = validate_upload("file.pdf", 1024, "image/jpeg")
    assert result.valid is False
    assert result.status_code == 415
