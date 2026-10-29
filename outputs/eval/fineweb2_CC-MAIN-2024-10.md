# Comparison with FineWeb-2, CC-MAIN-2024-10

- Our documents (collected with CLD2 'vie' and processed): 18575 from 50 WARC files
- FineWeb-2 rows of CC-MAIN-2024-10: 6350362; from the same 50 WARC files: 3085 (kept 1197, removed 1888)
- Our URLs present in FineWeb-2 (kept or removed): 3096 (16.7%); absent: 15479 (global deduplication, or not identified as vie_Latn)
- Absent among the documents we kept: 79.9%; among those we dropped: 87.4%
- FineWeb-2 Vietnamese documents from our WARC files that our collection never saw (CLD2 without 'vie', or under 200 characters): 14 (of which FineWeb-2 kept 4)

## Agreement on URLs present in both

- Overlap: 3096; agreement A = 0.6337; Cohen's kappa = 0.3145
- FineWeb-2 kept, we dropped: 5.04% of the overlap; FineWeb-2 removed, we kept: 31.59%

```
fw2           absent  kept  removed
kept                               
ours dropped    7454   156      915
ours kept       8025  1047      978
```

## Pages FineWeb-2 kept but we dropped, by our drop reason

```
      our drop reason  pages FineWeb-2 kept
        spam_keywords                   109
     langid_low_score                    15
     c4_curly_bracket                    13
     gopher_dup_lines                    10
       c4_lorem_ipsum                     3
boilerplate_too_short                     3
     gopher_top_4gram                     1
    gopher_word_count                     1
       near_duplicate                     1
```

## Pages FineWeb-2 removed, by FineWeb-2 filter_reason and our decision

```
ours                          ours dropped  ours kept  total
fw2_reason                                                  
line_punct_ratio                       768        588   1356
gopher_below_alpha_threshold            43        257    300
gopher_too_many_end_ellipsis            29         36     65
char_dup_ratio                          24         40     64
gopher_short_doc                        29         14     43
duplicated_5_n_grams                     2         21     23
list_ratio                              15          7     22
gopher_enough_stop_words                 3          2      5
dup_line_frac                            0          5      5
duplicated_10_n_grams                    0          2      2
duplicated_8_n_grams                     0          2      2
top_4_gram                               0          2      2
gopher_too_many_ellipsis                 1          1      2
gopher_below_avg_threshold               1          0      1
gopher_too_many_hashes                   0          1      1
```

## Pages both removed: our drop reason x FineWeb-2 filter_reason (top 15)

```
           drop_reason                   fw2_reason  pages
 boilerplate_too_short             line_punct_ratio    479
     gopher_word_count             line_punct_ratio     82
      langid_low_score             line_punct_ratio     42
        near_duplicate             line_punct_ratio     38
         spam_keywords             line_punct_ratio     27
      gopher_stopwords             line_punct_ratio     21
 boilerplate_too_short gopher_too_many_end_ellipsis     18
      gopher_dup_lines             line_punct_ratio     18
      c4_curly_bracket             line_punct_ratio     16
 boilerplate_too_short             gopher_short_doc     14
       exact_duplicate             line_punct_ratio     14
      c4_curly_bracket gopher_below_alpha_threshold      9
empty_after_line_dedup             line_punct_ratio      9
         spam_keywords gopher_below_alpha_threshold      9
 boilerplate_too_short               char_dup_ratio      9
```
