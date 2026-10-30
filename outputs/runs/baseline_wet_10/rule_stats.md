Run: 2414 documents in, 437 kept; langid=heuristic, quality unit=syllable, near-dup unit=syllable.

## Funnel

| Stage | In | Removed | Kept (% of input) | Top reason | Seconds |
|---|---:|---:|---:|---|---:|
| normalize | 2414 | 0 | 100.0% |  | 57.8 |
| langid | 2414 | 375 | 84.47% | langid_low_score | 10.6 |
| url_filter | 2039 | 172 | 77.34% | spam_keywords | 0.9 |
| dedup_exact | 1867 | 1 | 77.3% | exact_duplicate | 3.0 |
| dedup_near | 1866 | 23 | 76.35% | near_duplicate | 19.8 |
| dedup_line | 1843 | 0 | 76.35% |  | 1.4 |
| quality | 1843 | 1406 | 18.1% | gopher_dup_lines | 19.3 |
| pii | 437 | 0 | 18.1% |  | 2.2 |

## Quality rules

Documents evaluated: 1843; violating at least one rule: 1406 (76.3%).

| # | Rule | Drop if | Failed | Dropped | Sole | p10 / p50 / p90 | us/doc |
|---:|---|---|---:|---:|---:|---|---:|
| 1 | c4_lorem_ipsum | present | 7 (0.4%) | 7 | 0 | 0 / 0 / 0 | 142 |
| 2 | c4_curly_bracket | present | 61 (3.3%) | 61 | 11 | 0 / 0 / 0 | 13 |
| 3 | gopher_word_count | < 50 or > 100000 | 4 (0.2%) | 4 | 0 | 382 / 1233 / 3261 | 3 |
| 4 | gopher_mean_word_length | < 3 or > 10 | 6 (0.3%) | 6 | 1 | 3.35 / 3.55 / 3.92 | 462 |
| 5 | gopher_symbol_ratio | > 0.1 | 0 (0.0%) | 0 | 0 | 0 / 0.00065 / 0.0057 | 34 |
| 6 | gopher_bullet_lines | > 0.9 | 0 (0.0%) | 0 | 0 | 0 / 0 / 0.0505 | 111 |
| 7 | gopher_ellipsis_lines | > 0.3 | 0 (0.0%) | 0 | 0 | 0 / 0 / 0.0268 | 84 |
| 8 | gopher_alpha_words | < 0.8 | 31 (1.7%) | 29 | 1 | 0.879 / 0.943 / 0.977 | 2505 |
| 9 | gopher_stopwords | < 2 | 8 (0.4%) | 6 | 0 | 10 / 30 / 48 | 220 |
| 10 | gopher_dup_lines | > 0.3 | 542 (29.4%) | 516 | 11 | 0.0414 / 0.202 / 0.421 | 57 |
| 11 | gopher_dup_paragraphs | > 0.3 | 0 (0.0%) | 0 | 0 | 0 / 0 / 0 | 31 |
| 12 | gopher_top_2gram | > 0.2 | 10 (0.5%) | 1 | 0 | 0.0193 / 0.0401 / 0.0895 | 1510 |
| 13 | gopher_top_3gram | > 0.18 | 19 (1.0%) | 7 | 0 | 0.0135 / 0.0307 / 0.0727 | 1549 |
| 14 | gopher_top_4gram | > 0.16 | 35 (1.9%) | 14 | 2 | 0.012 / 0.0291 / 0.0736 | 1579 |
| 15 | fineweb_line_punct | <= 0.12 | 922 (50.0%) | 484 | 58 | 0.0276 / 0.12 / 0.323 | 120 |
| 16 | fineweb_dup_line_chars | >= 0.1 | 895 (48.6%) | 145 | 75 | 0.0137 / 0.0962 / 0.298 | 105 |
| 17 | fineweb_short_lines | >= 0.67 | 1093 (59.3%) | 126 | 126 | 0.453 / 0.716 / 0.887 | 54 |
