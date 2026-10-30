Run: 12304 documents in, 5125 kept; langid=heuristic, quality unit=syllable, near-dup unit=syllable.

## Funnel

| Stage | In | Removed | Kept (% of input) | Top reason | Seconds |
|---|---:|---:|---:|---|---:|
| normalize | 12304 | 0 | 100.0% |  | 257.6 |
| boilerplate | 12304 | 4507 | 63.37% | boilerplate_too_short | 313.2 |
| langid | 7797 | 7 | 63.31% | langid_low_score | 22.0 |
| url_filter | 7790 | 648 | 58.05% | spam_keywords | 2.2 |
| dedup_exact | 7142 | 113 | 57.13% | exact_duplicate | 6.7 |
| dedup_near | 7029 | 94 | 56.36% | near_duplicate | 50.6 |
| dedup_line | 6935 | 9 | 56.29% | empty_after_line_dedup | 2.6 |
| quality | 6926 | 1801 | 41.65% | fineweb_line_punct | 42.2 |
| pii | 5125 | 0 | 41.65% |  | 12.8 |

## Quality rules

Documents evaluated: 6926; violating at least one rule: 1801 (26.0%).

| # | Rule | Drop if | Failed | Dropped | Sole | p10 / p50 / p90 | us/doc |
|---:|---|---|---:|---:|---:|---|---:|
| 1 | c4_lorem_ipsum | present | 2 (0.0%) | 2 | 2 | 0 / 0 / 0 | 87 |
| 2 | c4_curly_bracket | present | 52 (0.8%) | 52 | 40 | 0 / 0 / 0 | 9 |
| 3 | gopher_word_count | < 50 or > 100000 | 83 (1.2%) | 83 | 44 | 118 / 698 / 2101 | 3 |
| 4 | gopher_mean_word_length | < 3 or > 10 | 26 (0.4%) | 22 | 6 | 3.3 / 3.45 / 3.66 | 275 |
| 5 | gopher_symbol_ratio | > 0.1 | 4 (0.1%) | 3 | 1 | 0 / 0 / 0.00702 | 23 |
| 6 | gopher_bullet_lines | > 0.9 | 18 (0.3%) | 15 | 12 | 0 / 0 / 0.106 | 33 |
| 7 | gopher_ellipsis_lines | > 0.3 | 146 (2.1%) | 131 | 124 | 0 / 0 / 0.0667 | 25 |
| 8 | gopher_alpha_words | < 0.8 | 37 (0.5%) | 25 | 7 | 0.926 / 0.973 / 0.994 | 1484 |
| 9 | gopher_stopwords | < 2 | 8 (0.1%) | 4 | 0 | 12 / 34 / 48 | 144 |
| 10 | gopher_dup_lines | > 0.3 | 402 (5.8%) | 387 | 46 | 0 / 0 / 0.226 | 22 |
| 11 | gopher_dup_paragraphs | > 0.3 | 0 (0.0%) | 0 | 0 | 0 / 0 / 0 | 19 |
| 12 | gopher_top_2gram | > 0.2 | 16 (0.2%) | 8 | 0 | 0.0194 / 0.0399 / 0.0799 | 905 |
| 13 | gopher_top_3gram | > 0.18 | 36 (0.5%) | 20 | 8 | 0.0136 / 0.0329 / 0.0764 | 893 |
| 14 | gopher_top_4gram | > 0.16 | 66 (1.0%) | 24 | 13 | 0.0122 / 0.0322 / 0.0789 | 916 |
| 15 | fineweb_line_punct | <= 0.12 | 690 (10.0%) | 480 | 245 | 0.121 / 0.471 / 1 | 37 |
| 16 | fineweb_dup_line_chars | >= 0.1 | 587 (8.5%) | 227 | 187 | 0 / 0 / 0.0862 | 43 |
| 17 | fineweb_short_lines | >= 0.67 | 809 (11.7%) | 318 | 318 | 0 / 0.276 / 0.697 | 18 |
