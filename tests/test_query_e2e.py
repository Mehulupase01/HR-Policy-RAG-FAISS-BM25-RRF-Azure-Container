from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.query import router as query_router
from app.generation.answerer import AnswerParseError
from app.generation.models import AnsweredQuery
from app.generation.prompts import REFUSAL_ANSWER
from app.models import Citation
from app.retrieval.models import RetrievedChunk


class FakeRetriever:
    def __init__(self, results: list[RetrievedChunk]) -> None:
        self.results = results
        self.calls: list[tuple[str, int]] = []

    def retrieve(self, question: str, top_k: int = 8) -> list[RetrievedChunk]:
        self.calls.append((question, top_k))
        return self.results


class FakeAnswerer:
    def __init__(self, result: AnsweredQuery | Exception) -> None:
        self.result = result
        self.calls: list[tuple[str, list[RetrievedChunk], int]] = []

    def answer(
        self,
        question: str,
        retrieved: list[RetrievedChunk],
        present_top_k: int = 4,
    ) -> AnsweredQuery:
        self.calls.append((question, retrieved, present_top_k))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def make_app(retriever: FakeRetriever, answerer: FakeAnswerer) -> FastAPI:
    app = FastAPI()
    app.include_router(query_router)
    app.state.retriever = retriever
    app.state.answerer = answerer
    return app


def chunk(rrf_score: float = 0.031) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id="chunk-1",
        source="opengov",
        file_path="sick-leave-policy.md",
        chunk_idx=0,
        breadcrumb="Leave > Sick leave",
        text="OpenGov sick leave policy text.",
        dense_score=0.7,
        bm25_rank=1,
        rrf_score=rrf_score,
    )


def test_query_returns_answer_and_citations() -> None:
    retrieved = [chunk(0.031), chunk(0.029)]
    citation = Citation(
        file_path="sick-leave-policy.md",
        source="opengov",
        chunk_idx=0,
        snippet="OpenGov sick leave policy text.",
    )
    retriever = FakeRetriever(retrieved)
    answerer = FakeAnswerer(
        AnsweredQuery(
            answer="You get sick leave according to the policy.",
            citations=[citation],
            retrieval_scores=None,
        )
    )
    client = TestClient(make_app(retriever, answerer))

    response = client.post("/query", json={"question": "How many sick days do I get?"})

    assert response.status_code == 200
    assert response.json() == {
        "answer": "You get sick leave according to the policy.",
        "citations": [citation.model_dump()],
        "retrieval_scores": [0.031, 0.029],
    }
    assert retriever.calls == [("How many sick days do I get?", 8)]
    assert answerer.calls == [("How many sick days do I get?", retrieved, 4)]


def test_query_empty_retrieval_returns_refusal() -> None:
    retriever = FakeRetriever([])
    answerer = FakeAnswerer(AnsweredQuery(answer="unused", citations=[]))
    client = TestClient(make_app(retriever, answerer))

    response = client.post("/query", json={"question": "What is the stock price?"})

    assert response.status_code == 200
    assert response.json() == {
        "answer": REFUSAL_ANSWER,
        "citations": [],
        "retrieval_scores": [],
    }
    assert answerer.calls == []


def test_query_answer_parse_error_returns_502() -> None:
    retriever = FakeRetriever([chunk()])
    answerer = FakeAnswerer(AnswerParseError("bad json"))
    client = TestClient(make_app(retriever, answerer))

    response = client.post("/query", json={"question": "How many sick days do I get?"})

    assert response.status_code == 502
    assert response.json()["detail"] == "Azure OpenAI returned an invalid answer payload."
