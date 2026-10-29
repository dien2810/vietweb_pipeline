# Danh mục luật lọc

File này liệt kê mọi luật pipeline dùng để loại, sửa hoặc che văn bản. Với mỗi luật có ngưỡng hiện tại, nguồn gốc của ngưỡng, số liệu đo được và trạng thái. Hai mục cuối là nhật ký thay đổi ngưỡng và lịch sử các lần chạy.

Số liệu trong file lấy từ lần chạy **`baseline_wet_10`**:
- dữ liệu: CC-MAIN-2026-39, 10 file WET, 2.414 tài liệu;
- cấu hình: langid `heuristic`, đơn vị đếm là âm tiết, ngưỡng gốc;
- chạy xong lúc 30/09/2026 18:09 (UTC).

Riêng tầng 3b (thêm ngày 03/10/2026) dùng số liệu của lần chạy `wet_50_bp` (50 file).

## Cách dùng

- **Mã luật:** chính là giá trị `drop_reason` trong `data\processed\dropped\`. Xem ví dụ bị loại bằng:
  ```powershell
  python -m vietweb peek --reason <mã> -n 5
  ```
- **Lấy số liệu sau mỗi lần chạy:** lệnh dưới in funnel và bảng thống kê 17 luật chất lượng (cần `quality.save_stats: true`).
  ```powershell
  python scripts\rule_stats.py --out outputs\stats\rule_stats.md
  ```
  Chép các số chính vào mục 11.
- **Khi đổi ngưỡng hoặc bật/tắt luật:** sửa file cấu hình, thêm một dòng vào mục 10 và cập nhật cột *Trạng thái*.
- **Sao lưu trước khi chạy lại**, vì `run` ghi đè `outputs\` và `data\processed\`:
  ```powershell
  $run = "baseline_wet_10"          # tên lần chạy
  New-Item -ItemType Directory -Force outputs\runs | Out-Null
  Copy-Item -Recurse outputs\stats outputs\runs\$run
  Copy-Item -Recurse data\processed outputs\runs\$run\processed
  ```

Ý nghĩa cột *Trạng thái*:

| Trạng thái | Nghĩa |
|---|---|
| gốc | Ngưỡng lấy nguyên từ bài báo (thiết kế cho tiếng Anh; với FineWeb là văn bản đã được trafilatura trích ra) |
| tạm | Luật hoặc ngưỡng tự đặt, chưa đo độ chính xác |
| cần xem | Số liệu baseline cho thấy có vấn đề, xem cột *Ghi chú* |
| đã hiệu chỉnh | Đã đổi ngưỡng, có ghi ở mục 10 |
| chưa viết | Có trong kế hoạch, chưa có code |

Ngưỡng viết trong `code` là giá trị y như trong file cấu hình (dùng dấu chấm thập phân). Số liệu đo được viết theo kiểu Việt Nam (dấu phẩy thập phân).

## 1. Tổng quan

| Tầng | Số luật | Hành động | Baseline | Cấu hình | Code |
|---|---:|---|---|---|---|
| 1–2. Thu thập | 2 | loại | 211.717 → 2.414 bản ghi | `collect` | `io/commoncrawl.py` |
| 3. Chuẩn hóa | 5 | sửa; 1 luật có thể loại | 0 bị loại, 2 gắn cờ mã cũ | `normalize` | `stages/s03_normalize.py`, `text/normalize.py` |
| 3b. Bỏ boilerplate | 5 | sửa; loại trang còn quá ngắn | chưa có trong baseline; `wet_50_bp`: −4.507 trang, bỏ 63,8% số ký tự | `boilerplate` | `stages/s03b_boilerplate.py` |
| 4. Nhận diện ngôn ngữ | 1 | loại | −375 | `langid` | `stages/s04_langid.py` |
| 5. Lọc URL, từ khóa | 2 | loại | −172 | `url_filter`, `blocklist_*.txt` | `stages/s05_url_filter.py` |
| 6. Khử trùng lặp | 3 | loại; xóa dòng | −24 tài liệu, −3.930 dòng | `dedup` | `stages/s06_dedup.py` |
| 7. Chất lượng | 17 | loại | −1.406 | `quality`, `vie_thresholds.yaml` | `stages/s07_quality.py` |
| 8. PII | 4 | che | 1.637 lần che | `pii` | `stages/s08_pii.py` |
| **Tổng** | **39** | | **2.414 → 437 (18,1%)** | | |

Cấu hình nằm trong `configs/pipeline.yaml` trừ khi ghi khác. Code nằm trong `src/vietweb/`.

## 2. Tầng 1–2: Thu thập

Hai luật này chạy lúc đọc file WET, không có `drop_reason`.

| Luật (khóa cấu hình) | Loại khi | Ngưỡng | Nguồn | Trạng thái | Ghi chú |
|---|---|---|---|---|---|
| `collect.language_prefilter` | Trường `WARC-Identified-Content-Language` (CLD2) không chứa mã này | `vie` | Common Crawl | cần xem | Lấy bản ghi có `vie` ở **bất kỳ vị trí nào**. 314/2.414 bản ghi có ngôn ngữ chính khác (Anh, Trung...), phần lớn bị tầng 4 loại sau đó. Chưa đo số trang tiếng Việt mà CLD2 bỏ sót (gọi `iter_wet_records(language=None)` để đo). |
| `collect.min_chars` | Văn bản ngắn hơn ngưỡng (ký tự) | `200` | tự đặt | tạm | Manifest chưa tách số bản ghi bị loại theo từng luật; hiện chỉ có tổng 211.717 → 2.414. |

## 3. Tầng 3: Chuẩn hóa

Các phép sửa áp dụng cho mọi tài liệu. Baseline: 2.414/2.414 tài liệu bị thay đổi ít nhất một ký tự (chưa tách theo từng phép). Tầng này mất 57,8 trên tổng 116 giây.

| Luật (khóa cấu hình) | Làm gì | Giá trị | Trạng thái | Ghi chú |
|---|---|---|---|---|
| `normalize.fix_mojibake` | Sửa lỗi mã hóa bằng ftfy | `true` | tạm | Giả định chưa đo: ftfy trên văn bản dài là phần chậm nhất của tầng |
| `normalize.unicode_form` | Chuẩn hóa Unicode | `NFC` | gốc | |
| `normalize.tone_mark_style` | Thống nhất vị trí dấu thanh | `old` (hòa, thủy) | tạm | `new` cho hoà, thuỷ; `none` giữ nguyên |
| (luôn bật) | Bỏ ký tự điều khiển và zero-width, gộp khoảng trắng, tối đa một dòng trống liên tiếp | — | gốc | |
| `legacy_encoding` | Điểm TCVN3/VNI ≥ ngưỡng: gắn cờ (`flag`) hoặc loại (`drop`) | `0.02`, `flag` | tạm | 2 tài liệu bị gắn cờ. Chưa có bộ chuyển đổi (`convert_legacy`) |

## 3b. Tầng 3b: Bỏ boilerplate

Thêm ngày 03/10/2026, chạy ngay sau tầng 3. Tầng này bỏ các dòng menu, sidebar, footer và loại trang còn quá ngắn.
- Từ 26/10/2026, phương pháp đang dùng là `method: c4_lines` (luật theo dòng của C4), chọn bằng `extract-eval` (xem cuối mục này và mục 10).
- jusText (Pomikálek, 2011), áp dụng cho từng dòng thay vì từng khối HTML, giữ làm phương án thay thế (`method: justext`). Hai bảng ngay dưới mô tả jusText.
- Tham số nằm ở mục `boilerplate` trong `configs/pipeline.yaml`.
- Số liệu lấy từ lần chạy `wet_50_bp` (jusText). Lần chạy 50 file với `c4_lines` là `wet_50_c4` (mục 11).

**Bước 1: phân loại từng dòng, chưa xét ngữ cảnh.** Kiểm tra theo thứ tự trong bảng; dòng khớp điều kiện nào trước thì nhận loại đó.

| Luật (khóa cấu hình) | Dòng bị xếp loại | Tham số | Nguồn | Trạng thái |
|---|---|---|---|---|
| `bad_patterns` | bad nếu chứa ©, "copyright", "bản quyền" hoặc "all rights reserved" | 4 mẫu | jusText (dấu ©) | tạm |
| `max_url_ratio` | bad nếu URL chiếm hơn ngưỡng số ký tự của dòng | `0.3` | Thay cho mật độ liên kết của jusText, vì WET không còn thẻ `<a>` | tạm |
| `length_low` | short nếu ngắn hơn ngưỡng | `70` ký tự | jusText | gốc |
| mật độ từ dừng (`stopwords_low`, `stopwords_high`, `length_high`) | Mật độ ≥ `stopwords_high`: good nếu dòng dài ≥ `length_high`, ngược lại neargood. Mật độ ≥ `stopwords_low`: neargood. Còn lại: bad | `0.08`, `0.12`, `150` | jusText (tiếng Anh: 0,30 / 0,32 / 200) | tạm |

**Bước 2–3: xét ngữ cảnh, giữ nguyên quy tắc của jusText.**
- Dòng short lấy loại của dòng good/bad gần nhất ở hai phía. Đầu và cuối trang được tính là bad.
- Dòng neargood thành good, trừ khi cả hai phía đều là bad.
- Cuối cùng chỉ giữ các dòng good.

| Mã | Loại khi | Ngưỡng | `wet_50_bp` | Trạng thái |
|---|---|---|---|---|
| `boilerplate_too_short` | Văn bản còn lại ngắn hơn ngưỡng | `min_chars_after: 200` | −4.507 (36,6%), trong đó 1.358 trang có ngôn ngữ chính theo CLD2 không phải tiếng Việt | tạm |

**Phương án đang dùng `method: c4_lines`** (luật theo dòng của C4):
- Chỉ giữ dòng kết thúc bằng dấu câu (`.` `!` `?` `"` `”` `…`) và có ít nhất `c4_min_words: 5` âm tiết.
- Bỏ dòng chứa "javascript".
- `c4_drop_ellipsis: true` (thêm ngày 27/10/2026): bỏ cả dòng kết thúc bằng "..." hoặc "…". Trên trang WET, đây phần lớn là đoạn trích bị cắt của bài khác ("Xem thêm…"). Trước khi có luật này, `gopher_ellipsis_lines` loại cả trang chỉ vì vài dòng như vậy (772 trang ở `wet_50_c4`).
- Loại trang còn ít hơn `min_chars_after: 200` ký tự (mã `boilerplate_too_short`). Luật "ít hơn 3 câu" của C4 chưa viết.

