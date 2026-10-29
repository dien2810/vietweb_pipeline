# Duplication in wet_200_final (CC-MAIN-2026-39, 200 WET files)

## Deduplication stages

| stage | documents in | removed | % |
|---|---:|---:|---:|
| dedup_exact | 31152 | 1005 | 3.23 |
| dedup_near | 30147 | 1013 | 3.36 |
| dedup_line | 29134 | 186 | 0.64 |

## Exact duplicates

- Documents entering: 31152; groups with 2+ identical texts: 629; removed copies: 1005
- Group size: median 2, max 22; groups of 2: 452 (71.9%)
- Removed copies whose whole group is on one domain: 894 (89.0%)

## Near duplicates (MinHash-LSH, 5-syllable shingles, 14 bands x 8 rows)

- Removed: 1013; matched document on the same domain: 760 (75.0%)
- Cluster size (kept document + its near duplicates): median 2, max 19

## Line level

- Lines removed, repeated in >= 3 documents of the same domain: 36704
- Lines removed, found on >= 20 domains: 11394 (73 distinct lines, in 5809 documents)
- Documents left empty: 186

## Domains (documents entering exact deduplication)

- Domains: 19858; with a single document: 14533 (73.2%); documents on domains with 10+ documents: 2414 (7.7%)

## Duplicate rate by number of WET files

Random nested subsets of the 200 files, 5 repeats (mean and standard deviation). exact_pct: share of documents that are exact copies; near_pct: share of the remaining documents removed as near duplicates.

```
          docs        exact_pct       near_pct      
          mean    std      mean   std     mean   std
files                                               
25      3895.0  45.06      0.85  0.21     0.71  0.06
50      7802.4  46.46      1.31  0.21     1.09  0.07
100    15554.8  76.72      2.16  0.16     1.78  0.14
150    23299.0  60.09      2.75  0.07     2.52  0.04
200    31152.0   0.00      3.23  0.00     3.36  0.00
```
