# Boilerplate removal vs trafilatura reference

Pages found in WARC: 737; pages whose trafilatura text has at least 200 characters: 562.

## Line-level agreement (character-weighted), best settings first

| precision | recall | f1 | pages_kept | pages_with_reference | pages_both | method | length_high | stopwords_high | stopwords_low | current_config |
|---|---|---|---|---|---|---|---|---|---|---|
| 0.7522 | 0.7601 | 0.7562 | 594 | 562 | 520 | c4_lines |  |  |  | False |
| 0.6919 | 0.7734 | 0.7304 | 479 | 562 | 445 | justext | 150 | 0.12 | 0.06 | False |
| 0.6874 | 0.778 | 0.7299 | 483 | 562 | 448 | justext | 150 | 0.1 | 0.06 | False |
| 0.7099 | 0.7475 | 0.7282 | 476 | 562 | 442 | justext | 150 | 0.12 | 0.08 | True |
| 0.7046 | 0.7523 | 0.7277 | 479 | 562 | 445 | justext | 150 | 0.1 | 0.08 | False |
| 0.7008 | 0.755 | 0.7268 | 444 | 562 | 420 | justext | 150 | 0.15 | 0.06 | False |
| 0.6864 | 0.7671 | 0.7245 | 468 | 562 | 433 | justext | 120 | 0.15 | 0.06 | False |
| 0.6861 | 0.7661 | 0.7239 | 505 | 562 | 455 | justext | 120 | 0.1 | 0.08 | False |
| 0.6909 | 0.76 | 0.7238 | 499 | 562 | 451 | justext | 120 | 0.12 | 0.08 | False |
| 0.718 | 0.7294 | 0.7236 | 440 | 562 | 416 | justext | 150 | 0.15 | 0.08 | False |
| 0.6734 | 0.7812 | 0.7233 | 502 | 562 | 454 | justext | 120 | 0.12 | 0.06 | False |
| 0.7033 | 0.7434 | 0.7228 | 465 | 562 | 430 | justext | 120 | 0.15 | 0.08 | False |

Current configuration:

| precision | recall | f1 | pages_kept | pages_with_reference | pages_both | method | length_high | stopwords_high | stopwords_low | current_config |
|---|---|---|---|---|---|---|---|---|---|---|
| 0.7099 | 0.7475 | 0.7282 | 476 | 562 | 442 | justext | 150 | 0.12 | 0.08 | True |

## Quality stage on the three versions

| pages | wet | wet_boilerplate | trafilatura |
|---|---|---|---|
| pages entering quality (>= min_chars_after) | 736 | 476 | 562 |
| pages passing quality | 167 | 329 | 360 |

| rule (% of pages failing) | wet | wet_boilerplate | trafilatura |
|---|---|---|---|
| c4_lorem_ipsum | 0.7 | 0.2 | 0.2 |
| c4_curly_bracket | 3.3 | 0.8 | 0.4 |
| gopher_word_count | 0.0 | 1.0 | 3.2 |
| gopher_mean_word_length | 0.8 | 0.6 | 2.3 |
| gopher_symbol_ratio | 0.1 | 0.2 | 0.5 |
| gopher_bullet_lines | 0.0 | 0.2 | 2.1 |
| gopher_ellipsis_lines | 0.0 | 2.5 | 3.4 |
| gopher_alpha_words | 2.7 | 0.4 | 8.5 |
| gopher_stopwords | 5.7 | 0.0 | 11.2 |
| gopher_dup_lines | 27.3 | 8.4 | 1.4 |
| gopher_dup_paragraphs | 0.0 | 0.0 | 0.2 |
| gopher_top_2gram | 0.4 | 0.2 | 0.2 |
| gopher_top_3gram | 1.6 | 1.0 | 1.2 |
| gopher_top_4gram | 3.3 | 1.5 | 2.1 |
| fineweb_line_punct | 47.0 | 12.4 | 16.0 |
| fineweb_dup_line_chars | 45.1 | 10.7 | 2.5 |
| fineweb_short_lines | 57.5 | 13.7 | 4.6 |