Kết quả `extract-eval` (3 file WARC, 737 trang, chạy ngày 09/10/2026; văn bản trafilatura làm tham chiếu; F1 tính theo số ký tự của dòng):

| Phương pháp | Precision | Recall | F1 | Trang có nội dung bị bỏ (/562) | Trang qua tầng 7 | Đồng thuận tập trang qua tầng 7 với trafilatura (Jaccard) |
|---|---|---|---|---|---|---|
| `c4_lines` (đang dùng) | 0,752 | 0,760 | 0,756 | 42 | 432 | 0,647 |
| jusText tốt nhất (`stopwords_low 0.06`) | 0,692 | 0,773 | 0,730 | 117 | 321 | 0,625 |
| jusText cũ (150 / 0,12 / 0,08) | 0,710 | 0,748 | 0,728 | 120 | 329 | 0,644 |
| Giữ hết (`none`) | 0,343 | 1,000 | 0,511 | 0 | 167 | — |
| Văn bản trafilatura | | | | | 360 | 1 |

Ghi chú về lựa chọn này:
- Chênh lệch F1 giữa `c4_lines` và jusText cũ là +0,028 (khoảng tin cậy 95% bootstrap theo trang: +0,005 đến +0,051). Chỉ có 3 file, các trang trong cùng file không độc lập, nên khoảng này lạc quan. Chênh lệch giữa jusText tốt nhất và jusText cũ (+0,002) nằm trong nhiễu.
- Ở cấp tài liệu, hai phương pháp đồng thuận với trafilatura gần như ngang nhau (Jaccard 0,647 và 0,644). `c4_lines` giữ được nhiều trang hơn nhưng cũng cho qua nhiều trang kém hơn.
- 98% số ký tự nội dung mà `c4_lines` bỏ sót nằm ở dòng không kết thúc bằng dấu câu: tiêu đề, mục liệt kê, ô bảng. Với jusText tỉ lệ này là 48%.
- `c4_lines` cho qua tầng 7 thêm 121 trang mà bản trafilatura không qua. Đọc 8 trang mẫu: phần lớn là boilerplate dạng câu ("Chưa có sản phẩm trong giỏ hàng.", "This entry was posted in…"), trang xổ số, cờ bạc. Bài đánh giá chỉ chạy tầng 7, chưa qua tầng 5 và 6, nên một phần các trang này sẽ bị loại ở pipeline thật.
- Vì mọi dòng còn lại đều kết thúc bằng dấu câu và đủ 5 âm tiết, luật `fineweb_line_punct` và `fineweb_short_lines` gần như không còn loại trang nào. Khi hiệu chỉnh ngưỡng (RQ1) cần ghi rõ điều này.
- 24 trong 49 trang mà bản trafilatura qua tầng 7 còn `c4_lines` trượt là do `gopher_ellipsis_lines`: `c4_lines` giữ các dòng trích dẫn bị cắt, kết thúc bằng "…". Thử bỏ thêm các dòng này (chưa viết vào code): F1 0,750, Jaccard 0,666.

Ghi chú:
- **Lượng bị bỏ:** ở `wet_50_bp`, tầng 3b bỏ 2.128.594 dòng, tức 63,8% số ký tự.
- **Ngưỡng từ dừng** chọn theo phân phối của 50 file: với các dòng từ 200 ký tự trở lên và kết thúc bằng dấu câu, p10 là 0,11, trung vị là 0,21.
- **`length_high` đặt 150 thay vì 200.** Với 200, trang có mọi đoạn dài 150–199 ký tự không có dòng good nào làm "neo", nên bị xóa sạch: 198/2.300 trang được giữ ở `wet_50` rơi vào trường hợp này. Với 150, con số còn 133.
- **Tầng 3b làm luôn việc lọc ngôn ngữ.** Trang không phải tiếng Việt mất gần hết các dòng ở đây vì cách phân loại dựa trên từ dừng tiếng Việt. Sau tầng 3b, tầng 4 chỉ còn loại 7 tài liệu (trước đó là 1.883). Số `too_short_cld2_not_vie` trong `funnel.csv` tách riêng nhóm trang này.
- **Trùng lặp thay đổi:**
  - Trùng chính xác tăng từ 30 lên 113, vì các trang cùng nội dung nhưng khác menu nay trở thành giống hệt nhau.
  - Trùng gần đúng giảm từ 334 xuống 94.
