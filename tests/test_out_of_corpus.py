from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.guardrails.out_of_corpus import OutOfCorpusDetector, OutOfCorpusJudgeError
from app.retrieval.models import RetrievedChunk


class FakeCompletions:
    def __init__(self, content: str) -> None:
        self.content = content

    def create(self, **kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=self.content),
                )
            ]
        )


class FakeClient:
    def __init__(self, content: str) -> None:
        self.chat = SimpleNamespace(completions=FakeCompletions(content))


def chunk(rrf_score: float) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id="chunk-1",
        source="opengov",
        file_path="policy.md",
        chunk_idx=0,
        breadcrumb=None,
        text="Relevant HR policy text.",
        dense_score=0.5,
        bm25_rank=1,
        rrf_score=rrf_score,
    )


@pytest.mark.parametrize(
    ("rrf_score", "judge_can_answer", "expected_refuse", "expected_disagree"),
    [
        (0.03, True, False, False),
        (0.03, False, False, True),
        (0.01, True, False, True),
        (0.01, False, True, False),
    ],
)
def test_out_of_corpus_truth_table(
    rrf_score: float,
    judge_can_answer: bool,
    expected_refuse: bool,
    expected_disagree: bool,
) -> None:
    detector = OutOfCorpusDetector(
        client=FakeClient(f'{{"can_answer": {str(judge_can_answer).lower()}}}'),
        deployment_name="gpt-4o",
    )

    decision = detector.decide("question", [chunk(rrf_score)])

    assert decision.score_signal_refuse is (rrf_score < 0.02)
    assert decision.judge_signal_refuse is (not judge_can_answer)
    assert decision.refuse is expected_refuse
    assert decision.signals_disagree is expected_disagree
    assert decision.max_rrf_score == rrf_score


def test_out_of_corpus_malformed_judge_json_raises() -> None:
    detector = OutOfCorpusDetector(
        client=FakeClient("not json"),
        deployment_name="gpt-4o",
    )

    with pytest.raises(OutOfCorpusJudgeError, match="malformed JSON"):
        detector.decide("question", [chunk(0.03)])


def test_out_of_corpus_ignores_extra_judge_fields() -> None:
    detector = OutOfCorpusDetector(
        client=FakeClient('{"can_answer": false, "reason": "not in policy"}'),
        deployment_name="gpt-4o",
    )

    decision = detector.decide("question", [chunk(0.01)])

    assert decision.refuse is True
