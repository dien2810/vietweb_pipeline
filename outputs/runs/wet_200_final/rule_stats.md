Run: 48815 documents in, 25255 kept; langid=heuristic, quality unit=syllable, near-dup unit=syllable.

## Funnel

| Stage | In | Removed | Kept (% of input) | Top reason | Seconds |
|---|---:|---:|---:|---|---:|
| normalize | 48815 | 0 | 100.0% |  | 636.0 |
| boilerplate | 48815 | 11359 | 76.73% | boilerplate_too_short | 42.1 |
| langid | 37456 | 4060 | 68.41% | langid_low_score | 24.4 |
| url_filter | 33396 | 2244 | 63.82% | spam_keywords | 2.8 |
| dedup_exact | 31152 | 1005 | 61.76% | exact_duplicate | 6.9 |
| dedup_near | 30147 | 1013 | 59.68% | near_duplicate | 51.5 |
| dedup_line | 29134 | 186 | 59.3% | empty_after_line_dedup | 3.1 |
| quality | 28948 | 3693 | 51.74% | gopher_word_count | 43.3 |
| pii | 25255 | 0 | 51.74% |  | 15.6 |

## Quality rules

Documents evaluated: 28948; violating at least one rule: 3693 (12.8%).

| # | Rule | Drop if | Failed | Dropped | Sole | p10 / p50 / p90 | us/doc |
|---:|---|---|---:|---:|---:|---|---:|
| 1 | c4_lorem_ipsum | present | 63 (0.2%) | 63 | 49 | 0 / 0 / 0 | 21 |
| 2 | c4_curly_bracket | present | 90 (0.3%) | 89 | 80 | 0 / 0 / 0 | 2 |
| 3 | gopher_word_count | < 53 or > 100000 | 1614 (5.6%) | 1609 | 762 | 69 / 464 / 1596 | 1 |
| 4 | gopher_mean_word_length | < 3 or > 10 | 344 (1.2%) | 296 | 101 | 3.28 / 3.45 / 3.68 | 66 |
| 5 | gopher_symbol_ratio | > 0.1 | 14 (0.0%) | 11 | 11 | 0 / 0 / 0.00242 | 6 |
| 6 | gopher_bullet_lines | > 0.9 | 161 (0.6%) | 135 | 115 | 0 / 0 / 0.143 | 5 |
| 7 | gopher_ellipsis_lines | > 0.3 | 0 (0.0%) | 0 | 0 | 0 / 0 / 0 | 3 |
| 8 | gopher_alpha_words | < 0.8 | 326 (1.1%) | 115 | 59 | 0.928 / 0.979 / 0.998 | 415 |
| 9 | gopher_stopwords | < 4 | 1131 (3.9%) | 365 | 242 | 7 / 30 / 47 | 37 |
| 10 | gopher_dup_lines | > 0.3 | 985 (3.4%) | 763 | 674 | 0 / 0 / 0.115 | 5 |
| 11 | gopher_dup_paragraphs | > 0.3 | 0 (0.0%) | 0 | 0 | 0 / 0 / 0 | 5 |
| 12 | gopher_top_2gram | > 0.2 | 256 (0.9%) | 23 | 16 | 0.0193 / 0.04 / 0.087 | 218 |
| 13 | gopher_top_3gram | > 0.18 | 428 (1.5%) | 68 | 38 | 0.0139 / 0.0338 / 0.0864 | 215 |
| 14 | gopher_top_4gram | > 0.16 | 983 (3.4%) | 142 | 142 | 0.0125 / 0.0336 / 0.0966 | 217 |
| 15 | fineweb_line_punct | <= 0.12 | 0 (0.0%) | 0 | 0 | 1 / 1 / 1 | 4 |
| 16 | fineweb_short_lines | >= 0.67 | 44 (0.2%) | 14 | 14 | 0 / 0 / 0.111 | 3 |