- **Có tài liệu tốt bị mất:** 245 tài liệu được giữ ở `wet_50` bị loại ở `wet_50_bp`, trong đó 127 tài liệu do tầng 3b. Cần đọc tay các trang này.
- **Tham số hiện là giá trị khởi điểm.** Chọn lại bằng `extract-eval`, so với văn bản trafilatura trích từ WARC (`HUONG_DAN_CHAY.md`, mục 5b).

## 4. Tầng 4: Nhận diện ngôn ngữ

| Mã | Loại khi | Ngưỡng | Nguồn | Baseline | Trạng thái |
|---|---|---|---|---|---|
| `langid_low_score` | Điểm heuristic < ngưỡng. Điểm = 0,6 × min(1, tỉ lệ âm tiết có dấu / 0,5) + 0,4 × min(1, tỉ lệ từ dừng / 0,12) | `0.6` | tự đặt | −375 (15,5%); điểm trung bình 0,78 | tạm |

Ghi chú:
- **Phần lớn bị loại đúng:** ngôn ngữ chính theo CLD2 của 375 tài liệu bị loại là Anh 220, Việt 68, Đức 12, Trung 11, Nhật 10, còn lại là ngôn ngữ khác.
- **68 trang tiếng Việt bị loại:** chủ yếu là trang sản phẩm toàn menu. Đây là vấn đề boilerplate (xem mục 7), không phải lỗi ngôn ngữ.
- **Giới hạn:** văn bản tiếng Việt không dấu sẽ bị chấm điểm thấp.
- **Kế hoạch:** chuyển sang GlotLID (tuần 8–10).

## 5. Tầng 5: Lọc URL và từ khóa

| Mã | Loại khi | Ngưỡng | Nguồn | Baseline | Trạng thái | Ghi chú |
|---|---|---|---|---|---|---|
| `url_blocklist` | Tên miền (kể cả tên miền con) có trong `blocklist_domains.txt` | 1 mục mẫu | tự đặt | 0 | chưa viết | Danh sách mới có ví dụ mẫu. Kế hoạch: danh sách UT1 (tuần 8–10) |
| `spam_keywords` | Tổng số lần xuất hiện của 12 từ khóa trong `blocklist_keywords.txt` ≥ ngưỡng | `keyword_min_hits: 3` | tự đặt | −172 (8,4% số vào tầng) | tạm | Số lần khớp: thấp nhất 3, trung vị 13, cao nhất 469. Xem tay 9 tài liệu, cả 9 đều là spam cờ bạc |

Rủi ro chưa đo của `spam_keywords`:
- Code đếm chuỗi con, không xét ranh giới âm tiết, nên "cá độ" khớp cả "cá độc", và "lô đề" khớp cả "lô đề xuất".
- Cụm "link vào" khá phổ biến trong văn bản thường.

## 6. Tầng 6: Khử trùng lặp

| Mã | Loại khi | Tham số | Nguồn | Baseline | Trạng thái | Ghi chú |
|---|---|---|---|---|---|---|
| `exact_duplicate` | SHA-1 của văn bản (viết thường, gộp khoảng trắng) trùng một tài liệu trước đó; giữ bản đầu | — | phổ biến | −1 | gốc | |
| `near_duplicate` | MinHash-LSH báo trùng với một tài liệu đã giữ | shingle 5 âm tiết; 112 hoán vị = 14 dải × 8 hàng; ngưỡng hiệu dụng ≈ 0,72 | FineWeb (5-gram, 14 × 8) | −23 | tạm | Đơn vị shingle là câu hỏi RQ1 (âm tiết / từ / ký tự). Ít trùng vì 10 file chọn ngẫu nhiên |
| dòng lặp (`empty_after_line_dedup` nếu tài liệu rỗng sau khi xóa dòng) | Dòng ≥ 10 ký tự lặp trong ≥ 3 tài liệu cùng tên miền thì bị xóa | `min_docs_per_domain: 3`, `min_line_chars: 10` | tự đặt | −3.930 dòng, 0 tài liệu | cần xem | Trong mẫu, 89% tên miền chỉ có 1 trang (2.151 tên miền / 2.414 tài liệu), nên luật này gần như không chạm được menu, footer |
| dòng lặp liên website | Dòng ≥ 10 ký tự xuất hiện trên ≥ `min_domains` tên miền khác nhau thì bị xóa (thêm ngày 27/10/2026) | `min_domains: 20` (0 = tắt) | CCNet (Wenzek và cs., 2020): CCNet xóa mọi đoạn trùng trong một phân đoạn dữ liệu; ở đây chỉ xóa dòng lặp trên nhiều website | Chạy thử 50 file: 21 dòng, xóa 2.858 lần trong 1.468 tài liệu | tạm | Cả 25 dòng đạt ngưỡng (đếm trên lần chạy `wet_50_c4`) đều là chuỗi của theme, plugin: "Chưa có sản phẩm trong giỏ hàng." (534 tên miền), "Lưu tên của tôi, email…" (428), "Chưa có đánh giá nào." (232), reCAPTCHA (137). Số tên miền tăng theo lượng dữ liệu, nên cần xem lại danh sách dòng bị xóa (`cross_site_top` trong `funnel.csv`) khi lên 200 file trở lên |

## 7. Tầng 7: Chất lượng (17 luật)

Luật được kiểm theo thứ tự `quality.rule_order`. Ngưỡng nằm trong `configs/vie_thresholds.yaml`. "Âm tiết" là đơn vị đếm hiện tại (`quality.unit: syllable`).

### 7.1. Định nghĩa

| # | Mã | Đo gì | Loại khi | Nguồn | Trạng thái |
|---:|---|---|---|---|---|
| 1 | `c4_lorem_ipsum` | Có chuỗi "lorem ipsum" | có | C4 | gốc |
| 2 | `c4_curly_bracket` | Có ký tự `{` | có | C4 | cần xem |
| 3 | `gopher_word_count` | Số âm tiết | `< 53` hoặc `> 100000` | Gopher (gốc: 50); hiệu chỉnh ngày 28/10/2026, mục 10 | tạm |
| 4 | `gopher_mean_word_length` | Số ký tự trung bình mỗi âm tiết | `< 3` hoặc `> 10` | Gopher | cần xem |
| 5 | `gopher_symbol_ratio` | (số `#` + `...` + `…`) / số âm tiết | `> 0.1` | Gopher | gốc |
| 6 | `gopher_bullet_lines` | Tỉ lệ dòng bắt đầu bằng ký hiệu đầu dòng | `> 0.9` | Gopher | gốc |
| 7 | `gopher_ellipsis_lines` | Tỉ lệ dòng kết thúc bằng `...` hoặc `…` | `> 0.3` | Gopher | gốc |
| 8 | `gopher_alpha_words` | Tỉ lệ từ (tách theo khoảng trắng) có ít nhất một chữ cái | `< 0.8` | Gopher | gốc |
| 9 | `gopher_stopwords` | Số từ dừng khác nhau (danh sách 53 từ trong `stopwords_vi.txt`) | `< 4` | Gopher (gốc: 2, trên 8 từ dừng tiếng Anh); hiệu chỉnh ngày 28/10/2026, mục 10 | tạm |
| 10 | `gopher_dup_lines` | Tỉ lệ dòng trùng trong tài liệu | `> 0.3` | Gopher | cần xem |
| 11 | `gopher_dup_paragraphs` | Tỉ lệ đoạn trùng (đoạn tách bằng dòng trống) | `> 0.3` | Gopher | cần xem |
| 12 | `gopher_top_2gram` | Tỉ lệ ký tự thuộc 2-gram âm tiết xuất hiện nhiều nhất | `> 0.20` | Gopher | gốc |
| 13 | `gopher_top_3gram` | Như trên, 3-gram | `> 0.18` | Gopher | gốc |
| 14 | `gopher_top_4gram` | Như trên, 4-gram | `> 0.16` | Gopher | gốc |
| 15 | `fineweb_line_punct` | Tỉ lệ dòng kết thúc bằng dấu câu | `<= 0.12` | FineWeb | cần xem |
| 16 | `fineweb_dup_line_chars` | Tỉ lệ ký tự nằm trong dòng trùng | tắt (`enabled: false`) | FineWeb (gốc: 0,1); tắt ngày 28/10/2026, mục 7.4 và 10 | tắt |
| 17 | `fineweb_short_lines` | Tỉ lệ dòng ngắn hơn 30 ký tự | `>= 0.67` | FineWeb | cần xem |

