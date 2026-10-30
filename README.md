# vietweb

Pipeline thu thập, làm sạch và kiểm định văn bản web tiếng Việt từ Common Crawl — đề tài môn Kỹ thuật xử lý dữ liệu (UIT).

**Cài đặt và tái lập kết quả:** [HUONG_DAN_CHAY.md](HUONG_DAN_CHAY.md).

**Demo:** `streamlit run dashboard/demo.py` (thử pipeline trên một trang, MinHash trên hai văn bản, kết quả chính; xem mục 6 của hướng dẫn).

Quy ước ngôn ngữ: code, comment, cấu hình, log và thông báo lỗi viết bằng tiếng Anh; tài liệu `.md` viết bằng tiếng Việt. Chuỗi tiếng Việt trong code chỉ là dữ liệu (văn bản mẫu, bảng chữ cái, từ dừng, từ khóa spam).

## Kết quả chính

Lần chạy chính `wet_200_final`: 200 file WET của CC-MAIN-2026-39, 48.815 bản ghi tiếng Việt, giữ lại 25.255 tài liệu (51,7%). Lần chạy `wet_1000` (1.000 file, 246.833 bản ghi) giữ lại 118.069 tài liệu (47,8%). Số liệu chi tiết nằm trong `LUAT_LOC.md` (số mục ghi trong ngoặc).

- **RQ1 – hiệu chỉnh:** bỏ boilerplate bằng luật dòng C4 (F1 0,756 so với trafilatura, jusText 0,728); nâng 2 ngưỡng, tắt `fineweb_dup_line_chars` (mục 3b, 7.4). Đếm theo từ (underthesea) không tốt hơn đếm âm tiết với ngưỡng tương ứng mà chậm hơn khoảng 130 lần (mục 14.4).
- **RQ2 – trùng lặp:** 3,23% trùng chính xác, 3,36% trùng gần đúng ở 200 file; 6,65% và 6,43% ở 1.000 file. Phần lớn nằm trong cùng một website; tốc độ tăng chậm dần khi dữ liệu lớn lên (mục 13, 14.6).
- **RQ3 – FineWeb-2:** trên CC-MAIN-2024-10, A = 0,634, κ = 0,31; 109 trang bị luật từ khóa cờ bạc của pipeline loại vẫn có trong FineWeb-2; 7,51% tài liệu `vie_Latn` được lấy mẫu có số điện thoại Việt Nam (mục 12).
- **RQ4 – thứ tự lọc và tốc độ:** sắp luật theo chi phí không nhanh hơn (0,97 lần); tầng chuẩn hóa là phần tốn nhất. Chạy ftfy theo dòng và 8 tiến trình: 4,2 ms/tài liệu ở 1.000 file, so với 17,1 ms ở 200 file khi chạy một tiến trình; trên cùng 200 file, kết quả giống hệt bản một tiến trình (mục 7.5, 14.1, 14.6).
- **Thí nghiệm mở rộng:** GlotLID giữ thêm 437 trang so với heuristic, trong đó có spam cờ bạc viết không dấu (mục 14.3); mô hình ngôn ngữ nhỏ học trên dữ liệu sạch có perplexity trên Wikipedia thấp hơn khoảng 1,9 lần so với dữ liệu thô cùng số token (mục 14.8); 17–65 câu VMLU xuất hiện gần nguyên văn trong dữ liệu 1.000 file (mục 14.7).

Mô tả dữ liệu đầu ra: [docs/dataset_card.md](docs/dataset_card.md). Văn bản đã xử lý và các file mẫu có văn bản gốc không được đưa lên Git.

## Cấu trúc

