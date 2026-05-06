"""Run the RAG evaluation set against a local or deployed API.

Example:
    python -m eval.run_eval --base-url http://127.0.0.1:8000 --test-set eval/test_set.json --out eval/results.json --report eval/results.md
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import os
import statistics
import time
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import pandas as pd
from dotenv import load_dotenv
from openai import AzureOpenAI
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from eval.judge_prompts import FAITHFULNESS_JUDGE

logger = logging.getLogger(__name__)
DEFAULT_CONTEXT_INDEX = Path("data/index")
QUALITY_BARS = {
    "mean_recall": 0.85,
    "refusal_accuracy": 0.90,
    "surfaces_both_rate": 0.75,
    "mean_faithfulness": 0.80,
}
REFUSAL_MARKERS = (
    "i don't have information",
    "consult your manager",
    "not in our hr policies",
)


class FaithfulnessJudgeError(ValueError):
    """Raised when the faithfulness judge returns invalid output."""


class _FaithfulnessPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    score: float = Field(ge=0.0, le=1.0)
    reasoning: str


@dataclass(frozen=True)
class APIResult:
    status_code: int
    payload: dict[str, Any]
    latency_ms: float


@dataclass(frozen=True)
class FaithfulnessResult:
    score: float
    reasoning: str


class ContextResolver:
    """Resolve cited chunks to full text when local index artifacts are available."""

    def __init__(self, index_dir: Path | None) -> None:
        self._chunk_text_by_key: dict[str, str] = {}
        if index_dir is None:
            return
        parquet_path = index_dir / "embeddings.parquet"
        if not parquet_path.exists():
            return
        dataframe = pd.read_parquet(
            parquet_path, columns=["file_path", "chunk_idx", "text"]
        )
        self._chunk_text_by_key = {
            f"{row.file_path}#{int(row.chunk_idx)}": str(row.text)
            for row in dataframe.itertuples(index=False)
        }

    def context_from_citations(self, citations: Any) -> str:
        if not isinstance(citations, list):
            return ""
        parts: list[str] = []
        for citation in citations:
            if not isinstance(citation, dict):
                continue
            key = f"{citation.get('file_path', '')}#{citation.get('chunk_idx', '')}"
            source = citation.get("source", "")
            text = self._chunk_text_by_key.get(key) or citation.get("snippet", "")
            parts.append(f"{key} ({source}): {text}")
        return "\n".join(parts)


PostQuery = Callable[[str, str], APIResult]
FaithfulnessJudge = Callable[[str, str, str], FaithfulnessResult]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run HR RAG evaluation cases.")
    parser.add_argument(
        "--base-url",
        required=True,
        help="Base API URL, for example http://127.0.0.1:8000",
    )
    parser.add_argument("--test-set", required=True, help="Path to eval/test_set.json")
    parser.add_argument(
        "--out", required=True, help="Path for structured raw results JSON"
    )
    parser.add_argument(
        "--report", required=True, help="Path for human-readable markdown report"
    )
    parser.add_argument(
        "--context-index",
        default=str(DEFAULT_CONTEXT_INDEX),
        help="Optional local index dir used to resolve full cited chunk text for faithfulness judging.",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    load_dotenv()
    judge = make_azure_faithfulness_judge()
    result = run_evaluation(
        base_url=args.base_url,
        test_set_path=Path(args.test_set),
        out_path=Path(args.out),
        report_path=Path(args.report),
        context_index_path=Path(args.context_index) if args.context_index else None,
        faithfulness_judge=judge,
    )
    logger.info("Wrote raw results to %s", result["output_path"])
    logger.info("Wrote report to %s", result["report_path"])
    return 0


def run_evaluation(
    *,
    base_url: str,
    test_set_path: Path,
    out_path: Path,
    report_path: Path,
    faithfulness_judge: FaithfulnessJudge,
    post_query: PostQuery | None = None,
    context_index_path: Path | None = DEFAULT_CONTEXT_INDEX,
) -> dict[str, Any]:
    test_set_bytes = test_set_path.read_bytes()
    test_set_hash = hashlib.sha256(test_set_bytes).hexdigest()
    cases = json.loads(test_set_bytes.decode("utf-8"))
    if not isinstance(cases, list):
        raise ValueError("test set must be a JSON array")

    poster = post_query or make_http_post_query(base_url)
    context_resolver = ContextResolver(context_index_path)
    model_versions = model_versions_from_env()
    raw_cases: list[dict[str, Any]] = []
    for case in cases:
        raw_cases.append(
            _run_case(case, base_url, poster, faithfulness_judge, context_resolver)
        )

    aggregates = aggregate_results(raw_cases)
    output = {
        "config": {
            "base_url": base_url,
            "test_set": str(test_set_path),
            "test_set_sha256": test_set_hash,
            "model_versions": model_versions,
            "quality_bars": QUALITY_BARS,
            "context_index": str(context_index_path) if context_index_path else None,
        },
        "aggregates": aggregates,
        "cases": raw_cases,
        "output_path": str(out_path),
        "report_path": str(report_path),
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    report_path.write_text(
        render_report(output, report_path=report_path, test_set_path=test_set_path),
        encoding="utf-8",
    )
    return output


def make_http_post_query(base_url: str) -> PostQuery:
    clean_base_url = base_url.rstrip("/")

    def post_query(question: str, case_id: str) -> APIResult:
        _ = case_id
        start = time.perf_counter()
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                f"{clean_base_url}/query", json={"question": question}
            )
        latency_ms = (time.perf_counter() - start) * 1000.0
        try:
            payload = response.json()
        except ValueError:
            payload = {"raw_text": response.text}
        return APIResult(
            status_code=response.status_code, payload=payload, latency_ms=latency_ms
        )

    return post_query


def make_azure_faithfulness_judge() -> FaithfulnessJudge:
    client = AzureOpenAI(
        api_key=_required_env("AZURE_OPENAI_KEY"),
        azure_endpoint=_required_env("AZURE_OPENAI_ENDPOINT"),
        api_version=_required_env("AZURE_OPENAI_API_VERSION"),
    )
    deployment_name = _required_env("AZURE_OPENAI_CHAT_DEPLOYMENT")

    def judge(question: str, answer: str, context: str) -> FaithfulnessResult:
        response = client.chat.completions.create(
            model=deployment_name,
            messages=[
                {"role": "system", "content": FAITHFULNESS_JUDGE},
                {
                    "role": "user",
                    "content": _faithfulness_user_message(question, answer, context),
                },
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
            max_tokens=300,
        )
        content = getattr(response.choices[0].message, "content", None)
        if not content:
            raise FaithfulnessJudgeError(
                "Faithfulness judge returned an empty response"
            )
        try:
            payload = _FaithfulnessPayload.model_validate_json(content)
        except ValidationError as exc:
            raise FaithfulnessJudgeError(
                "Faithfulness judge returned malformed JSON"
            ) from exc
        return FaithfulnessResult(score=payload.score, reasoning=payload.reasoning)

    return judge


def _run_case(
    case: dict[str, Any],
    base_url: str,
    post_query: PostQuery,
    faithfulness_judge: FaithfulnessJudge,
    context_resolver: ContextResolver,
) -> dict[str, Any]:
    api_result = post_query(str(case["question"]), str(case["id"]))
    payload = api_result.payload
    answer = _extract_answer(payload)
    citations = (
        payload.get("citations") if isinstance(payload.get("citations"), list) else []
    )
    citation_paths = [
        str(citation.get("file_path", ""))
        for citation in citations
        if isinstance(citation, dict)
    ]
    context = context_resolver.context_from_citations(citations)
    expected_citations = case.get("expected_citations_contain")
    recall = _retrieval_recall(expected_citations, citation_paths)
    detected_refusal = _is_refusal(answer)
    refusal_match = detected_refusal == bool(case["expected_refusal"])
    detected_surfaces_both = _surfaces_both_sources(answer)
    surfaces_both_match = (
        detected_surfaces_both
        if bool(case["expected_surfaces_both_sources"])
        else not detected_surfaces_both
    )

    faithfulness: dict[str, Any] | None = None
    if not bool(case["expected_refusal"]) and api_result.status_code < 400:
        try:
            judged = faithfulness_judge(str(case["question"]), answer, context)
            faithfulness = {
                "score": judged.score,
                "reasoning": judged.reasoning,
                "error": None,
            }
        except Exception as exc:  # noqa: BLE001 - preserve per-case eval failures.
            faithfulness = {
                "score": None,
                "reasoning": "",
                "error": f"{type(exc).__name__}: {exc}",
            }

    error = api_result.status_code >= 400
    return {
        "id": case["id"],
        "category": case["category"],
        "question": case["question"],
        "expected_behavior": case["expected_behavior"],
        "expected_citations_contain": expected_citations,
        "expected_refusal": case["expected_refusal"],
        "expected_surfaces_both_sources": case["expected_surfaces_both_sources"],
        "http_status": api_result.status_code,
        "latency_ms": api_result.latency_ms,
        "answer": answer,
        "citations": citations,
        "retrieval_scores": payload.get("retrieval_scores"),
        "metrics": {
            "retrieval_recall": recall,
            "detected_refusal": detected_refusal,
            "refusal_match": refusal_match,
            "detected_surfaces_both_sources": detected_surfaces_both,
            "surfaces_both_match": surfaces_both_match,
            "faithfulness": faithfulness,
            "error": error,
        },
    }


def aggregate_results(cases: list[dict[str, Any]]) -> dict[str, Any]:
    by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in cases:
        by_category[str(case["category"])].append(case)

    categories = {
        category: _aggregate_group(group)
        for category, group in sorted(by_category.items())
    }
    return {
        "overall": _aggregate_group(cases),
        "by_category": categories,
    }


def render_report(
    output: dict[str, Any], *, report_path: Path, test_set_path: Path
) -> str:
    config = output["config"]
    overall = output["aggregates"]["overall"]
    categories = output["aggregates"]["by_category"]
    lines = [
        "# RAG Evaluation Results",
        "",
        "## Configuration",
        "",
        "```text",
        f"base_url: {config['base_url']}",
        f"test_set: {test_set_path}",
        f"test_set_sha256: {config['test_set_sha256']}",
        f"chat_deployment: {config['model_versions']['chat_deployment']}",
        f"embedding_deployment: {config['model_versions']['embedding_deployment']}",
        f"azure_openai_api_version: {config['model_versions']['azure_openai_api_version']}",
        f"context_index: {config['context_index']}",
        "```",
        "",
        "## Quality Bar",
        "",
        "- recall >= 0.85",
        "- refusal >= 0.90",
        "- surfaces-both >= 0.75",
        "- mean faithfulness >= 0.80",
        "",
        "## Summary By Category",
        "",
        "| Category | Cases | Mean Recall | Refusal Accuracy | Surfaces-Both Rate | Mean Faithfulness | Mean Latency ms | P95 Latency ms | Error Rate |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for category, metrics in categories.items():
        lines.append(_summary_row(category, metrics))
    lines.extend(
        [
            _summary_row("overall", overall),
            "",
            "## Met / Missed",
            "",
        ]
    )
    lines.extend(_met_missed_lines(overall))
    lines.extend(
        [
            "",
            "## Worst-Performing Five Cases",
            "",
        ]
    )
    for case in worst_cases(output["cases"], limit=5):
        lines.extend(
            [
                f"### {case['id']} ({case['category']})",
                "",
                f"Question: {case['question']!r}",
                "",
                f"Diagnosis: {_diagnose_case(case)}",
                "",
            ]
        )
    lines.extend(
        [
            "## Methodology",
            "",
            "This harness posts each test case to `/query`, records latency/status/payload, computes deterministic checks for retrieval recall, refusal matching, and both-source surfacing, and uses a strict GPT-4o judge for faithfulness on non-refusal cases.",
            "",
            "Known limitations: LLM-judge scores can reflect length preference, self-preference, and single-axis grading bias. Refusal detection uses string matching and can miss alternative refusal phrasings. The sample is only 40 cases, so it is useful for regression and qualitative coverage but not statistically significant.",
            "",
            "## Reproduce",
            "",
            "```bash",
            f"python -m eval.run_eval --base-url {config['base_url']} --test-set {test_set_path} --out {output['output_path']} --report {report_path}",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def worst_cases(cases: list[dict[str, Any]], *, limit: int = 5) -> list[dict[str, Any]]:
    return sorted(cases, key=_case_quality_score)[:limit]


def model_versions_from_env() -> dict[str, str]:
    return {
        "chat_deployment": os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "unknown"),
        "embedding_deployment": os.getenv(
            "AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "unknown"
        ),
        "azure_openai_api_version": os.getenv("AZURE_OPENAI_API_VERSION", "unknown"),
    }


def _aggregate_group(cases: list[dict[str, Any]]) -> dict[str, Any]:
    recall_values = [
        case["metrics"]["retrieval_recall"]
        for case in cases
        if case["metrics"]["retrieval_recall"] is not None
    ]
    faithfulness_values = [
        case["metrics"]["faithfulness"]["score"]
        for case in cases
        if case["metrics"]["faithfulness"] is not None
        and case["metrics"]["faithfulness"]["score"] is not None
    ]
    expected_both = [
        case for case in cases if bool(case["expected_surfaces_both_sources"])
    ]
    latencies = [float(case["latency_ms"]) for case in cases]
    return {
        "case_count": len(cases),
        "mean_recall": _mean_or_none(recall_values),
        "refusal_accuracy": _mean_or_none(
            [1.0 if case["metrics"]["refusal_match"] else 0.0 for case in cases]
        ),
        "mean_faithfulness": _mean_or_none(faithfulness_values),
        "surfaces_both_rate": _mean_or_none(
            [
                1.0 if case["metrics"]["detected_surfaces_both_sources"] else 0.0
                for case in expected_both
            ]
        ),
        "mean_latency_ms": _mean_or_none(latencies),
        "p95_latency_ms": _p95_or_none(latencies),
        "error_rate": _mean_or_none(
            [1.0 if case["metrics"]["error"] else 0.0 for case in cases]
        ),
    }


def _summary_row(category: str, metrics: dict[str, Any]) -> str:
    return (
        f"| {category} | {metrics['case_count']} | {_fmt(metrics['mean_recall'])} | "
        f"{_fmt(metrics['refusal_accuracy'])} | {_fmt(metrics['surfaces_both_rate'])} | "
        f"{_fmt(metrics['mean_faithfulness'])} | {_fmt(metrics['mean_latency_ms'])} | "
        f"{_fmt(metrics['p95_latency_ms'])} | {_fmt(metrics['error_rate'])} |"
    )


def _met_missed_lines(overall: dict[str, Any]) -> list[str]:
    checks = [
        ("mean_recall", "Recall", "retrieved citations missed expected source files."),
        (
            "refusal_accuracy",
            "Refusal",
            "refusal behavior did not match the test set expectations.",
        ),
        (
            "surfaces_both_rate",
            "Surfaces-both",
            "disagreement answers did not consistently name both handbooks.",
        ),
        (
            "mean_faithfulness",
            "Faithfulness",
            "the judge found unsupported answer claims.",
        ),
    ]
    lines: list[str] = []
    for key, label, miss_reason in checks:
        value = overall.get(key)
        bar = QUALITY_BARS[key]
        if value is None:
            lines.append(
                f"- {label}: missed because no applicable cases produced this metric."
            )
        elif value >= bar:
            lines.append(f"- {label}: met ({value:.3f} >= {bar:.2f}).")
        else:
            lines.append(f"- {label}: missed ({value:.3f} < {bar:.2f}); {miss_reason}")
    return lines


def _diagnose_case(case: dict[str, Any]) -> str:
    metrics = case["metrics"]
    issues: list[str] = []
    if metrics["retrieval_recall"] is not None and metrics["retrieval_recall"] < 1.0:
        issues.append("expected citation file was not returned")
    if not metrics["refusal_match"]:
        issues.append("refusal expectation did not match")
    if (
        bool(case["expected_surfaces_both_sources"])
        and not metrics["detected_surfaces_both_sources"]
    ):
        issues.append("answer did not surface both sources")
    faithfulness = metrics["faithfulness"]
    if (
        faithfulness
        and faithfulness["score"] is not None
        and faithfulness["score"] < 0.8
    ):
        issues.append(f"faithfulness was low ({faithfulness['score']:.2f})")
    if metrics["error"]:
        issues.append(f"HTTP status was {case['http_status']}")
    return (
        "; ".join(issues)
        if issues
        else "lowest aggregate score among otherwise passing cases"
    )


def _case_quality_score(case: dict[str, Any]) -> float:
    metrics = case["metrics"]
    parts: list[float] = []
    if metrics["retrieval_recall"] is not None:
        parts.append(float(metrics["retrieval_recall"]))
    parts.append(1.0 if metrics["refusal_match"] else 0.0)
    if bool(case["expected_surfaces_both_sources"]):
        parts.append(1.0 if metrics["detected_surfaces_both_sources"] else 0.0)
    faithfulness = metrics["faithfulness"]
    if faithfulness and faithfulness["score"] is not None:
        parts.append(float(faithfulness["score"]))
    if metrics["error"]:
        parts.append(0.0)
    return statistics.mean(parts) if parts else 0.0


def _extract_answer(payload: dict[str, Any]) -> str:
    answer = payload.get("answer")
    if isinstance(answer, str):
        return answer
    detail = payload.get("detail")
    if isinstance(detail, str):
        return detail
    if detail is not None:
        return json.dumps(detail, ensure_ascii=False)
    return ""


def _retrieval_recall(
    expected_citations: Any, citation_paths: list[str]
) -> float | None:
    if expected_citations is None:
        return None
    expected = [str(item) for item in expected_citations]
    if not expected:
        return None
    returned = set(citation_paths)
    return sum(1 for filename in expected if filename in returned) / len(expected)


def _is_refusal(answer: str) -> bool:
    lower = answer.lower()
    return any(marker in lower for marker in REFUSAL_MARKERS)


def _surfaces_both_sources(answer: str) -> bool:
    lower = answer.lower()
    has_opengov = "opengov" in lower or "open gov" in lower
    has_madetech = "made tech" in lower or "madetech" in lower
    return has_opengov and has_madetech


def _faithfulness_user_message(question: str, answer: str, context: str) -> str:
    return "\n".join(
        [
            "Question:",
            question,
            "",
            "Answer:",
            answer,
            "",
            "Context:",
            context or "(no cited context)",
        ]
    )


def _mean_or_none(values: Sequence[float]) -> float | None:
    if not values:
        return None
    return float(statistics.mean(values))


def _p95_or_none(values: Sequence[float]) -> float | None:
    if not values:
        return None
    sorted_values = sorted(values)
    index = max(
        0, min(len(sorted_values) - 1, math.ceil(len(sorted_values) * 0.95) - 1)
    )
    return float(sorted_values[index])


def _fmt(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
