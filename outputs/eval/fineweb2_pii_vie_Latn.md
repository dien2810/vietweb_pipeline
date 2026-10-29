# PII patterns on FineWeb-2 vie_Latn

10000 documents from 10 files, dumps CC-MAIN-2013-20 to CC-MAIN-2023-50; 0.02 GB read

| pattern | documents with a match | % | matches |
|---|---:|---:|---:|
| email | 5 | 0.05 | 5 |
| ipv4 | 22 | 0.22 | 52 |
| phone_vn | 751 | 7.51 | 1401 |
| cccd | 2 | 0.02 | 2 |

FineWeb-2 anonymises e-mail and IP addresses; matches of example.com / example.org are not counted.
Phone numbers and 12-digit numbers are not anonymised by FineWeb-2. The patterns over-match (see LUAT_LOC.md, section 8), so read the counts as upper bounds and check a sample by hand.