### 7.2. Số liệu baseline

Có 1.843 tài liệu vào tầng 7; 1.406 (76,3%) trượt ít nhất một luật.

Ý nghĩa các cột:
- **Trượt:** số tài liệu vi phạm luật này, khi mọi luật đều được kiểm.
- **Bị loại:** số tài liệu có `drop_reason` là luật này, tức luật đầu tiên mà tài liệu vi phạm theo thứ tự. Cột này phụ thuộc thứ tự luật.
- **Chỉ trượt luật này:** số tài liệu sẽ được giữ lại nếu bỏ luật này.

| # | Mã | Trượt | Bị loại | Chỉ trượt luật này | p10 / p50 / p90 | µs/tài liệu |
|---:|---|---:|---:|---:|---|---:|
| 1 | `c4_lorem_ipsum` | 7 (0,4%) | 7 | 0 | 0 / 0 / 0 | 142 |
| 2 | `c4_curly_bracket` | 61 (3,3%) | 61 | 11 | 0 / 0 / 0 | 13 |
| 3 | `gopher_word_count` | 4 (0,2%) | 4 | 0 | 382 / 1.233 / 3.261 | 3 |
| 4 | `gopher_mean_word_length` | 6 (0,3%) | 6 | 1 | 3,35 / 3,55 / 3,92 | 462 |
| 5 | `gopher_symbol_ratio` | 0 | 0 | 0 | 0 / 0,00065 / 0,0057 | 34 |
| 6 | `gopher_bullet_lines` | 0 | 0 | 0 | 0 / 0 / 0,0505 | 111 |
| 7 | `gopher_ellipsis_lines` | 0 | 0 | 0 | 0 / 0 / 0,0268 | 84 |
| 8 | `gopher_alpha_words` | 31 (1,7%) | 29 | 1 | 0,879 / 0,943 / 0,977 | 2.505 |
| 9 | `gopher_stopwords` | 8 (0,4%) | 6 | 0 | 10 / 30 / 48 | 220 |
| 10 | `gopher_dup_lines` | 542 (29,4%) | 516 | 11 | 0,041 / 0,202 / 0,421 | 57 |
| 11 | `gopher_dup_paragraphs` | 0 | 0 | 0 | 0 / 0 / 0 | 31 |
| 12 | `gopher_top_2gram` | 10 (0,5%) | 1 | 0 | 0,019 / 0,040 / 0,090 | 1.510 |
| 13 | `gopher_top_3gram` | 19 (1,0%) | 7 | 0 | 0,014 / 0,031 / 0,073 | 1.549 |
| 14 | `gopher_top_4gram` | 35 (1,9%) | 14 | 2 | 0,012 / 0,029 / 0,074 | 1.579 |
| 15 | `fineweb_line_punct` | 922 (50,0%) | 484 | 58 | 0,028 / 0,120 / 0,323 | 120 |
| 16 | `fineweb_dup_line_chars` | 895 (48,6%) | 145 | 75 | 0,014 / 0,096 / 0,298 | 105 |
| 17 | `fineweb_short_lines` | 1.093 (59,3%) | 126 | 126 | 0,453 / 0,716 / 0,887 | 54 |

### 7.3. Nhận xét

1. **Ba luật FineWeb (15–17) trượt 49–59% tài liệu.**
   - Nguyên nhân chính: văn bản WET còn nguyên menu, sidebar và footer, trong khi FineWeb đặt ngưỡng trên văn bản đã được trafilatura trích từ WARC.
   - 755 tài liệu chỉ trượt ba luật này, không trượt luật nào khác.
   - **Không hiệu chỉnh ba luật này trước khi xử lý boilerplate** (mục 9, dòng đầu).
   - Đã thêm tầng 3b (mục 3b). Ở lần chạy `wet_50_bp`, ba luật này còn trượt lần lượt 10,0% / 8,5% / 11,7%.
2. **Cột *Bị loại* không dùng được để so sánh các luật.**
   - Ví dụ: `gopher_dup_lines` đứng trước ba luật FineWeb nên nhận 516 tài liệu, dù chỉ 11 tài liệu trượt riêng luật này.
   - Khi viết báo cáo, so sánh các luật bằng cột *Trượt* và *Chỉ trượt luật này*.
3. **Bốn luật không loại tài liệu nào:** 5, 6, 7 và 11.
   - Với luật 11: chỉ 0,2% tài liệu WET có dòng trống ngăn đoạn, nên luật này mất tác dụng. Cần đổi định nghĩa "đoạn" hoặc bỏ luật khỏi danh sách.
4. **Luật 9 coi như đang tắt.** p10 là 10 từ dừng khác nhau, trong khi ngưỡng chỉ là 2.
5. **Luật 4:** âm tiết tiếng Việt ngắn hơn từ tiếng Anh (p50 = 3,55 ký tự).
   - Ngưỡng trên 10 không có tác dụng với âm tiết.
   - Ngưỡng dưới 3 thấp hơn p10 (3,35).
   - Đây là luật dùng cho hình hiệu chỉnh (Hình 4).
6. **Luật 2:** 11 tài liệu bị loại chỉ vì có `{`. Cần xem đó là code thật hay CSS/JS lọt vào WET.
7. **Chi phí:** luật 8 (2.505 µs/tài liệu) và ba luật n-gram (khoảng 1.500 µs/tài liệu) đắt nhất. Dùng `python -m vietweb order-filters` để có thứ tự tối ưu (RQ4).

### 7.4. Kết quả hiệu chỉnh ngưỡng (RQ1)

Cách làm:
- Dữ liệu: `wet_200`, sau tầng 3b `c4_lines`.
- Chia theo file: 150 file đầu là tập dev (dùng để chọn ngưỡng), 50 file sau là tập test (dùng để kiểm tra).
- Với mỗi luật, gán nhãn các trang **chỉ bị luật đó loại** và các trang được giữ, đều nằm sát ngưỡng (`scripts/calibration_sample.py`).
- Nhãn: 1 = trang kém, 0 = chấp nhận được. Một người gán nhãn.
- Quy tắc dời ngưỡng: chỉ dời khi tỉ lệ trang kém trong nhóm đổi trạng thái đạt khoảng 0,8.

