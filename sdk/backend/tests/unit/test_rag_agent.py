"""Unit tests for the RAG agent core logic."""

from agent.rag_agent import (
    AgentResult,
    ChatMessage,
    IDK_RESPONSE,
    NullRetriever,
    RetrievalResult,
    generate_reply,
)


class FakeRetriever:
    def __init__(self, results):
        self._results = results

    def retrieve(self, question, chat_history):
        return self._results


def test_generate_reply_no_retriever_returns_fallback():
    result = generate_reply("What is AI?")
    assert result.is_fallback is True
    assert result.reply == IDK_RESPONSE


def test_generate_reply_with_results_no_llm():
    retriever = FakeRetriever([
        RetrievalResult(text="AI is artificial intelligence.", score=0.9, source="doc.pdf"),
    ])
    result = generate_reply("What is AI?", retriever=retriever)
    assert result.is_fallback is True
    assert "AI is artificial intelligence" in result.reply


def test_generate_reply_with_llm():
    retriever = FakeRetriever([
        RetrievalResult(text="Context about AI.", score=0.8, source="ai.pdf"),
    ])

    def fake_llm(question, context, history):
        return "AI stands for Artificial Intelligence."

    result = generate_reply("What is AI?", retriever=retriever, llm=fake_llm)
    assert result.is_fallback is False
    assert result.reply == "AI stands for Artificial Intelligence."
    assert "ai.pdf" in result.sources


def test_generate_reply_empty_question_raises():
    try:
        generate_reply("")
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


def test_below_threshold_fallback():
    retriever = FakeRetriever([
        RetrievalResult(text="Low score result.", score=0.1, source="low.pdf"),
    ])
    result = generate_reply("test?", retriever=retriever, similarity_threshold=0.5)
    assert result.is_fallback is True
    assert "Low score result" in result.reply
