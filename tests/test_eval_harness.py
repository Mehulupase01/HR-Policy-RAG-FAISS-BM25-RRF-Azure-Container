from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.query import router as query_router
from app.generation.models import AnsweredQuery
from app.guardrails.disagreement import DisagreementInfo
from app.guardrails.out_of_corpus import OutOfCorpusDecision
from app.models import Citation
from app.retrieval.models import RetrievedChunk
from eval.run_eval import APIResult, FaithfulnessResult, run_evaluation


class FakeRetriever:
    def retrieve(self, question: str, top_k: int = 8) -> list[RetrievedChunk]:
        _ = (question, top_k)
        return [
            RetrievedChunk(
                chunk_id="chunk-1",
                source="opengov",
                file_path="email-and-password-policy.md",
                chunk_idx=0,
                breadcrumb=None,
                text="Use organizational email for work.",
                dense_score=0.7,
                bm25_rank=1,
                rrf_score=0.031,
            )
        ]


class FakeAnswerer:
    def answer(
        self,
        question: str,
        retrieved: list[RetrievedChunk],
        present_top_k: int = 4,
        surface_disagreement: bool = False,
    ) -> AnsweredQuery:
        _ = (retrieved, present_top_k, surface_disagreement)
        if "stock price" in question.lower():
            return AnsweredQuery(
                answer=(
                    "I don't have information about that in our HR policies. "
                    "You may want to consult your manager or HR directly."
                ),
                citations=[],
            )
        return AnsweredQuery(
            answer="Use the organizational email account for work messages.",
            citations=[
                Citation(
                    file_path="email-and-password-policy.md",
                    source="opengov",
                    chunk_idx=0,
                    snippet="Use organizational email for work.",
                )
            ],
        )


class FakeOutOfCorpusDetector:
    def decide(
        self,
        question: str,
        retrieved: list[RetrievedChunk],
        *,
        present_top_k: int = 4,
    ) -> OutOfCorpusDecision:
        _ = (retrieved, present_top_k)
        should_refuse = "stock price" in question.lower()
        return OutOfCorpusDecision(
            score_signal_refuse=should_refuse,
            judge_signal_refuse=should_refuse,
            refuse=should_refuse,
            signals_disagree=False,
            max_rrf_score=0.031,
        )


class FakeDisagreementDetector:
    def detect(self, retrieved: list[RetrievedChunk]) -> DisagreementInfo:
        _ = retrieved
        return DisagreementInfo(
            multi_source=False,
            topic_overlap_score=None,
            surface_disagreement=False,
        )


@pytest.fixture()
def eval_test_set_path(tmp_path: Path) -> Path:
    test_set = [
        {
            "id": "T01",
            "category": "single_source_factual",
            "question": "Can I use personal email?",
            "expected_behavior": "Should cite email policy.",
            "expected_citations_contain": ["email-and-password-policy.md"],
            "expected_refusal": False,
            "expected_surfaces_both_sources": False,
        },
        {
            "id": "T02",
            "category": "clearly_out_of_corpus",
            "question": "What is the company stock price?",
            "expected_behavior": "Should refuse.",
            "expected_citations_contain": None,
            "expected_refusal": True,
            "expected_surfaces_both_sources": False,
        },
    ]
    path = tmp_path / "test_set.json"
    path.write_text(json.dumps(test_set), encoding="utf-8")
    return path


@pytest.fixture()
def test_client() -> TestClient:
    app = FastAPI()
    app.include_router(query_router)
    app.state.retriever = FakeRetriever()
    app.state.answerer = FakeAnswerer()
    app.state.out_of_corpus_detector = FakeOutOfCorpusDetector()
    app.state.disagreement_detector = FakeDisagreementDetector()
    return TestClient(app)


def test_eval_harness_writes_results_and_report(
    tmp_path: Path,
    eval_test_set_path: Path,
    test_client: TestClient,
) -> None:
    def post_query(question: str, case_id: str) -> APIResult:
        _ = case_id
        response = test_client.post("/query", json={"question": question})
        return APIResult(
            status_code=response.status_code,
            payload=response.json(),
            latency_ms=12.0,
        )

    def faithfulness_judge(question: str, answer: str, context: str) -> FaithfulnessResult:
        _ = (question, answer, context)
        return FaithfulnessResult(score=1.0, reasoning="Supported by cited context.")

    out_path = tmp_path / "results.json"
    report_path = tmp_path / "results.md"

    output = run_evaluation(
        base_url="http://testserver",
        test_set_path=eval_test_set_path,
        out_path=out_path,
        report_path=report_path,
        faithfulness_judge=faithfulness_judge,
        post_query=post_query,
    )

    assert output["aggregates"]["overall"]["case_count"] == 2
    assert out_path.exists()
    report = report_path.read_text(encoding="utf-8")
    expected_sections = [
        "# RAG Evaluation Results",
        "## Configuration",
        "## Quality Bar",
        "## Summary By Category",
        "## Met / Missed",
        "## Worst-Performing Five Cases",
        "## Methodology",
        "## Reproduce",
    ]
    for section in expected_sections:
        assert section in report
