from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.query import router as query_router
from app.generation.answerer import AnswerParseError
from app.generation.models import AnsweredQuery
from app.generation.prompts import LIMITED_INFORMATION_PREFIX, REFUSAL_ANSWER
from app.guardrails.disagreement import DisagreementInfo
from app.guardrails.out_of_corpus import OutOfCorpusDecision
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
        self.calls: list[tuple[str, list[RetrievedChunk], int, bool]] = []

    def answer(
        self,
        question: str,
        retrieved: list[RetrievedChunk],
        present_top_k: int = 4,
        surface_disagreement: bool = False,
    ) -> AnsweredQuery:
        self.calls.append((question, retrieved, present_top_k, surface_disagreement))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class FakeOutOfCorpusDetector:
    def __init__(self, decision: OutOfCorpusDecision | None = None) -> None:
        self.decision = decision or OutOfCorpusDecision(
            score_signal_refuse=False,
            judge_signal_refuse=False,
            refuse=False,
            signals_disagree=False,
            max_rrf_score=0.031,
        )
        self.calls: list[tuple[str, list[RetrievedChunk], int]] = []

    def decide(
        self,
        question: str,
        retrieved: list[RetrievedChunk],
        *,
        present_top_k: int = 4,
    ) -> OutOfCorpusDecision:
        self.calls.append((question, retrieved, present_top_k))
        return self.decision


class FakeDisagreementDetector:
    def __init__(self, info: DisagreementInfo | None = None) -> None:
        self.info = info or DisagreementInfo(
            multi_source=False,
            topic_overlap_score=None,
            surface_disagreement=False,
        )
        self.calls: list[list[RetrievedChunk]] = []

    def detect(self, retrieved: list[RetrievedChunk]) -> DisagreementInfo:
        self.calls.append(retrieved)
        return self.info


def make_app(
    retriever: FakeRetriever,
    answerer: FakeAnswerer,
    out_of_corpus_detector: FakeOutOfCorpusDetector | None = None,
    disagreement_detector: FakeDisagreementDetector | None = None,
) -> FastAPI:
    app = FastAPI()
    app.include_router(query_router)
    app.state.retriever = retriever
    app.state.answerer = answerer
    app.state.out_of_corpus_detector = out_of_corpus_detector or FakeOutOfCorpusDetector()
    app.state.disagreement_detector = disagreement_detector or FakeDisagreementDetector()
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
    assert answerer.calls == [("How many sick days do I get?", retrieved, 4, False)]


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


def test_query_out_of_corpus_refusal_short_circuits_answerer() -> None:
    retrieved = [chunk()]
    retriever = FakeRetriever(retrieved)
    answerer = FakeAnswerer(AnsweredQuery(answer="unused", citations=[]))
    out_of_corpus_detector = FakeOutOfCorpusDetector(
        OutOfCorpusDecision(
            score_signal_refuse=True,
            judge_signal_refuse=True,
            refuse=True,
            signals_disagree=False,
            max_rrf_score=0.01,
        )
    )
    client = TestClient(make_app(retriever, answerer, out_of_corpus_detector))

    response = client.post("/query", json={"question": "What is the stock price?"})

    assert response.status_code == 200
    assert response.json() == {
        "answer": REFUSAL_ANSWER,
        "citations": [],
        "retrieval_scores": [0.031],
    }
    assert answerer.calls == []


def test_query_hedges_when_out_of_corpus_signals_disagree() -> None:
    retrieved = [chunk()]
    retriever = FakeRetriever(retrieved)
    answerer = FakeAnswerer(
        AnsweredQuery(answer="The policy mentions sick leave.", citations=[])
    )
    out_of_corpus_detector = FakeOutOfCorpusDetector(
        OutOfCorpusDecision(
            score_signal_refuse=True,
            judge_signal_refuse=False,
            refuse=False,
            signals_disagree=True,
            max_rrf_score=0.01,
        )
    )
    client = TestClient(make_app(retriever, answerer, out_of_corpus_detector))

    response = client.post("/query", json={"question": "Tell me about sick leave."})

    assert response.status_code == 200
    assert response.json()["answer"].startswith(LIMITED_INFORMATION_PREFIX)


def test_query_does_not_hedge_exact_refusal() -> None:
    retrieved = [chunk()]
    retriever = FakeRetriever(retrieved)
    answerer = FakeAnswerer(
        AnsweredQuery(answer=REFUSAL_ANSWER, citations=[])
    )
    out_of_corpus_detector = FakeOutOfCorpusDetector(
        OutOfCorpusDecision(
            score_signal_refuse=False,
            judge_signal_refuse=True,
            refuse=False,
            signals_disagree=True,
            max_rrf_score=0.03,
        )
    )
    client = TestClient(make_app(retriever, answerer, out_of_corpus_detector))

    response = client.post("/query", json={"question": "What is the stock price?"})

    assert response.status_code == 200
    assert response.json()["answer"] == REFUSAL_ANSWER


def test_query_passes_disagreement_flag_to_answerer() -> None:
    retrieved = [chunk()]
    retriever = FakeRetriever(retrieved)
    answerer = FakeAnswerer(
        AnsweredQuery(answer="Per OpenGov... Per Made Tech...", citations=[])
    )
    disagreement_detector = FakeDisagreementDetector(
        DisagreementInfo(
            multi_source=True,
            topic_overlap_score=0.9,
            surface_disagreement=True,
        )
    )
    client = TestClient(
        make_app(
            retriever,
            answerer,
            disagreement_detector=disagreement_detector,
        )
    )

    response = client.post("/query", json={"question": "Compare sick leave."})

    assert response.status_code == 200
    assert answerer.calls == [("Compare sick leave.", retrieved, 4, True)]


def test_query_answer_parse_error_returns_502() -> None:
    retriever = FakeRetriever([chunk()])
    answerer = FakeAnswerer(AnswerParseError("bad json"))
    client = TestClient(make_app(retriever, answerer))

    response = client.post("/query", json={"question": "How many sick days do I get?"})

    assert response.status_code == 502
    assert response.json()["detail"] == "Azure OpenAI returned an invalid answer payload."
