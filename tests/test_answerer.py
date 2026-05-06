from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.generation.answerer import AnswerParseError, Answerer
from app.generation.prompts import DISAGREEMENT_INSTRUCTION
from app.generation.prompts import SYSTEM_PROMPT_V1
from app.retrieval.models import RetrievedChunk


class FakeCompletions:
    def __init__(self, content: str, finish_reason: str = "stop") -> None:
        self.content = content
        self.finish_reason = finish_reason
        self.kwargs: dict[str, object] | None = None

    def create(self, **kwargs: object) -> SimpleNamespace:
        self.kwargs = kwargs
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason=self.finish_reason,
                    message=SimpleNamespace(content=self.content),
                )
            ]
        )


class FakeClient:
    def __init__(self, content: str, finish_reason: str = "stop") -> None:
        self.completions = FakeCompletions(content, finish_reason)
        self.chat = SimpleNamespace(completions=self.completions)


def retrieved_chunk(
    *,
    file_path: str = "sick-leave-policy.md",
    chunk_idx: int = 3,
    source: str = "opengov",
    text: str = "Employees receive sick leave under the policy.",
) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=f"{file_path}-{chunk_idx}",
        source=source,  # type: ignore[arg-type]
        file_path=file_path,
        chunk_idx=chunk_idx,
        breadcrumb="Leave > Sick leave",
        text=text,
        dense_score=0.72,
        bm25_rank=1,
        rrf_score=0.032,
    )


def madetech_chunk() -> RetrievedChunk:
    return retrieved_chunk(
        file_path="sick-leave-procedures.md",
        chunk_idx=0,
        source="madetech",
        text="Made Tech sick leave procedure text.",
    )


def test_answer_returns_valid_citations() -> None:
    client = FakeClient(
        '{"answer":"Employees receive sick leave. sick-leave-policy.md#3",'
        '"citation_keys":["sick-leave-policy.md#3"]}'
    )
    answerer = Answerer(client=client, deployment_name="gpt-4o")

    result = answerer.answer("How many sick days?", [retrieved_chunk()])

    assert result.answer == "Employees receive sick leave. sick-leave-policy.md#3"
    assert len(result.citations) == 1
    assert result.citations[0].file_path == "sick-leave-policy.md"
    assert result.citations[0].source == "opengov"
    assert result.citations[0].chunk_idx == 3
    assert result.retrieval_scores == [0.032]
    assert client.completions.kwargs is not None
    assert client.completions.kwargs["model"] == "gpt-4o"
    assert client.completions.kwargs["response_format"] == {"type": "json_object"}
    assert client.completions.kwargs["temperature"] == 0.0
    messages = client.completions.kwargs["messages"]
    assert isinstance(messages, list)
    assert messages[0] == {"role": "system", "content": SYSTEM_PROMPT_V1}


def test_refusal_returns_empty_citations() -> None:
    refusal = (
        "I don't have information about that in our HR policies. "
        "You may want to consult your manager or HR directly."
    )
    client = FakeClient(f'{{"answer":"{refusal}","citation_keys":[]}}')
    answerer = Answerer(client=client, deployment_name="gpt-4o")

    result = answerer.answer("What is the stock price?", [retrieved_chunk()])

    assert result.answer == refusal
    assert result.citations == []


def test_surface_disagreement_prepends_disagreement_instruction() -> None:
    client = FakeClient(
        '{"answer":"Per OpenGov... Per Made Tech...",'
        '"citation_keys":["sick-leave-policy.md#3"]}'
    )
    answerer = Answerer(client=client, deployment_name="gpt-4o")

    answerer.answer(
        "How do sick leave policies differ?",
        [retrieved_chunk()],
        surface_disagreement=True,
    )

    assert client.completions.kwargs is not None
    messages = client.completions.kwargs["messages"]
    assert isinstance(messages, list)
    assert messages[0]["content"].startswith(DISAGREEMENT_INSTRUCTION)


def test_surface_disagreement_presents_both_sources_when_one_is_lower_ranked() -> None:
    client = FakeClient(
        '{"answer":"Per OpenGov... Per Made Tech...",'
        '"citation_keys":["sick-leave-policy.md#3","sick-leave-procedures.md#0"]}'
    )
    answerer = Answerer(client=client, deployment_name="gpt-4o")

    result = answerer.answer(
        "How do the policies differ?",
        [
            retrieved_chunk(text="OpenGov top chunk."),
            retrieved_chunk(file_path="calendar-policy.md", chunk_idx=0, text="Another OpenGov chunk."),
            retrieved_chunk(file_path="meetings-policy.md", chunk_idx=0, text="Third OpenGov chunk."),
            madetech_chunk(),
        ],
        present_top_k=3,
        surface_disagreement=True,
    )

    assert [citation.source for citation in result.citations] == ["opengov", "madetech"]
    assert client.completions.kwargs is not None
    user_message = client.completions.kwargs["messages"][1]["content"]
    assert "sick-leave-policy.md#3" in user_message
    assert "sick-leave-procedures.md#0" in user_message


def test_hallucinated_citation_is_dropped(caplog: pytest.LogCaptureFixture) -> None:
    client = FakeClient(
        '{"answer":"Use the actual cited policy.",'
        '"citation_keys":["sick-leave-policy.md#3","made-up.md#99"]}'
    )
    answerer = Answerer(client=client, deployment_name="gpt-4o")

    result = answerer.answer("How many sick days?", [retrieved_chunk()])

    assert [citation.file_path for citation in result.citations] == ["sick-leave-policy.md"]
    assert "Dropping hallucinated citation key" in caplog.text


def test_malformed_json_raises_clearly() -> None:
    answerer = Answerer(client=FakeClient("not json"), deployment_name="gpt-4o")

    with pytest.raises(AnswerParseError, match="malformed answer JSON"):
        answerer.answer("How many sick days?", [retrieved_chunk()])


def test_truncated_json_raises_clearly() -> None:
    answerer = Answerer(
        client=FakeClient('{"answer":"partial"', finish_reason="length"),
        deployment_name="gpt-4o",
    )

    with pytest.raises(AnswerParseError, match="truncated answer JSON"):
        answerer.answer("How many sick days?", [retrieved_chunk()])