| Luật | Ngưỡng gốc → cuối | Dev: tỉ lệ kém ở trang bị loại | Test: tỉ lệ kém ở trang bị loại (khoảng tin cậy 95%) | Test: tỉ lệ kém ở trang được giữ sát ngưỡng |
|---|---|---|---|---|
| `gopher_word_count` | `< 50` → `< 53` | 0,79 (39) | 0,87 (13/15; 0,62–0,96) | 0,93 |
| `gopher_stopwords` | `< 2` → `< 4` | 0,89 (38) | 0,93 (14/15; 0,70–0,99) | 0,80 |
| `gopher_top_4gram` | `> 0,16` (giữ) | 0,85 (20) | 0,87 (13/15; 0,62–0,96) | 0,67 |
| `gopher_mean_word_length` | `< 3` (giữ) | 0,75 (20) | 0,73 (11/15; 0,48–0,89) | 0,33 |
| `fineweb_dup_line_chars` | `≥ 0,1` → tắt | 0,56 (50) | 0,33 (5/15; 0,15–0,58) tại ngưỡng thử 0,23 | 0,47 |
| `fineweb_line_punct`, `fineweb_short_lines`, `gopher_ellipsis_lines`, `gopher_dup_paragraphs` | giữ | — | — | — |

Nhận xét:
- Bốn luật FineWeb và Gopher ở dòng cuối gần như không loại trang nào. Tầng 3b `c4_lines` đã làm thay việc của chúng.
- Trang được giữ ngay trên ngưỡng `gopher_word_count` và `gopher_stopwords` vẫn phần lớn là trang kém (0,80–0,93). Các luật này chỉ loại được trang **rất** ngắn hoặc rất ít từ dừng. Trang ngắn nhưng qua ngưỡng vẫn nhiều rác, nên cần một bộ phân loại chất lượng (ví dụ kiểu FineWeb-Edu) mới xử lý được. Nâng ngưỡng sau khi đã xem tập test thì tập test không còn độc lập nữa.
- Giới hạn: mỗi ô chỉ 15–50 trang và chỉ một người gán nhãn, nên chưa có κ. Precision chỉ đo trên dải sát ngưỡng, không phải trên toàn bộ dữ liệu.
- Độ chắc của từng quyết định:
  - Tắt `fineweb_dup_line_chars` phải đổi khoảng 12 nhãn mới lật.
  - Hai thay đổi `gopher_word_count` và `gopher_stopwords` chỉ cần đổi 1 nhãn là lật, nhưng mỗi cái chỉ ảnh hưởng dưới 1% dữ liệu.
  - Với `gopher_mean_word_length`, nếu áp đúng quy tắc 0,8 thì phải nới xuống khoảng 2,95: nhóm 2,956–3,0 có 7/11 trang kém. Ngưỡng vẫn giữ 3, vì thay đổi chỉ khoảng 40 trang và cũng chỉ cần đổi 1 nhãn là lật.

### 7.5. Thứ tự luật theo chi phí (RQ4)

Đo bằng `scripts/time_quality_order.py` trên 28.948 trang vào tầng 7 của `wet_200_final`:
- Chế độ `save_stats: false`; hai thứ tự chạy xen kẽ 5 lần, lấy trung vị; đo trên máy cá nhân ngày 29/10/2026.

| Thứ tự | Trung vị | ms/tài liệu | Chi phí luật dự tính |
|---|---:|---:|---:|
| Hiện tại (`rule_order`) | 42,96 s | 1,484 | 1,075 ms |
| Theo chi phí, xếp theo (1 − p)/c | 44,22 s | 1,528 | 1,014 ms |

- **Không có lợi ích đo được.** Đo được 0,97 lần; dự tính chỉ 1,06 lần. Chênh lệch nằm trong mức dao động giữa các lần chạy: lần chạy đầu của mỗi thứ tự mất 106 và 118 giây. Tập trang được giữ giống hệt nhau.
- **Vì sao lợi ích nhỏ:**
  - Sau tầng 3b và sau khi hiệu chỉnh ngưỡng, luật nào cũng cho qua ít nhất 94% số trang. Gần như mọi trang đều phải qua đủ các luật, nên đổi thứ tự không bớt được bao nhiêu phép tính.
  - Các luật tốn nhất (`gopher_alpha_words` 608 µs, ba luật n-gram mỗi luật khoảng 320 µs) cho qua 98–99% số trang, nên dù sắp kiểu nào chúng cũng đứng cuối.
  - Khoảng 28% thời gian tầng 7 là phần tách âm tiết: 1,48 so với 1,075 ms mỗi tài liệu. Phần này không phụ thuộc thứ tự luật.
- **Cùng phép tính ở `wet_50`** (jusText, ngưỡng gốc, các luật loại nhiều hơn) từng cho dự tính 1,41 lần. Lợi ích biến mất khi tầng 3b đã gánh phần lớn việc lọc.
- **Tầng 7 chỉ chiếm 5% tổng thời gian** (43/835 giây); tầng chuẩn hóa chiếm 76% (636 giây). Muốn nhanh hơn thì phải tăng tốc tầng chuẩn hóa hoặc chạy song song, và làm cho các chỉ số tốn kém rẻ hơn (ví dụ đếm n-gram một lần cho cả ba luật), chứ không phải đổi thứ tự luật.

## 8. Tầng 8: PII

Tầng này che thông tin chứ không loại tài liệu. Các mẫu chạy lần lượt theo thứ tự trong bảng; chuỗi đã bị mẫu trước che thì mẫu sau không còn bắt được.

| Mã | Mẫu | Thay bằng | Baseline | Trạng thái | Ghi chú (xem tay trên văn bản gốc) |
|---|---|---|---:|---|---|
| `email` | `[\w.+-]+@[\w-]+(\.[\w-]+)+` | `<EMAIL>` | 425 | tạm | |
| `ipv4` | 4 số 0–255 nối bằng dấu chấm | `<IP>` | 3 | cần xem | 1/3 là số điện thoại dạng "09.67.68.69"; 2/3 là DNS công cộng 1.1.1.1, không phải dữ liệu cá nhân |
| `phone_vn` | `0`, `84` hoặc `+84`, đầu số 3/5/7/8/9, thêm 8 chữ số; cho phép cách bằng khoảng trắng, chấm, gạch | `<PHONE>` | 1.207 | cần xem | Phần lớn là hotline doanh nghiệp. Trong 8 mẫu có 1 mã số doanh nghiệp 10 chữ số (CNKD) bị bắt nhầm |
| `cccd` | 12 chữ số liền nhau | `<ID>` | 2 | cần xem | Cả 2 không phải CCCD: một số tài khoản ngân hàng, một số giấy phép kinh doanh |

Số lần che không bằng số dữ liệu cá nhân thật. Precision sẽ đo khi gán nhãn ở tuần 11–12.

## 9. Luật đề xuất, chưa viết

