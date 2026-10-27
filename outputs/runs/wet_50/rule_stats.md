Run finished 2026-10-02T18:46:55+00:00 (UTC): 12304 documents in, 2300 kept; langid=heuristic, quality unit=syllable, near-dup unit=syllable.

## Funnel

| Stage | In | Removed | Kept (% of input) | Top reason | Seconds |
|---|---:|---:|---:|---|---:|
| normalize | 12304 | 0 | 100.0% |  | 304.2 |
| langid | 12304 | 1883 | 84.7% | langid_low_score | 53.7 |
| url_filter | 10421 | 880 | 77.54% | spam_keywords | 4.5 |
| dedup_exact | 9541 | 30 | 77.3% | exact_duplicate | 15.3 |
| dedup_near | 9511 | 334 | 74.59% | near_duplicate | 102.2 |
| dedup_line | 9177 | 0 | 74.59% |  | 7.5 |
| quality | 9177 | 6877 | 18.69% | gopher_dup_lines | 86.9 |
| pii | 2300 | 0 | 18.69% |  | 11.2 |

## Quality rules

Documents evaluated: 9177; violating at least one rule: 6877 (74.9%).

| # | Rule | Drop if | Failed | Dropped | Sole | p10 / p50 / p90 | us/doc |
|---:|---|---|---:|---:|---:|---|---:|
| 1 | c4_lorem_ipsum | present | 30 (0.3%) | 30 | 4 | 0 / 0 / 0 | 129 |
| 2 | c4_curly_bracket | present | 294 (3.2%) | 294 | 62 | 0 / 0 / 0 | 12 |
| 3 | gopher_word_count | < 50 or > 100000 | 29 (0.3%) | 29 | 5 | 344 / 1210 / 3048 | 4 |
| 4 | gopher_mean_word_length | < 3 or > 10 | 43 (0.5%) | 37 | 3 | 3.34 / 3.54 / 3.9 | 407 |
| 5 | gopher_symbol_ratio | > 0.1 | 9 (0.1%) | 9 | 3 | 0 / 0.00059 / 0.00616 | 31 |
| 6 | gopher_bullet_lines | > 0.9 | 0 (0.0%) | 0 | 0 | 0 / 0 / 0.0522 | 97 |
| 7 | gopher_ellipsis_lines | > 0.3 | 9 (0.1%) | 9 | 4 | 0 / 0 / 0.0286 | 71 |
| 8 | gopher_alpha_words | < 0.8 | 159 (1.7%) | 133 | 11 | 0.876 / 0.942 / 0.977 | 2251 |
| 9 | gopher_stopwords | < 2 | 46 (0.5%) | 33 | 0 | 9 / 30 / 48 | 206 |
| 10 | gopher_dup_lines | > 0.3 | 2772 (30.2%) | 2621 | 66 | 0.0417 / 0.206 / 0.429 | 53 |
| 11 | gopher_dup_paragraphs | > 0.3 | 1 (0.0%) | 0 | 0 | 0 / 0 / 0 | 29 |
| 12 | gopher_top_2gram | > 0.2 | 61 (0.7%) | 13 | 1 | 0.0191 / 0.04 / 0.0905 | 1367 |
| 13 | gopher_top_3gram | > 0.18 | 85 (0.9%) | 31 | 4 | 0.0138 / 0.032 / 0.0784 | 1391 |
| 14 | gopher_top_4gram | > 0.16 | 146 (1.6%) | 47 | 9 | 0.0126 / 0.0305 / 0.076 | 1456 |
| 15 | fineweb_line_punct | <= 0.12 | 4464 (48.6%) | 2219 | 320 | 0.0272 / 0.125 / 0.341 | 111 |
| 16 | fineweb_dup_line_chars | >= 0.1 | 4296 (46.8%) | 698 | 365 | 0.0132 / 0.0915 / 0.302 | 96 |
| 17 | fineweb_short_lines | >= 0.67 | 5374 (58.6%) | 674 | 674 | 0.438 / 0.712 / 0.888 | 45 |
