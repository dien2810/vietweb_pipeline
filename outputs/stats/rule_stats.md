Run finished 2026-10-26T19:14:29+00:00 (UTC): 48815 documents in, 24621 kept; langid=heuristic, quality unit=syllable, near-dup unit=syllable.

## Funnel

| Stage | In | Removed | Kept (% of input) | Top reason | Seconds |
|---|---:|---:|---:|---|---:|
| normalize | 48815 | 0 | 100.0% |  | 434.6 |
| boilerplate | 48815 | 11359 | 76.73% | boilerplate_too_short | 37.7 |
| langid | 37456 | 4060 | 68.41% | langid_low_score | 45.2 |
| url_filter | 33396 | 2244 | 63.82% | spam_keywords | 4.7 |
| dedup_exact | 31152 | 1005 | 61.76% | exact_duplicate | 11.6 |
| dedup_near | 30147 | 1013 | 59.68% | near_duplicate | 80.0 |
| dedup_line | 29134 | 186 | 59.3% | empty_after_line_dedup | 5.1 |
| quality | 28948 | 4327 | 50.44% | gopher_word_count | 64.6 |
| pii | 24621 | 0 | 50.44% |  | 21.2 |

## Quality rules

Documents evaluated: 28948; violating at least one rule: 4327 (14.9%).

| # | Rule | Drop if | Failed | Dropped | Sole | p10 / p50 / p90 | us/doc |
|---:|---|---|---:|---:|---:|---|---:|
| 1 | c4_lorem_ipsum | present | 63 (0.2%) | 63 | 49 | 0 / 0 / 0 | 31 |
| 2 | c4_curly_bracket | present | 90 (0.3%) | 89 | 78 | 0 / 0 / 0 | 3 |
| 3 | gopher_word_count | < 50 or > 100000 | 1368 (4.7%) | 1363 | 757 | 69 / 464 / 1596 | 1 |
| 4 | gopher_mean_word_length | < 3 or > 10 | 344 (1.2%) | 299 | 98 | 3.28 / 3.45 / 3.68 | 97 |
| 5 | gopher_symbol_ratio | > 0.1 | 14 (0.0%) | 11 | 11 | 0 / 0 / 0.00242 | 9 |
| 6 | gopher_bullet_lines | > 0.9 | 161 (0.6%) | 139 | 116 | 0 / 0 / 0.143 | 7 |
| 7 | gopher_ellipsis_lines | > 0.3 | 0 (0.0%) | 0 | 0 | 0 / 0 / 0 | 5 |
| 8 | gopher_alpha_words | < 0.8 | 326 (1.1%) | 120 | 68 | 0.928 / 0.979 / 0.998 | 608 |
| 9 | gopher_stopwords | < 2 | 320 (1.1%) | 100 | 59 | 7 / 30 / 47 | 54 |
| 10 | gopher_dup_lines | > 0.3 | 985 (3.4%) | 827 | 23 | 0 / 0 / 0.115 | 7 |
| 11 | gopher_dup_paragraphs | > 0.3 | 0 (0.0%) | 0 | 0 | 0 / 0 / 0 | 7 |
| 12 | gopher_top_2gram | > 0.2 | 256 (0.9%) | 32 | 18 | 0.0193 / 0.04 / 0.087 | 326 |
| 13 | gopher_top_3gram | > 0.18 | 428 (1.5%) | 79 | 38 | 0.0139 / 0.0338 / 0.0864 | 319 |
| 14 | gopher_top_4gram | > 0.16 | 983 (3.4%) | 180 | 143 | 0.0125 / 0.0336 / 0.0966 | 325 |
| 15 | fineweb_line_punct | <= 0.12 | 0 (0.0%) | 0 | 0 | 1 / 1 / 1 | 7 |
| 16 | fineweb_dup_line_chars | >= 0.1 | 2135 (7.4%) | 1010 | 1009 | 0 / 0 / 0.0602 | 11 |
| 17 | fineweb_short_lines | >= 0.67 | 44 (0.2%) | 15 | 15 | 0 / 0 / 0.111 | 4 |
