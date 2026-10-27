# vietweb

Pipeline thu thập, làm sạch và kiểm định văn bản web tiếng Việt từ Common Crawl — đề tài môn Kỹ thuật xử lý dữ liệu (UIT).

**Bắt đầu từ đâu:** đọc [HUONG_DAN_CHAY.md](HUONG_DAN_CHAY.md).

Quy ước ngôn ngữ: code, comment, cấu hình, log và thông báo lỗi viết bằng tiếng Anh; tài liệu `.md` viết bằng tiếng Việt. Chuỗi tiếng Việt trong code chỉ là dữ liệu (văn bản mẫu, bảng chữ cái, từ dừng, từ khóa spam).

## Cấu trúc

```
vietweb/
├── HUONG_DAN_CHAY.md          Hướng dẫn cài đặt và thứ tự chạy
├── LUAT_LOC.md                Danh mục luật lọc: ngưỡng, số liệu, nhật ký thay đổi
├── configs/
│   ├── pipeline.yaml          Cấu hình chính: bản crawl, thứ tự tầng, tham số từng tầng
│   ├── vie_thresholds.yaml    Ngưỡng luật lọc chất lượng (đang là ngưỡng gốc, cần hiệu chỉnh)
│   ├── stopwords_vi.txt       Từ dừng tiếng Việt
│   └── blocklist_*.txt        Tên miền và từ khóa spam
├── src/vietweb/
│   ├── cli.py                 Dòng lệnh: python -m vietweb <lệnh>
│   ├── collect.py             Tầng 1–2: tải WET, lọc sơ bộ tiếng Việt, lưu Parquet thô
│   ├── io/                    Common Crawl (HTTP có thử lại) và lưu trữ Parquet / manifest
│   ├── text/                  Chuẩn hóa tiếng Việt, tách âm tiết / từ / shingle
│   ├── stages/                Tầng 3–8: normalize, boilerplate (3b), langid, url_filter, dedup, quality, pii
│   ├── pipeline.py            Chạy các tầng, ghi funnel, xuất dữ liệu (tầng 9)
│   ├── reference.py           Bản tham chiếu: tải WARC, trích văn bản bằng trafilatura
│   ├── ordering.py            RQ4: gợi ý thứ tự luật lọc theo chi phí
│   ├── eval/                  Gán nhãn, precision, kappa, so sánh shingle, so tầng 3b với trafilatura, khung đối chiếu FineWeb-2
│   ├── validation.py          Kiểm tra đầu ra
│   └── spark_runner.py        Khung chạy trên Spark (chưa kiểm thử)
├── scripts/
│   ├── make_sample_wet.py     Tạo file WET giả lập để chạy thử không cần mạng
│   ├── plot_report_figures.py Sinh hình cho báo cáo
│   └── rule_stats.py          Thống kê từng luật sau mỗi lần chạy (cho LUAT_LOC.md)
├── dashboard/app.py           Dashboard Streamlit
├── flows/pipeline_flow.py     Khung điều phối Prefect (chưa kiểm thử)
├── docs/dataset_card.md       Mẫu dataset card
└── tests/                     pytest (23 test, chạy offline)
```

Dữ liệu (`data/`) và kết quả trung gian không đưa lên Git (xem `.gitignore`).
