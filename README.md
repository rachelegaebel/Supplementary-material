# RacqI thesis — supplementary materials

This repository accompanies the bachelor thesis on **RacqI**, a grounded vertical agent for
racquet-sports facilities. It holds the frozen study materials, the anonymised questionnaire 
exports, the de-blinding key, and the analysis code, so that the empirical results in Chapter 
5 can be reproduced independently.

The study compares RacqI, in its full grounded configuration, against the same base model
without grounding, on 16 strategic questions, across a dense market (Italy) and a thin one
(the Czech Republic), rated blind by two panels: domain experts (evidence and reasoning
quality) and non-expert decision-makers (perceived confidence).

## Contents

| Path | What it is |
|------|------------|
| `DATASET_32_verbatim.md` | The 32 rated answers (16 questions × 2 arms: RacqI grounded vs the plain base model), verbatim as frozen. |
| `DATASET_32_normalized.md` | The same 32 answers in the form the raters saw (RacqI branding removed; content unchanged). Read by the analysis to self-verify the key. |
| `Test 2 - Experts_anonymized.csv` | Expert-panel questionnaire export, **anonymised** (name, e-mail, IP address, and geolocation removed). |
| `Test 2 - Non-experts_anonymized.csv` | Non-expert-panel questionnaire export, **anonymised** (same fields removed). |
| `blinding_key.json` | The pre-registered A/B → grounded/plain mapping (seed 20260806) that decodes the blind labels. |
| `survey_definitions/qualtrics_EXPERTS_full.txt`, `qualtrics_BUSINESSMEN_full.txt` | The two survey definitions, used by the analysis to self-verify the key against the answer text. |
| `analysis/analyze_test2.py` · `analysis/analyze_test2.R` | The analysis pipeline (Python and R): de-blinds the responses with the key, then computes the per-condition aggregates, the density gradient, retention, Krippendorff's ordinal alpha, and the controls attribution behind Chapter 5. |
| `analysis/experts_tidy.csv` · `nonexperts_tidy.csv` · `dissociation_pairing.csv` | The de-blinded ratings and per-question contrasts, produced by the pipeline. |

## Reproducing the analysis

From the `analysis/` folder:

```
python analyze_test2.py      # or:  Rscript analyze_test2.R
```

The script reads the anonymised questionnaire exports, `blinding_key.json` and
`DATASET_32_normalized.md`, de-blinds each rating through the key, writes the three tidy
files, and prints the aggregates, the gradient, the retention percentages, the alphas and
the controls reading. The outputs are byte-for-byte identical whether the personal-data
fields are present or removed, so the anonymised exports reproduce every number in Chapter 5.

## Data protection

The questionnaire exports here are **anonymised**: the name, e-mail address, IP address and
geolocation fields have been removed. Only the pseudonymous response ID, the timestamps, and
the ratings themselves remain. Participation was voluntary and anonymous, under informed
consent. No personal data is included in this repository.

## Frozen record

The plain-model answers were generated once, with web search off, and frozen on 6 August
2026 as a single read-only file sealed with SHA-256
`9b711563c91883added4509f467611ffd74587349ee2cced430ca2bb0284578a`. The two scoring rubrics,
the 16 questions, the plain-model prompt, and the system configuration were fixed and dated
before any response was generated. Full provenance is in Appendix D of the thesis.
