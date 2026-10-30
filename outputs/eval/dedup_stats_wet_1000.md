# Duplication in wet_1000 (CC-MAIN-2026-39, 1000 WET files)

## Deduplication stages

| stage | documents in | removed | % |
|---|---:|---:|---:|
| dedup_exact | 157687 | 10480 | 6.65 |
| dedup_near | 147207 | 9470 | 6.43 |
| dedup_line | 137737 | 2014 | 1.46 |

## Exact duplicates

- Documents entering: 157687; groups with 2+ identical texts: 4199; removed copies: 10480
- Group size: median 2, max 102; groups of 2: 2299 (54.8%)
- Removed copies whose whole group is on one domain: 9370 (89.4%)

## Near duplicates (MinHash-LSH, 5-syllable shingles, 14 bands x 8 rows)

- Removed: 9470; matched document on the same domain: 7462 (78.8%)
- Cluster size (kept document + its near duplicates): median 2, max 98

## Line level

- Lines removed, repeated in >= 3 documents of the same domain: 387994
- Lines removed, found on >= 20 domains: 38314 (279 distinct lines, in 19444 documents)
- Documents left empty: 2014

## Domains (documents entering exact deduplication)

- Domains: 58569; with a single document: 32050 (54.7%); documents on domains with 10+ documents: 42651 (27.0%)

## Duplicate rate by number of WET files

Random nested subsets of the 1000 files, 5 repeats (mean and standard deviation). exact_pct: share of documents that are exact copies; near_pct: share of the remaining documents removed as near duplicates.

```
           docs         exact_pct       near_pct      
           mean     std      mean   std     mean   std
files                                                 
25       3976.2   49.63      0.97  0.11     0.41  0.09
50       7939.4   49.20      1.46  0.25     0.52  0.08
100     15848.4  149.29      2.12  0.13     0.81  0.11
150     23827.6  107.81      2.70  0.17     1.16  0.11
200     31702.0  144.05      3.13  0.09     1.45  0.10
400     63099.4  184.94      4.44  0.09     2.60  0.11
600     94647.6  202.85      5.34  0.08     3.88  0.14
800    126159.8  168.86      6.07  0.06     5.16  0.09
1000   157687.0    0.00      6.65  0.00     6.43  0.00
```
