Run: 246833 documents in, 118069 kept; langid=heuristic, quality unit=syllable, near-dup unit=syllable.

## Funnel

| Stage | In | Removed | Kept (% of input) | Top reason | Seconds |
|---|---:|---:|---:|---|---:|
| normalize | 246833 | 0 | 100.0% |  | 476.9 |
| boilerplate | 246833 | 57158 | 76.84% | boilerplate_too_short | 89.2 |
| langid | 189675 | 20513 | 68.53% | langid_low_score | 73.2 |
| url_filter | 169162 | 11475 | 63.88% | spam_keywords | 18.1 |
| dedup_exact | 157687 | 10480 | 59.64% | exact_duplicate | 38.3 |
| dedup_near | 147207 | 9470 | 55.8% | near_duplicate | 130.1 |
| dedup_line | 137737 | 2014 | 54.99% | empty_after_line_dedup | 18.7 |
| quality | 135723 | 17654 | 47.83% | gopher_word_count | 104.8 |
| pii | 118069 | 0 | 47.83% |  | 44.7 |

## Quality rules

Documents evaluated: 135723; violating at least one rule: 17654 (13.0%).

| # | Rule | Drop if | Failed | Dropped | Sole | p10 / p50 / p90 | us/doc |
|---:|---|---|---:|---:|---:|---|---:|
| 1 | c4_lorem_ipsum | present | 124 (0.1%) | 124 | 95 | 0 / 0 / 0 | 75 |
| 2 | c4_curly_bracket | present | 348 (0.3%) | 346 | 296 | 0 / 0 / 0 | 7 |
| 3 | gopher_word_count | < 53 or > 100000 | 8638 (6.4%) | 8621 | 3559 | 68 / 476 / 1569 | 3 |
| 4 | gopher_mean_word_length | < 3 or > 10 | 1957 (1.4%) | 1542 | 400 | 3.27 / 3.44 / 3.66 | 257 |
| 5 | gopher_symbol_ratio | > 0.1 | 68 (0.1%) | 52 | 47 | 0 / 0 / 0.00241 | 21 |
| 6 | gopher_bullet_lines | > 0.9 | 1110 (0.8%) | 869 | 764 | 0 / 0 / 0.143 | 19 |
| 7 | gopher_ellipsis_lines | > 0.3 | 0 (0.0%) | 0 | 0 | 0 / 0 / 0 | 14 |
| 8 | gopher_alpha_words | < 0.8 | 1746 (1.3%) | 400 | 198 | 0.931 / 0.981 / 0.999 | 1576 |
| 9 | gopher_stopwords | < 4 | 6204 (4.6%) | 1505 | 994 | 7 / 30 / 47 | 128 |
| 10 | gopher_dup_lines | > 0.3 | 4031 (3.0%) | 3039 | 2749 | 0 / 0 / 0.1 | 15 |
| 11 | gopher_dup_paragraphs | > 0.3 | 0 (0.0%) | 0 | 0 | 0 / 0 / 0 | 17 |
| 12 | gopher_top_2gram | > 0.2 | 1741 (1.3%) | 126 | 70 | 0.0197 / 0.0403 / 0.0887 | 874 |
| 13 | gopher_top_3gram | > 0.18 | 2989 (2.2%) | 317 | 143 | 0.0141 / 0.034 / 0.0899 | 864 |
| 14 | gopher_top_4gram | > 0.16 | 5729 (4.2%) | 679 | 678 | 0.0126 / 0.0336 / 0.101 | 867 |
| 15 | fineweb_line_punct | <= 0.12 | 0 (0.0%) | 0 | 0 | 1 / 1 / 1 | 18 |
| 16 | fineweb_short_lines | >= 0.67 | 214 (0.2%) | 34 | 34 | 0 / 0 / 0.0909 | 11 |