| Đề xuất | Tầng | Lý do | Nguồn | Ưu tiên |
|---|---|---|---|---|
| Tầng bỏ boilerplate trên WET: bỏ các khối dòng ngắn, không có dấu câu, ít từ dừng | mới, ngay sau tầng 3 | Mục 7.3 ý 1; mục 4 (68 trang tiếng Việt bị loại vì menu) | jusText | Đã viết (03/10/2026): tầng 3b |
| Luật theo dòng của C4: chỉ giữ dòng kết thúc bằng dấu câu và có ít nhất 5 từ; bỏ dòng chứa "javascript"; loại trang có ít hơn 3 câu | tầng boilerplate | Ứng viên cho tầng ở dòng trên | C4 | Đã viết; đang dùng từ 26/10/2026 (`boilerplate.method: c4_lines`). Phần "ít hơn 3 câu" chưa viết |
| `c4_lines`: bỏ thêm dòng kết thúc bằng "..." hoặc "…" (đoạn trích bị cắt) | tầng 3b | Mục 3b: 24/49 trang trafilatura qua mà `c4_lines` trượt là do `gopher_ellipsis_lines` | — | Đã viết (27/10/2026): `boilerplate.c4_drop_ellipsis` |
| Trích 2–3 file WARC bằng trafilatura làm chuẩn để đo tầng boilerplate | 1–2 | Đo phương án WET so với WARC | FineWeb | Đã viết: `vietweb reference`, `extract-eval`; chưa chạy với dữ liệu thật |
| Tách số bản ghi bị loại bởi CLD2 và bởi `min_chars`; thêm dòng "CLD2: ngôn ngữ chính là vie" vào funnel | 1–2 | Funnel trong báo cáo đang gộp hai việc này | — | Trung bình |
| GlotLID thay cho heuristic | 4 | Mục 4 | FineWeb-2 | Trung bình (tuần 8–10) |
| Danh sách tên miền UT1 | 5 | `blocklist_domains.txt` mới có ví dụ mẫu | UT1 | Trung bình |
| So khớp từ khóa spam theo ranh giới âm tiết | 5 | "cá độ" khớp cả "cá độc" | — | Trung bình |
| Bổ sung các luật Gopher còn thiếu: tỉ lệ ký tự trong đoạn trùng (0,20); tỉ lệ ký tự thuộc n-gram trùng, từ 5-gram (0,15) đến 10-gram (0,10) | 7 | Đủ bộ luật lặp của Gopher | Gopher | Thấp |
| Chuyển đổi TCVN3/VNI (`convert_legacy`), sau đó chọn `flag` hay `drop` | 3 | Mới có 2 tài liệu bị gắn cờ | — | Thấp |
| PII: bỏ qua số đứng sau "MST", "CNKD", "GPKD", "Số tài khoản"; đổi nhãn `cccd` thành "dãy 12 số" | 8 | Mục 8 | — | Thấp (tuần 11–12) |

## 10. Nhật ký thay đổi

Mỗi lần đổi ngưỡng, bật/tắt hoặc thêm luật thì ghi một dòng.

| Ngày | Luật | Cũ → mới | Lý do, bằng chứng | Lần chạy dùng để kiểm |
|---|---|---|---|---|
| 30/09/2026 | tất cả | — | Baseline với ngưỡng gốc | `baseline_wet_10` |
| 03/10/2026 | tầng 3b (mới) | — → jusText theo dòng: `length_low 70`, `length_high 150`, `stopwords_low 0.08`, `stopwords_high 0.12`, `min_chars_after 200` | Ở `wet_50`, ba luật FineWeb trượt 47–59% vì WET còn menu (mục 7.3). `length_high` hạ từ 200 (giá trị của jusText) xuống 150 để giảm số trang tốt bị xóa sạch: từ 198 xuống 133 trên 2.300 trang được giữ ở `wet_50` | `wet_50_bp` |
| 26/10/2026 | tầng 3b | jusText (`length_high 150`, `stopwords_low 0.08`, `stopwords_high 0.12`) → `method: c4_lines` (`c4_min_words 5`, `min_chars_after 200`); tham số jusText giữ nguyên để có thể quay lại | `extract-eval` trên 3 file WARC (mục 3b): F1 0,756 so với 0,728 (+0,028, khoảng tin cậy 95% +0,005 đến +0,051); bỏ sót 42 thay vì 120 trên 562 trang có nội dung. Đánh đổi: mất tiêu đề và mục liệt kê, giữ boilerplate dạng câu, `fineweb_line_punct` và `fineweb_short_lines` gần như không còn tác dụng | `wet_50_c4` |
| 27/10/2026 | tầng 3b, tầng 6 | Thêm `boilerplate.c4_drop_ellipsis: true` và `dedup.line.min_domains: 20` | Chạy thử trên bản sao 50 file, so với `wet_50_c4`. Khi tắt hai luật, kết quả khớp `wet_50_c4` (6.116). Khi bật: giữ 6.501 tài liệu (+385); tầng 7 loại 1.114/7.615 (14,6%, trước là 22,9%); số ký tự giữ lại gần như không đổi (23,8 triệu). Được thêm 505 tài liệu, trong đó 426 trước đây bị `gopher_ellipsis_lines` loại. Mất 120 tài liệu, đọc 8 trang mẫu thì 6 là trang sản phẩm chỉ còn chuỗi giỏ hàng, footer, cờ bạc; 2 là bài viết thật bị luật tầng 7 loại sát ngưỡng (`fineweb_dup_line_chars`, `gopher_top_4gram`) | bản sao 50 file (chưa chạy trên máy) |
| 28/10/2026 | `gopher_word_count`, `gopher_stopwords` | `min 50` → `53`; `min 2` → `4` | Gán nhãn vòng 1, tập dev (150 file đầu của `wet_200`, 200 trang sát ngưỡng): trang có 50–52 âm tiết kém 16/19, trang có 2–3 từ dừng kém 15/18 (khoảng tin cậy 95% khoảng 0,62–0,95). Giữ nguyên `gopher_mean_word_length` và `gopher_top_4gram`: dời ngưỡng không cải thiện rõ. `fineweb_dup_line_chars` chưa đổi: phía bị loại chỉ 12/20 là trang kém, đang gán nhãn vòng 2 trên dải rộng hơn. Ước tính loại thêm 350 trong 24.621 trang được giữ ở `wet_200` (1,4%) | chưa chạy lại; kiểm tra trên tập test |
| 28/10/2026 | `fineweb_dup_line_chars`; `gopher_word_count` (xem lại) | `max 0.1` → `0.23`; `gopher_word_count` giữ `53` | Gán nhãn vòng 2 (60 trang, dải rộng hơn). `fineweb_dup_line_chars`: trang chỉ bị luật này loại, giá trị 0,10–0,23, chỉ 28/50 là trang kém, và tỉ lệ này gần như không đổi (0,50–0,56) ở mọi ngưỡng trong dải. Trang tốt bị loại thường chỉ có 2–3 dòng lặp hai lần (mục liệt kê, tiêu đề bài liên quan, dòng đăng ký nhận tin). Ở mức ≥ 0,23, 814/1.077 trang cũng trượt `gopher_dup_lines`. `gopher_word_count`: trang được giữ có 53–66 âm tiết kém 24/31 (0,77), dưới mức 0,8 dùng để dời ngưỡng, nên giữ 53. Quy tắc dời ngưỡng: chỉ dời khi tỉ lệ trang kém trong nhóm đổi trạng thái đạt khoảng 0,8 | chưa chạy lại; kiểm tra trên tập test |
| 28/10/2026 | `fineweb_dup_line_chars` | `max 0.23` → tắt | Tập test (50 file cuối của `wet_200`): trong 15 trang bị loại sát ngưỡng 0,23, chỉ 5 trang kém (0,33; khoảng tin cậy 95% 0,15–0,58). Ở tập dev, tỉ lệ trang kém cũng không vượt 0,56 ở bất kỳ ngưỡng nào trong dải 0,10–0,23. Trang lặp nhiều vẫn bị `gopher_dup_lines` bắt: ở mức ≥ 0,23, 814/1.077 trang trượt cả luật này. Lưu ý: quyết định tắt luật dùng cả kết quả tập test, nên con số 0,33 không còn là ước lượng độc lập | chưa chạy lại |
| | | | | |

## 11. Lịch sử lần chạy

