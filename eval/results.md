# RAG Evaluation Results

## Configuration

```text
base_url: http://127.0.0.1:8010
test_set: eval\test_set.json
test_set_sha256: 56fe379ebaf74f70ee248f9e4c5bcb77b0356e74c0ab689a02ea7afd103f5a0a
chat_deployment: gpt-4o
embedding_deployment: text-embedding-3-large
azure_openai_api_version: 2024-10-21
context_index: data\index
```

## Quality Bar

- recall >= 0.85
- refusal >= 0.90
- surfaces-both >= 0.75
- mean faithfulness >= 0.80

## Summary By Category

| Category | Cases | Mean Recall | Refusal Accuracy | Surfaces-Both Rate | Mean Faithfulness | Mean Latency ms | P95 Latency ms | Error Rate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| adversarial | 3 | n/a | 1.000 | n/a | n/a | 1118.993 | 2402.520 | 0.000 |
| clearly_out_of_corpus | 5 | n/a | 1.000 | n/a | n/a | 2048.519 | 2533.943 | 0.000 |
| paraphrased | 5 | 1.000 | 1.000 | n/a | 0.900 | 3704.626 | 4979.928 | 0.000 |
| plausibly_out_of_corpus | 4 | n/a | 1.000 | n/a | n/a | 1925.615 | 2530.262 | 0.000 |
| single_source_factual | 6 | 1.000 | 1.000 | n/a | 1.000 | 3037.546 | 5453.981 | 0.000 |
| single_source_only | 4 | 1.000 | 1.000 | n/a | 1.000 | 2937.466 | 3456.246 | 0.000 |
| source_disagreement | 8 | 0.938 | 1.000 | 1.000 | 0.975 | 6206.290 | 11248.755 | 0.000 |
| verbatim | 5 | 1.000 | 1.000 | n/a | 0.800 | 3699.806 | 5607.725 | 0.000 |
| overall | 40 | 0.982 | 1.000 | 1.000 | 0.939 | 3448.741 | 7114.199 | 0.000 |

## Met / Missed

- Recall: met (0.982 >= 0.85).
- Refusal: met (1.000 >= 0.90).
- Surfaces-both: met (1.000 >= 0.75).
- Faithfulness: met (0.939 >= 0.80).

## Worst-Performing Five Cases

### A03 (verbatim)

Question: 'Annual cost of living increases'

Diagnosis: faithfulness was low (0.00)

### B03 (paraphrased)

Question: 'How far ahead should I ask to permanently change my working pattern?'

Diagnosis: faithfulness was low (0.50)

### D07 (source_disagreement)

Question: 'Who should I report harassment, misconduct, or a serious workplace concern to?'

Diagnosis: expected citation file was not returned

### D06 (source_disagreement)

Question: 'What are the normal working hours and availability expectations?'

Diagnosis: lowest aggregate score among otherwise passing cases

### A01 (verbatim)

Question: 'organizational Google Suite account'

Diagnosis: lowest aggregate score among otherwise passing cases

## Methodology

This harness posts each test case to `/query`, records latency/status/payload, computes deterministic checks for retrieval recall, refusal matching, and both-source surfacing, and uses a strict GPT-4o judge for faithfulness on non-refusal cases.

Known limitations: LLM-judge scores can reflect length preference, self-preference, and single-axis grading bias. Refusal detection uses string matching and can miss alternative refusal phrasings. The sample is only 40 cases, so it is useful for regression and qualitative coverage but not statistically significant.

## Reproduce

```bash
python -m eval.run_eval --base-url http://127.0.0.1:8010 --test-set eval\test_set.json --out eval\results.json --report eval\results.md
```
