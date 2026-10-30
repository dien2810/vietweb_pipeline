Run: 12304 documents in, 6116 kept; langid=heuristic, quality unit=syllable, near-dup unit=syllable.

## Funnel

| Stage | In | Removed | Kept (% of input) | Top reason | Seconds |
|---|---:|---:|---:|---|---:|
| normalize | 12304 | 0 | 100.0% |  | 138.5 |
| boilerplate | 12304 | 2249 | 81.72% | boilerplate_too_short | 5.8 |
| langid | 10055 | 1230 | 71.72% | langid_low_score | 8.4 |
| url_filter | 8825 | 597 | 66.87% | spam_keywords | 0.8 |
| dedup_exact | 8228 | 127 | 65.84% | exact_duplicate | 1.9 |
| dedup_near | 8101 | 151 | 64.61% | near_duplicate | 14.3 |
| dedup_line | 7950 | 20 | 64.45% | empty_after_line_dedup | 0.8 |
| quality | 7930 | 1814 | 49.71% | gopher_ellipsis_lines | 13.6 |
| pii | 6116 | 0 | 49.71% |  | 4.0 |

## Quality rules

Documents evaluated: 7930; violating at least one rule: 1814 (22.9%).

| # | Rule | Drop if | Failed | Dropped | Sole | p10 / p50 / p90 | us/doc |
|---:|---|---|---:|---:|---:|---|---:|
| 1 | c4_lorem_ipsum | present | 28 (0.4%) | 28 | 16 | 0 / 0 / 0 | 23 |
| 2 | c4_curly_bracket | present | 32 (0.4%) | 30 | 23 | 0 / 0 / 0 | 2 |
| 3 | gopher_word_count | < 50 or > 100000 | 213 (2.7%) | 211 | 102 | 77.9 / 477 / 1690 | 1 |
| 4 | gopher_mean_word_length | < 3 or > 10 | 75 (0.9%) | 70 | 22 | 3.3 / 3.46 / 3.71 | 75 |
| 5 | gopher_symbol_ratio | > 0.1 | 24 (0.3%) | 18 | 2 | 0 / 0 / 0.0141 | 7 |
| 6 | gopher_bullet_lines | > 0.9 | 21 (0.3%) | 20 | 14 | 0 / 0 / 0.133 | 6 |
| 7 | gopher_ellipsis_lines | > 0.3 | 846 (10.7%) | 772 | 643 | 0 / 0 / 0.333 | 4 |
| 8 | gopher_alpha_words | < 0.8 | 82 (1.0%) | 38 | 22 | 0.93 / 0.978 / 0.997 | 476 |
| 9 | gopher_stopwords | < 2 | 48 (0.6%) | 17 | 11 | 8 / 29 / 47 | 43 |
| 10 | gopher_dup_lines | > 0.3 | 300 (3.8%) | 207 | 10 | 0 / 0 / 0.152 | 5 |
| 11 | gopher_dup_paragraphs | > 0.3 | 0 (0.0%) | 0 | 0 | 0 / 0 / 0 | 6 |
| 12 | gopher_top_2gram | > 0.2 | 47 (0.6%) | 7 | 6 | 0.0188 / 0.0392 / 0.0842 | 245 |
| 13 | gopher_top_3gram | > 0.18 | 68 (0.9%) | 10 | 4 | 0.0135 / 0.0333 / 0.0829 | 240 |
| 14 | gopher_top_4gram | > 0.16 | 197 (2.5%) | 37 | 24 | 0.0122 / 0.0338 / 0.0924 | 247 |
| 15 | fineweb_line_punct | <= 0.12 | 0 (0.0%) | 0 | 0 | 1 / 1 / 1 | 5 |
| 16 | fineweb_dup_line_chars | >= 0.1 | 759 (9.6%) | 347 | 346 | 0 / 0 / 0.0952 | 8 |
| 17 | fineweb_short_lines | >= 0.67 | 12 (0.2%) | 2 | 2 | 0 / 0 / 0.133 | 3 |