| Lần chạy | Ngày | Dữ liệu | Khác baseline ở đâu | Vào | Giữ lại | Ghi chú |
|---|---|---|---|---:|---:|---|
| `baseline_wet_10` | 30/09/2026 | CC-MAIN-2026-39, 10 file WET | — | 2.414 | 437 (18,1%) | Tầng 7 loại 76,3% số tài liệu vào tầng |
| `wet_50` | 03/10/2026 | CC-MAIN-2026-39, 50 file WET (gồm 10 file baseline) | Chỉ thêm dữ liệu | 12.304 | 2.300 (18,7%) | Tầng 7 loại 74,9%; tỉ lệ trượt từng luật lệch baseline tối đa 1,8 điểm %. Lọc dòng lặp xóa 122.365 dòng (baseline: 3.930). Near-dup 334, 95% cùng tên miền với bản đại diện |
| `wet_50_bp` | 03/10/2026 | CC-MAIN-2026-39, 50 file WET | Thêm tầng 3b | 12.304 | 5.125 (41,7%) | Tầng 3b loại 4.507 (1.358 trang có ngôn ngữ chính không phải tiếng Việt); tầng 4 chỉ còn loại 7; tầng 7 loại 26,0%. Đã chạy lại trên máy ngày 03/10/2026: số tài liệu khớp từng tầng; tổng thời gian khoảng 12 phút (tầng 3b 313 giây, chuẩn hóa 258 giây) |
| `wet_50_c4` | 27/10/2026 | CC-MAIN-2026-39, 50 file WET | Tầng 3b đổi sang `method: c4_lines` | 12.304 | 6.116 (49,7%) | Tầng 3b loại 2.249 (369 trang có ngôn ngữ chính không phải tiếng Việt), chạy 5,8 giây (jusText ở `wet_50_bp`: 313 giây). Tầng 4 loại 1.230, vì tầng 3b không còn gánh việc lọc trang ngoại ngữ. Spam 597; trùng chính xác 127, gần đúng 151. Tầng 7 loại 1.814/7.930 (22,9%): luật loại nhiều nhất là `gopher_ellipsis_lines` (772), `fineweb_line_punct` không loại trang nào. Tổng khoảng 190 giây |
| `wet_200` | 27/10/2026 | CC-MAIN-2026-39, 200 file WET (gồm 50 file cũ) | `c4_lines` + bỏ dòng "…" + dòng lặp liên website | 48.815 | 24.621 (50,4%) | Tầng 7 loại 14,9%; 73 dòng lặp liên website, tất cả là boilerplate; tổng 717 giây (chuẩn hóa 435 giây) |
| `wet_200_cal` | 28/10/2026 | Như `wet_200` | Ngưỡng: `gopher_word_count` 53, `gopher_stopwords` 4, `fineweb_dup_line_chars` 0,23 | 48.815 | 25.054 (51,3%) | Khớp số dự tính từ `quality_stats.parquet` |
| `wet_200_final` | 29/10/2026 | Như `wet_200` | Tắt `fineweb_dup_line_chars` | 48.815 | 25.255 (51,7%) | Tầng 7 loại 3.693/28.948 (12,8%); tổng 835 giây, chuẩn hóa 636 giây (76%), tầng 7 43 giây |
| `wet_2024_10_50` | 29/10/2026 | CC-MAIN-2024-10, 50 file WET | Như `wet_200_final`; dùng để đối chiếu với FineWeb-2 (mục 12) | 18.576 | 10.050 (54,1%) | Bản crawl này có nhiều bản ghi tiếng Việt hơn trên mỗi file so với CC-MAIN-2026-39 (18.576 so với 12.304 trên 50 file) |
| | | | | | | |

## 12. Đối chiếu với FineWeb-2 (RQ3)

**Dữ liệu và cách đo:**
- Lần chạy `wet_2024_10_50`: CC-MAIN-2024-10, 50 file, 18.575 tài liệu (giữ 10.050).
- Ghép theo URL với FineWeb-2 của cùng bản crawl. FineWeb-2 có 6,35 triệu dòng của bản crawl này: 2,43 triệu ở `vie_Latn`, 3,93 triệu ở `vie_Latn_removed`.
- Lệnh `fw2-urls` đọc 0,52 GB qua mạng, mất khoảng 2,9 giờ.
- Kết quả gốc nằm ở `outputs/eval/fineweb2_CC-MAIN-2024-10.md` và `fineweb2_pii_vie_Latn.md`.

**Độ phủ:**
- **Chỉ 3.096 trong 18.575 URL (16,7%) có trong FineWeb-2.** Trong cùng 50 file WARC, FineWeb-2 chỉ có 3.085 tài liệu tiếng Việt.
- Giả định, chưa kiểm chứng: phần lớn số còn lại bị FineWeb-2 loại khi khử trùng lặp toàn cục trên 96 bản crawl. Một phần có thể do trafilatura trích ra văn bản rỗng (9% ở thí nghiệm WARC, mục 3b) hoặc do GlotLID không nhận là tiếng Việt.
- **Bộ lọc sơ bộ CLD2 hầu như không bỏ sót.** Chỉ 14 trong 3.085 tài liệu tiếng Việt của FineWeb-2 trong cùng các file WARC (0,45%) không được pipeline thu thập.

**Đồng thuận trên 3.096 URL có ở cả hai bên:**
- A = 0,634; κ = 0,31 (mức đồng thuận "khá thấp" theo thang Landis và Koch).

| | FineWeb-2 giữ | FineWeb-2 loại |
|---|---:|---:|
| Pipeline giữ | 1.047 | 978 |
| Pipeline loại | 156 | 915 |

**FineWeb-2 loại nhưng pipeline giữ (978 trang):**
- Lý do của FineWeb-2: `line_punct_ratio` 588 trang (60%), `gopher_below_alpha_threshold` 257 (26%), các luật khác dưới 5% mỗi luật.
- Phần lớn bất đồng đến từ khác biệt trong cách trích văn bản:
  - trafilatura giữ tiêu đề, danh sách, bảng số, nên trang dễ trượt hai luật trên.
  - `c4_lines` chỉ giữ dòng thành câu, nên văn bản của pipeline luôn qua `line_punct`.
- Đọc 15 trang mẫu (đánh giá của người làm, chưa gán nhãn chính thức): khoảng một nửa là nội dung dùng được (bài báo thể thao, thông báo của trường, bài phong thủy, mô tả sản phẩm). Nửa còn lại là boilerplate hoặc rác: form mật khẩu, thống kê xổ số, một trang soi kèo mà luật spam bỏ sót.

**FineWeb-2 giữ nhưng pipeline loại (156 trang):**
- **109 trang (70%) bị luật từ khóa cờ bạc loại.** Cả 6 trang loại này trong mẫu đều là nội dung cờ bạc: bầu cua, lô đề, tài xỉu, soi kèo. Như vậy FineWeb-2 giữ lại nội dung cờ bạc tiếng Việt.
- 15 trang bị loại vì nhận diện ngôn ngữ, 13 trang vì `c4_curly_bracket`. Trong mẫu:
  - Phần lớn là trang mà **văn bản WET chứa JavaScript**. Pipeline loại vì nhận ra mã, trong khi FineWeb-2 trích từ HTML nên lấy được nội dung thật. Đây là điểm yếu của cách làm dựa trên WET.
  - Có 1 trang tiếng Việt thật (trang trợ giúp của Google) bị nhận diện ngôn ngữ bằng heuristic loại nhầm.

**Cả hai cùng loại (915 trang):** cặp lý do thường gặp nhất là `boilerplate_too_short` × `line_punct_ratio` (479 trang). Hai bên loại cùng một kiểu trang (danh mục, menu), chỉ ở hai bước khác nhau.