```
vietweb/
├── HUONG_DAN_CHAY.md          Hướng dẫn cài đặt và tái lập kết quả
├── LUAT_LOC.md                Danh mục luật lọc: ngưỡng, số liệu, thay đổi so với cấu hình gốc, kết quả thí nghiệm
├── configs/
│   ├── pipeline.yaml          Cấu hình chính: bản crawl, thứ tự tầng, tham số từng tầng
│   ├── vie_thresholds.yaml    Ngưỡng luật lọc chất lượng, đã hiệu chỉnh cho tiếng Việt
│   ├── stopwords_vi.txt       Từ dừng tiếng Việt
│   └── blocklist_*.txt        Tên miền và từ khóa spam
├── src/vietweb/
│   ├── cli.py                 Dòng lệnh: python -m vietweb <lệnh>
│   ├── collect.py             Tầng 1–2: tải WET, lọc sơ bộ tiếng Việt, lưu Parquet thô
│   ├── io/                    Common Crawl (HTTP có thử lại) và lưu trữ Parquet / manifest
│   ├── text/                  Chuẩn hóa tiếng Việt, chuyển TCVN3/VNI, tách âm tiết / từ / shingle
│   ├── stages/                Tầng 3–8: normalize, boilerplate (3b), langid, url_filter, dedup, quality, pii
│   ├── pipeline.py            Chạy các tầng, ghi funnel, xuất dữ liệu (tầng 9)
│   ├── parallel.py            Chạy song song các tầng xử lý từng tài liệu
│   ├── reference.py           Bản tham chiếu: tải WARC, trích văn bản bằng trafilatura
│   ├── ordering.py            RQ4: gợi ý thứ tự luật lọc theo chi phí
│   ├── explain.py             Giải thích quyết định của từng tầng trên một trang (dùng cho demo)
│   ├── eval/                  Gán nhãn, precision, kappa, so sánh shingle, so tầng 3b với trafilatura, đối chiếu FineWeb-2
│   ├── validation.py          Kiểm tra đầu ra
│   └── spark_runner.py        Chạy tầng 3–9 trên Spark, kết quả giống bản pandas
├── scripts/
│   ├── make_sample_wet.py     Tạo file WET giả lập để chạy thử không cần mạng
│   ├── plot_report_figures.py Sinh hình funnel và phân phối các chỉ số chất lượng từ outputs/stats
│   ├── plot_results_figures.py Sinh hình kết quả (tiếng Việt và tiếng Anh)
│   ├── rule_stats.py          Thống kê từng luật của một lần chạy
│   ├── compare_runs.py        Kiểm hai lần chạy cho kết quả giống hệt nhau
│   ├── calibration_sample.py  RQ1: lấy mẫu gán nhãn mù quanh ngưỡng, chấm kết quả
│   ├── word_unit_eval.py      RQ1: đếm theo âm tiết hay theo từ (underthesea)
│   ├── quality_model.py       RQ1: bộ phân loại fastText và perplexity học từ Wikipedia
│   ├── dedup_stats.py         RQ2: thống kê trùng lặp theo số file
│   ├── time_quality_order.py  RQ4: đo thời gian tầng 7 theo hai thứ tự luật
│   ├── bench_parallel.py      RQ4: tốc độ tầng 3 và 3b theo số tiến trình
│   ├── langid_compare.py      So heuristic với GlotLID ở tầng 4
│   ├── legacy_eval.py         Thử chuyển TCVN3/VNI trên văn bản tổng hợp
│   ├── legacy_scan.py         Đếm trang TCVN3/VNI trong file WET (mọi ngôn ngữ)
│   ├── benchmark_overlap.py   Dò câu benchmark (VMLU) trong dữ liệu đã làm sạch
│   └── lm_ablation.py         Huấn luyện GPT nhỏ trên dữ liệu thô và dữ liệu sạch
├── dashboard/app.py           Dashboard Streamlit: duyệt kết quả
├── dashboard/demo.py          Ứng dụng demo cho buổi thuyết trình
├── flows/pipeline_flow.py     Khung điều phối Prefect (chưa kiểm thử)
├── docs/dataset_card.md       Dataset card của lần chạy wet_200_final
└── tests/                     pytest (42 test, chạy offline)
```

Dữ liệu (`data/`) và kết quả trung gian không đưa lên Git (xem `.gitignore`).
