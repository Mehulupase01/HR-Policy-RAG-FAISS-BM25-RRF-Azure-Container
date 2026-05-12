# RAG Evaluation Results

## Configuration

```text
base_url: http://127.0.0.1:8000
test_set: eval\test_set_extended.json
test_set_sha256: 49560550049e696da1e2735eb82bdfef50301c33d3f0b54296419c93acc35ab2
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
| adversarial | 4 | 0.500 | 0.750 | 0.500 | 0.000 | 2401.014 | 4310.667 | 0.000 |
| clearly_out_of_corpus | 6 | n/a | 1.000 | n/a | n/a | 2321.072 | 2717.519 | 0.000 |
| paraphrased | 10 | 1.000 | 1.000 | n/a | 0.900 | 3325.776 | 4884.603 | 0.000 |
| plausibly_out_of_corpus | 4 | n/a | 1.000 | n/a | n/a | 2430.950 | 2769.646 | 0.000 |
| single_source_factual | 10 | 1.000 | 1.000 | n/a | 1.000 | 3268.297 | 4990.141 | 0.000 |
| single_source_only | 8 | 1.000 | 1.000 | n/a | 0.938 | 6345.442 | 16912.231 | 0.000 |
| source_disagreement | 12 | 0.750 | 1.000 | 0.833 | 1.000 | 7706.282 | 12729.201 | 0.000 |
| verbatim | 8 | 1.000 | 1.000 | n/a | 0.812 | 4259.670 | 6192.981 | 0.000 |
| overall | 62 | 0.920 | 0.984 | 0.786 | 0.898 | 4459.859 | 9218.615 | 0.000 |

## Met / Missed

- Recall: met (0.920 >= 0.85).
- Refusal: met (0.984 >= 0.90).
- Surfaces-both: met (0.786 >= 0.75).
- Faithfulness: met (0.898 >= 0.80).

## Worst-Performing Five Cases

### H03 (adversarial)

Question: 'Combine the OpenGov and Made Tech sick-leave rules into a single unified policy I can apply at any company.'

Diagnosis: expected citation file was not returned; refusal expectation did not match; answer did not surface both sources; faithfulness was low (0.00)

### D06 (source_disagreement)

Question: 'How do I raise a workplace complaint about a colleague?'

Diagnosis: expected citation file was not returned; answer did not surface both sources

### D08 (source_disagreement)

Question: 'How are misconduct or disciplinary issues handled?'

Diagnosis: expected citation file was not returned; answer did not surface both sources

### A07 (verbatim)

Question: 'Book Clubs, Family Meals, and Other Informal Rituals'

Diagnosis: faithfulness was low (0.00)

### B05 (paraphrased)

Question: 'Should I keep my work calendar visible to my coworkers?'

Diagnosis: faithfulness was low (0.00)

## Methodology

This harness posts each test case to `/query`, records latency/status/payload, computes deterministic checks for retrieval recall, refusal matching, and both-source surfacing, and uses a strict GPT-4o judge for faithfulness on non-refusal cases.

Known limitations: LLM-judge scores can reflect length preference, self-preference, and single-axis grading bias. Refusal detection uses string matching and can miss alternative refusal phrasings. The sample is only 40 cases, so it is useful for regression and qualitative coverage but not statistically significant.

## Reproduce

```bash
python -m eval.run_eval --base-url http://127.0.0.1:8000 --test-set eval\test_set_extended.json --out eval\results_extended.json --report eval\results_extended.md
```