**Thông tin cá nhân còn lại trong FineWeb-2** (`fw2-pii`, 10.000 tài liệu `vie_Latn`):
- **7,51% tài liệu có chuỗi khớp mẫu số điện thoại Việt Nam** (1.401 lần khớp).
- Đọc 25 lần khớp: 24 là số điện thoại thật, 1 là ngày giờ. Khoảng 8 số có vẻ là của cá nhân (bài đăng diễn đàn, "Mr. Mạnh…"); còn lại là hotline doanh nghiệp.
- Dãy 12 số: 0,02%. Email: 0,05%; thấy cả email thay thế của FineWeb-2 (`firstname.lastname@example.org`).
- Giới hạn: mẫu lấy từ các nhóm dòng đầu file nên chỉ gồm các bản crawl 2013–2014 và 2023-40.

**Giới hạn chung:**
- Chỉ một bản crawl, 50 file.
- Đánh giá trang mẫu là của một người, chưa gán nhãn chính thức.
- Không lấy văn bản FineWeb-2 để so trực tiếp, chỉ so quyết định giữ/loại theo URL.

## 13. Mức trùng lặp (RQ2)

Số liệu của `wet_200_final` (CC-MAIN-2026-39, 200 file), tính bằng `scripts/dedup_stats.py`. Kết quả gốc nằm ở `outputs/eval/dedup_stats_wet_200_final.md`.

| Mức | Tài liệu vào | Bị loại hoặc bị xóa | Tỉ lệ | Cùng một tên miền |
|---|---:|---:|---:|---:|
| Trùng chính xác (SHA-1) | 31.152 | 1.005 bản sao | 3,23% | 89,0% số bản sao |
| Trùng gần đúng (MinHash-LSH, ngưỡng ≈ 0,72) | 30.147 | 1.013 | 3,36% | 75,0% số cặp |
| Dòng lặp ≥ 3 trang cùng tên miền | 29.134 | 36.704 dòng | — | 100% (theo định nghĩa) |
| Dòng lặp ≥ 20 tên miền | 29.134 | 11.394 dòng (73 dòng khác nhau, ở 5.809 tài liệu) | — | 0% (theo định nghĩa) |
| Tài liệu rỗng sau khi xóa dòng | 29.134 | 186 | 0,64% | — |

Ngoài ra, tầng 3b bỏ 65,7% số ký tự: phần lớn là menu, footer, lặp lại trên mọi trang của một website.

**Tỉ lệ trùng tăng theo lượng dữ liệu** (lấy ngẫu nhiên các tập con lồng nhau của 200 file, 5 lần):

| Số file | Tài liệu | Trùng chính xác | Trùng gần đúng (ước lượng thấp hơn thực tế) |
|---:|---:|---:|---:|
| 25 | 3.895 | 0,85% | 0,71% |
| 50 | 7.802 | 1,31% | 1,09% |
| 100 | 15.555 | 2,16% | 1,78% |
| 150 | 23.299 | 2,75% | 2,52% |
| 200 | 31.152 | 3,23% | 3,36% |

Nhận xét:
- **Trùng lặp chủ yếu nằm trong cùng một website.** 89% bản sao chính xác và 75% cặp trùng gần đúng thuộc cùng một tên miền. Đó thường là các trang tag hoặc danh mục chỉ còn đoạn giới thiệu chung sau khi bỏ boilerplate.
- **73,2% trong 19.858 tên miền chỉ có một trang** trong mẫu. Vì vậy luật dòng lặp cùng tên miền chạm được ít trang, còn luật liên website (mục 6) bổ sung cho nó.
- **Tỉ lệ trùng tăng đều khi tăng số file:** mỗi lần gấp đôi dữ liệu, tỉ lệ tăng khoảng 1,5 lần. Suy ra (giả định, chưa đo): trên cả bản crawl 100.000 file, và khi khử trùng lặp trên nhiều bản crawl như FineWeb-2, tỉ lệ sẽ cao hơn nhiều. Điều này khớp với việc 83% URL của pipeline không có trong FineWeb-2 (mục 12).
- Giới hạn: với tập con, trùng gần đúng chỉ được tính khi tài liệu được khớp cũng nằm trong tập con, nên con số thấp hơn thực tế. Ở 200 file con số là chính xác.

**Đơn vị shingle** (`dedup-eval`): 3.000 tài liệu đã làm sạch của `wet_200_final`; nhãn đúng là Jaccard chính xác ≥ 0,75 trên mọi cặp. Kết quả nằm ở `outputs/eval/dedup_units.csv`.

| Đơn vị | Cặp đúng | Cặp LSH | Precision | Recall | F1 | Giây |
|---|---:|---:|---:|---:|---:|---:|
| 5-gram âm tiết (đang dùng) | 43 | 66 | 0,636 | 0,977 | 0,771 | 251 |
| 3-gram âm tiết | 55 | 68 | 0,750 | 0,927 | 0,829 | 225 |
| 15-gram ký tự | 45 | 53 | 0,774 | 0,911 | 0,837 | 1.345 |

- LSH gần như không bỏ sót cặp trùng, nhưng báo cả các cặp có Jaccard dưới 0,75. Lý do: ngưỡng hiệu dụng của cấu hình 14 × 8 (khoảng 0,72) thấp hơn 0,75, và pipeline không kiểm tra lại Jaccard của cặp ứng viên.
- Chênh lệch F1 giữa các đơn vị chưa đủ để đổi đơn vị, vì mỗi đơn vị chỉ có 43–55 cặp. Đơn vị ký tự chậm hơn khoảng 5 lần.
- Lần chạy đầu ngày 29/10/2026 (do người làm chạy trên máy cá nhân) cho kết quả sai: mẫu lẫn khoảng 28 trang rỗng (bị xóa sạch ở bước xóa dòng lặp). Các trang rỗng có cùng chữ ký MinHash nên tạo ra khoảng 380 cặp trùng giả. Đã sửa: bỏ trang rỗng khi lấy mẫu, và bỏ tập shingle rỗng trong `lsh_pairs`. Bảng trên là kết quả chạy lại.

## Nguồn

- Rae et al. (2021). *Scaling Language Models: Methods, Analysis & Insights from Training Gopher.* [arXiv:2112.11446](https://arxiv.org/abs/2112.11446). Phụ lục A mô tả các luật chất lượng và luật lặp.
- Raffel et al. (2020). *Exploring the Limits of Transfer Learning with a Unified Text-to-Text Transformer* (C4). [arXiv:1910.10683](https://arxiv.org/abs/1910.10683), mục 2.2.
- Penedo et al. (2024). *The FineWeb Datasets.* [arXiv:2406.17557](https://arxiv.org/abs/2406.17557); [blog FineWeb](https://huggingface.co/spaces/HuggingFaceFW/blogpost-fineweb-v1).
- [FineWeb-2](https://huggingface.co/datasets/HuggingFaceFW/fineweb-2) (GlotLID, ngưỡng theo từng ngôn ngữ).
- Pomikálek, J. (2011). *Removing Boilerplate and Duplicate Content from Web Corpora* (luận án, Masaryk University); thuật toán được cài đặt trong [jusText](https://github.com/miso-belica/jusText). Tầng 3b dùng lại các bước phân loại của jusText.
- Barbaresi, A. (2021). *Trafilatura: A Web Scraping Library and Command-Line Tool for Text Discovery and Extraction.* ACL 2021 System Demonstrations. Cấu hình FineWeb dùng: [datatrove, extractors/trafilatura.py](https://github.com/huggingface/datatrove/blob/main/src/datatrove/pipeline/extractors/trafilatura.py).
- [Danh sách chặn UT1](https://dsi.ut-capitole.fr/blacklists/) (Université Toulouse Capitole).
