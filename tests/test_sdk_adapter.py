from __future__ import annotations

from app.retrieval.models import RetrievedChunk
from app.retrieval.sdk_adapter import SDKRetrieverAdapter


class FakeHybridRetriever:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    def retrieve(self, question: str, top_k: int = 8) -> list[RetrievedChunk]:
        self.calls.append((question, top_k))
        return [
            RetrievedChunk(
                chunk_id="chunk-1",
                source="madetech",
                file_path="sick-leave-procedures.md",
                chunk_idx=0,
                breadcrumb=None,
                text="Made Tech sick leave text",
                dense_score=0.61,
                bm25_rank=2,
                rrf_score=0.031,
            )
        ]


def test_sdk_adapter_exposes_hybrid_retriever_as_sdk_results() -> None:
    retriever = FakeHybridRetriever()
    adapter = SDKRetrieverAdapter(retriever=retriever, top_k=4)  # type: ignore[arg-type]

    results = adapter.retrieve("How many sick days?", chat_history=[])

    assert retriever.calls == [("How many sick days?", 4)]
    assert len(results) == 1
    assert results[0].text == "Made Tech sick leave text"
    assert results[0].score == 0.61
    assert results[0].source == "sick-leave-procedures.md#0"
