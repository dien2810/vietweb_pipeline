Run: 18576 documents in, 10050 kept; langid=heuristic, quality unit=syllable, near-dup unit=syllable.

## Funnel

| Stage | In | Removed | Kept (% of input) | Top reason | Seconds |
|---|---:|---:|---:|---|---:|
| normalize | 18576 | 0 | 100.0% |  | 446.2 |
| boilerplate | 18576 | 4313 | 76.78% | boilerplate_too_short | 22.3 |
| langid | 14263 | 1469 | 68.87% | langid_low_score | 25.9 |
| url_filter | 12794 | 399 | 66.73% | spam_keywords | 1.0 |
| dedup_exact | 12395 | 318 | 65.01% | exact_duplicate | 3.3 |
| dedup_near | 12077 | 360 | 63.08% | near_duplicate | 63.8 |
| dedup_line | 11717 | 46 | 62.83% | empty_after_line_dedup | 3.0 |
| quality | 11671 | 1621 | 54.1% | gopher_word_count | 49.5 |
| pii | 10050 | 0 | 54.1% |  | 17.1 |

## Quality rules

Documents evaluated: 11671; violating at least one rule: 1621 (13.9%).

| # | Rule | Drop if | Failed | Dropped | Sole | p10 / p50 / p90 | us/doc |
|---:|---|---|---:|---:|---:|---|---:|
| 1 | c4_lorem_ipsum | present | 29 (0.2%) | 29 | 24 | 0 / 0 / 0 | 64 |
| 2 | c4_curly_bracket | present | 212 (1.8%) | 212 | 167 | 0 / 0 / 0 | 7 |
| 3 | gopher_word_count | < 53 or > 100000 | 705 (6.0%) | 697 | 317 | 66 / 438 / 1477 | 3 |
| 4 | gopher_mean_word_length | < 3 or > 10 | 57 (0.5%) | 34 | 22 | 3.28 / 3.44 / 3.7 | 193 |
| 5 | gopher_symbol_ratio | > 0.1 | 2 (0.0%) | 2 | 2 | 0 / 0 / 0.00346 | 18 |
| 6 | gopher_bullet_lines | > 0.9 | 54 (0.5%) | 46 | 40 | 0 / 0 / 0.182 | 16 |
| 7 | gopher_ellipsis_lines | > 0.3 | 0 (0.0%) | 0 | 0 | 0 / 0 / 0 | 12 |
| 8 | gopher_alpha_words | < 0.8 | 69 (0.6%) | 30 | 17 | 0.929 / 0.978 / 0.997 | 1035 |
| 9 | gopher_stopwords | < 4 | 444 (3.8%) | 161 | 111 | 7 / 30 / 48 | 104 |
| 10 | gopher_dup_lines | > 0.3 | 399 (3.4%) | 299 | 272 | 0 / 0 / 0.125 | 14 |
| 11 | gopher_dup_paragraphs | > 0.3 | 0 (0.0%) | 0 | 0 | 0 / 0 / 0 | 14 |
| 12 | gopher_top_2gram | > 0.2 | 79 (0.7%) | 14 | 10 | 0.0198 / 0.0419 / 0.087 | 638 |
| 13 | gopher_top_3gram | > 0.18 | 177 (1.5%) | 37 | 19 | 0.0143 / 0.0352 / 0.0877 | 626 |
| 14 | gopher_top_4gram | > 0.16 | 360 (3.1%) | 55 | 55 | 0.013 / 0.0348 / 0.0974 | 639 |
| 15 | fineweb_line_punct | <= 0.12 | 0 (0.0%) | 0 | 0 | 1 / 1 / 1 | 17 |
| 16 | fineweb_short_lines | >= 0.67 | 21 (0.2%) | 5 | 5 | 0 / 0 / 0.125 | 9 |
