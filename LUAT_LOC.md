# Danh mục luật lọc và kết quả

File này liệt kê mọi luật pipeline dùng để loại, sửa hoặc che văn bản: ngưỡng, nguồn của ngưỡng và số liệu đo được. Các mục 12–14 ghi kết quả của các thí nghiệm. Lệnh tái lập từng kết quả nằm trong [HUONG_DAN_CHAY.md](HUONG_DAN_CHAY.md), mục 5.

Số liệu lấy từ các lần chạy sau (mô tả đầy đủ ở mục 11):
- **`baseline_wet_10`**: CC-MAIN-2026-39, 10 file WET, 2.414 tài liệu; ngưỡng gốc, chưa có tầng 3b. Cột "Ban đầu" trong các bảng là của lần chạy này.
- **`wet_50_bp`**: 50 file, tầng 3b dùng jusText (mục 3b).
- **`wet_200_final`**: 200 file, cấu hình cuối. Cột "`wet_200_final`" trong các bảng là của lần chạy này.
- **`wet_1000`**: 1.000 file, cấu hình cuối (mục 14.6).

Quy ước:
- Mã luật chính là giá trị `drop_reason` trong `data\processed\dropped\`. Xem ví dụ bị loại: `python -m vietweb peek --reason <mã> -n 5`.
- Thống kê từng luật của một lần chạy: `python scripts\rule_stats.py --out outputs\stats\rule_stats.md` (cần `quality.save_stats: true`); bản của từng lần chạy nằm ở `outputs/runs/<lần chạy>/rule_stats.md`.
- Ngưỡng viết trong `code` là giá trị như trong file cấu hình (dấu chấm thập phân). Số liệu đo được viết kiểu Việt Nam (dấu phẩy thập phân).
- Cấu hình nằm trong `configs/pipeline.yaml` trừ khi ghi khác. Code nằm trong `src/vietweb/`.

## 1. Tổng quan

| Tầng | Số luật | Hành động | Ban đầu | `wet_200_final` | Cấu hình | Code |
|---|---:|---|---|---|---|---|
| 1–2. Thu thập | 2 | loại | 211.717 → 2.414 bản ghi | 48.815 bản ghi tiếng Việt | `collect` | `io/commoncrawl.py` |
| 3. Chuẩn hóa | 5 | sửa; chuyển bảng mã cũ | 0 bị loại, 2 gắn cờ mã cũ | 0 bị loại, 48.810 tài liệu bị sửa | `normalize` | `stages/s03_normalize.py`, `text/normalize.py`, `text/legacy.py` |
| 3b. Bỏ boilerplate | 5 | sửa; loại trang còn quá ngắn | chưa có tầng này | −11.359; bỏ 65,7% số ký tự | `boilerplate` | `stages/s03b_boilerplate.py` |
| 4. Nhận diện ngôn ngữ | 1 | loại | −375 | −4.060 | `langid` | `stages/s04_langid.py` |
| 5. Lọc URL, từ khóa | 2 | loại | −172 | −2.244 | `url_filter`, `blocklist_*.txt` | `stages/s05_url_filter.py` |
| 6. Khử trùng lặp | 4 | loại; xóa dòng | −24 tài liệu, −3.930 dòng | −2.204 tài liệu, −48.098 dòng | `dedup` | `stages/s06_dedup.py` |
| 7. Chất lượng | 17 (16 bật) | loại | −1.406 | −3.693 | `quality`, `vie_thresholds.yaml` | `stages/s07_quality.py` |
| 8. PII | 4 | che | 1.637 lần che | 4.289 lần che | `pii` | `stages/s08_pii.py` |
| **Tổng** | **40** | | **2.414 → 437 (18,1%)** | **48.815 → 25.255 (51,7%)** | | |

## 2. Tầng 1–2: Thu thập

Hai luật này chạy lúc đọc file WET, không có `drop_reason`.

| Luật (khóa cấu hình) | Loại khi | Ngưỡng | Nguồn | Ghi chú |
|---|---|---|---|---|
| `collect.language_prefilter` | Trường `WARC-Identified-Content-Language` (CLD2) không chứa mã này | `vie` | Common Crawl | Lấy bản ghi có `vie` ở **bất kỳ vị trí nào**. Ban đầu, 314/2.414 bản ghi có ngôn ngữ chính khác (Anh, Trung...), phần lớn bị tầng 3b hoặc 4 loại sau đó. So với FineWeb-2, bộ lọc này chỉ bỏ sót 14 trong 3.085 tài liệu tiếng Việt (0,45%, mục 12). |
| `collect.min_chars` | Văn bản ngắn hơn ngưỡng (ký tự) | `200` | tự đặt | Manifest không tách số bản ghi bị loại theo từng luật; chỉ có tổng (ban đầu 211.717 → 2.414). |

## 3. Tầng 3: Chuẩn hóa

Các phép sửa áp dụng cho mọi tài liệu. Ban đầu, 2.414/2.414 tài liệu bị thay đổi ít nhất một ký tự; ở `wet_200_final` là 48.810/48.815, phần lớn là khoảng trắng và dạng Unicode. Khi chạy một tiến trình và chạy ftfy trên cả văn bản, tầng này chiếm 76% thời gian của `wet_200_final` (636/835 giây).

| Luật (khóa cấu hình) | Làm gì | Giá trị | Nguồn | Ghi chú |
|---|---|---|---|---|
| `normalize.fix_mojibake` | Sửa lỗi mã hóa bằng ftfy | `true` | ftfy | ftfy chỉ chạy trên những dòng có ký tự nó có thể sửa. Kết quả giống chạy trên cả văn bản ở cả 48.815 tài liệu, nhanh 4,9 lần (mục 14.1) |
| `normalize.unicode_form` | Chuẩn hóa Unicode | `NFC` | Unicode | |
| `normalize.tone_mark_style` | Thống nhất vị trí dấu thanh | `old` (hòa, thủy) | tự đặt | `new` cho hoà, thuỷ; `none` giữ nguyên. Ở mẫu 50 file, 673 trang dùng kiểu đặt dấu mới |
| (luôn bật) | Bỏ ký tự điều khiển và zero-width, gộp khoảng trắng, tối đa một dòng trống liên tiếp | — | | |
| `normalize.legacy_encoding_action` | `convert`: giải mã TCVN3 và VNI, giữ bản giải mã khi ít nhất 2% ký tự không phải khoảng trắng là mã riêng của bảng mã đó, tỉ lệ từ dừng tăng ít nhất 4 điểm %, và ít nhất 30% âm tiết sau giải mã có dấu | `convert` | tự đặt; bảng chuyển đổi lấy từ Unikey | 0/48.815 tài liệu (200 file) và 1/246.833 tài liệu (1.000 file) được chuyển; thử tổng hợp ở mục 14.2. Điểm `legacy_score` (tỉ lệ ký tự đặc trưng của bảng mã cũ) vẫn được lưu: 31 tài liệu ≥ `0.02` ở 200 file; trong mẫu 50 file, cả 8 trang bị gắn cờ đều là tiếng Thổ Nhĩ Kỳ hoặc tiếng Kurd, và không trang nào bị chuyển |

## 3b. Tầng 3b: Bỏ boilerplate

Chạy ngay sau tầng 3. Tầng này bỏ các dòng menu, sidebar, footer và loại trang còn quá ngắn. Tham số nằm ở mục `boilerplate` trong `configs/pipeline.yaml`.
- Phương pháp đang dùng là `method: c4_lines` (luật theo dòng của C4), chọn bằng `extract-eval` (cuối mục này).
- jusText (Pomikálek, 2011), áp dụng cho từng dòng thay vì từng khối HTML, là phương án thay thế (`method: justext`). Hai bảng ngay dưới mô tả jusText, với số liệu của lần chạy `wet_50_bp`.

**jusText, bước 1: phân loại từng dòng, chưa xét ngữ cảnh.** Kiểm tra theo thứ tự trong bảng; dòng khớp điều kiện nào trước thì nhận loại đó.

| Luật (khóa cấu hình) | Dòng bị xếp loại | Tham số | Nguồn |
|---|---|---|---|
| `bad_patterns` | bad nếu chứa ©, "copyright", "bản quyền" hoặc "all rights reserved" | 4 mẫu | jusText (dấu ©) |
| `max_url_ratio` | bad nếu URL chiếm hơn ngưỡng số ký tự của dòng | `0.3` | Thay cho mật độ liên kết của jusText, vì WET không còn thẻ `<a>` |
| `length_low` | short nếu ngắn hơn ngưỡng | `70` ký tự | jusText |
| mật độ từ dừng (`stopwords_low`, `stopwords_high`, `length_high`) | Mật độ ≥ `stopwords_high`: good nếu dòng dài ≥ `length_high`, ngược lại neargood. Mật độ ≥ `stopwords_low`: neargood. Còn lại: bad | `0.08`, `0.12`, `150` | jusText (tiếng Anh: 0,30 / 0,32 / 200) |

**jusText, bước 2–3: xét ngữ cảnh, giữ nguyên quy tắc của jusText.**
- Dòng short lấy loại của dòng good/bad gần nhất ở hai phía. Đầu và cuối trang được tính là bad.
- Dòng neargood thành good, trừ khi cả hai phía đều là bad.
- Cuối cùng chỉ giữ các dòng good.

| Mã | Loại khi | Ngưỡng | `wet_50_bp` (jusText) | `wet_200_final` (`c4_lines`) |
|---|---|---|---|---|
| `boilerplate_too_short` | Văn bản còn lại ngắn hơn ngưỡng | `min_chars_after: 200` | −4.507 (36,6%), trong đó 1.358 trang có ngôn ngữ chính theo CLD2 không phải tiếng Việt | −11.359 (23,3%), trong đó 2.672 trang có ngôn ngữ chính không phải tiếng Việt |

**Phương án đang dùng `method: c4_lines`** (luật theo dòng của C4):
- Chỉ giữ dòng kết thúc bằng dấu câu (`.` `!` `?` `"` `”` `…`) và có ít nhất `c4_min_words: 5` âm tiết.
- Bỏ dòng chứa "javascript".
- `c4_drop_ellipsis: true`: bỏ cả dòng kết thúc bằng "..." hoặc "…". Trên trang WET, đây phần lớn là đoạn trích bị cắt của bài khác ("Xem thêm…"). Khi chưa có luật này, `gopher_ellipsis_lines` loại cả trang chỉ vì vài dòng như vậy (772 trang ở `wet_50_c4`).
- Loại trang còn ít hơn `min_chars_after: 200` ký tự (mã `boilerplate_too_short`). Luật "ít hơn 3 câu" của C4 không được cài đặt.

Kết quả `extract-eval` (3 file WARC, 737 trang; văn bản trafilatura làm tham chiếu; F1 tính theo số ký tự của dòng):

| Phương pháp | Precision | Recall | F1 | Trang có nội dung bị bỏ (/562) | Trang qua tầng 7 | Đồng thuận tập trang qua tầng 7 với trafilatura (Jaccard) |
|---|---|---|---|---|---|---|
| `c4_lines` | 0,752 | 0,760 | 0,756 | 42 | 432 | 0,647 |
| `c4_lines` + bỏ dòng "…" (đang dùng) | 0,774 | 0,727 | 0,750 | — | — | 0,666 |
| jusText tốt nhất (`stopwords_low 0.06`) | 0,692 | 0,773 | 0,730 | 117 | 321 | 0,625 |
| jusText ban đầu (150 / 0,12 / 0,08) | 0,710 | 0,748 | 0,728 | 120 | 329 | 0,644 |
| Giữ hết (`none`) | 0,343 | 1,000 | 0,511 | 0 | 167 | — |
| Văn bản trafilatura | | | | | 360 | 1 |

Nhận xét:
- Chênh lệch F1 giữa `c4_lines` và jusText ban đầu là +0,028 (khoảng tin cậy 95% bootstrap theo trang: +0,005 đến +0,051). Chênh lệch giữa jusText tốt nhất và jusText ban đầu (+0,002) nằm trong nhiễu.
- Ở cấp tài liệu, hai phương pháp đồng thuận với trafilatura gần như ngang nhau (Jaccard 0,647 và 0,644). `c4_lines` giữ được nhiều trang hơn nhưng cũng cho qua nhiều trang kém hơn.
- 98% số ký tự nội dung mà `c4_lines` bỏ sót nằm ở dòng không kết thúc bằng dấu câu: tiêu đề, mục liệt kê, ô bảng. Với jusText tỉ lệ này là 48%.
- `c4_lines` cho qua tầng 7 thêm 121 trang mà bản trafilatura không qua. Trong 8 trang mẫu, phần lớn là boilerplate dạng câu ("Chưa có sản phẩm trong giỏ hàng.", "This entry was posted in…"), trang xổ số, cờ bạc. Bài đánh giá chỉ chạy tầng 7, chưa qua tầng 5 và 6, nên một phần các trang này bị loại ở pipeline đầy đủ.
- Vì mọi dòng còn lại đều kết thúc bằng dấu câu và đủ 5 âm tiết, luật `fineweb_line_punct` và `fineweb_short_lines` gần như không còn loại trang nào (mục 7.4).
- 24 trong 49 trang mà bản trafilatura qua tầng 7 còn `c4_lines` trượt là do `gopher_ellipsis_lines`, vì `c4_lines` giữ các dòng trích dẫn bị cắt. Đây là lý do thêm `c4_drop_ellipsis`.

Số liệu jusText ở `wet_50_bp`:
- **Lượng bị bỏ:** tầng 3b bỏ 2.128.594 dòng, tức 63,8% số ký tự.
- **Ngưỡng từ dừng** chọn theo phân phối của 50 file: với các dòng từ 200 ký tự trở lên và kết thúc bằng dấu câu, p10 là 0,11, trung vị là 0,21.
- **`length_high` đặt 150 thay vì 200.** Với 200, trang có mọi đoạn dài 150–199 ký tự không có dòng good nào làm "neo", nên bị xóa sạch: 198/2.300 trang được giữ ở `wet_50` rơi vào trường hợp này. Với 150, con số còn 133.
- **Tầng 3b làm luôn việc lọc ngôn ngữ.** Trang không phải tiếng Việt mất gần hết các dòng ở đây vì cách phân loại dựa trên từ dừng tiếng Việt. Sau tầng 3b, tầng 4 chỉ còn loại 7 tài liệu (khi chưa có tầng 3b là 1.883). Số `too_short_cld2_not_vie` trong `funnel.csv` tách riêng nhóm trang này.
- **Trùng lặp thay đổi:** trùng chính xác tăng từ 30 lên 113, vì các trang cùng nội dung nhưng khác menu trở thành giống hệt nhau; trùng gần đúng giảm từ 334 xuống 94.
- **Có tài liệu tốt bị mất:** 245 tài liệu được giữ ở `wet_50` bị loại ở `wet_50_bp`, trong đó 127 tài liệu do tầng 3b.

## 4. Tầng 4: Nhận diện ngôn ngữ

| Mã | Loại khi | Ngưỡng | Nguồn | Ban đầu | `wet_200_final` |
|---|---|---|---|---|---|
| `langid_low_score` | Điểm heuristic < ngưỡng. Điểm = 0,6 × min(1, tỉ lệ âm tiết có dấu / 0,5) + 0,4 × min(1, tỉ lệ từ dừng / 0,12) | `0.6` | tự đặt | −375 (15,5%); điểm trung bình 0,78 | −4.060 (10,8% số vào tầng); điểm trung bình 0,889 |

Ghi chú:
- **Ban đầu, phần lớn bị loại đúng:** ngôn ngữ chính theo CLD2 của 375 tài liệu bị loại là Anh 220, Việt 68, Đức 12, Trung 11, Nhật 10, còn lại là ngôn ngữ khác. 68 trang tiếng Việt bị loại chủ yếu là trang sản phẩm toàn menu, tức vấn đề boilerplate (mục 7.3).
- **Giới hạn:** văn bản tiếng Việt không dấu bị chấm điểm thấp. Ở FineWeb-2, một trang tiếng Việt thật bị luật này loại nhầm (mục 12).
- Các backend `fasttext` (lid.176) và `glotlid` có trong code. So sánh với GlotLID: mục 14.3.

## 5. Tầng 5: Lọc URL và từ khóa

| Mã | Loại khi | Ngưỡng | Nguồn | Ban đầu | `wet_200_final` | Ghi chú |
|---|---|---|---|---|---|---|
| `url_blocklist` | Tên miền (kể cả tên miền con) có trong `blocklist_domains.txt` | 1 mục mẫu | tự đặt | 0 | 0 | Danh sách chỉ có một mục mẫu; chưa dùng danh sách UT1 |
| `spam_keywords` | Tổng số lần xuất hiện của 12 từ khóa trong `blocklist_keywords.txt` ≥ ngưỡng | `keyword_min_hits: 3` | tự đặt | −172 (8,4% số vào tầng) | −2.244 (6,7%) | Ban đầu: số lần khớp thấp nhất 3, trung vị 13, cao nhất 469; xem tay 9 tài liệu, cả 9 đều là spam cờ bạc. FineWeb-2 giữ 109 trang mà luật này loại; cả 6 trang mẫu là cờ bạc (mục 12) |

Giới hạn của `spam_keywords`:
- Code đếm chuỗi con, không xét ranh giới âm tiết, nên "cá độ" khớp cả "cá độc", và "lô đề" khớp cả "lô đề xuất".
- Cụm "link vào" khá phổ biến trong văn bản thường.
- Danh sách chỉ có từ có dấu; spam viết không dấu đang bị tầng 4 chặn thay (mục 14.3).

## 6. Tầng 6: Khử trùng lặp

| Mã | Loại khi | Tham số | Nguồn | Ban đầu | `wet_200_final` | Ghi chú |
|---|---|---|---|---|---|---|
| `exact_duplicate` | SHA-1 của văn bản (viết thường, gộp khoảng trắng) trùng một tài liệu trước đó; giữ bản đầu | — | phổ biến | −1 | −1.005 (3,23%) | |
| `near_duplicate` | MinHash-LSH báo trùng với một tài liệu đã giữ | shingle 5 âm tiết; 112 hoán vị = 14 dải × 8 hàng; ngưỡng hiệu dụng ≈ 0,72 | FineWeb (5-gram, 14 × 8) | −23 | −1.013 (3,36%) | So sánh đơn vị shingle: mục 13 |
| dòng lặp cùng tên miền (`empty_after_line_dedup` nếu tài liệu rỗng sau khi xóa dòng) | Dòng ≥ 10 ký tự lặp trong ≥ 3 tài liệu cùng tên miền thì bị xóa | `min_docs_per_domain: 3`, `min_line_chars: 10` | tự đặt | −3.930 dòng, 0 tài liệu | −36.704 dòng; 186 tài liệu rỗng | Ban đầu, 89% tên miền chỉ có 1 trang (2.151 tên miền / 2.414 tài liệu); ở 200 file là 73,2%. Vì vậy luật này chạm được ít trang |
| dòng lặp liên website | Dòng ≥ 10 ký tự xuất hiện trên ≥ `min_domains` tên miền khác nhau thì bị xóa | `min_domains: 20` (0 = tắt) | CCNet (Wenzek và cs., 2020) xóa mọi đoạn trùng trong một phân đoạn dữ liệu; ở đây chỉ xóa dòng lặp trên nhiều website | chưa có luật này | −11.394 dòng (73 dòng khác nhau, ở 5.809 tài liệu) | Ở 200 file, cả 73 dòng đều là chuỗi của theme, plugin: "Chưa có sản phẩm trong giỏ hàng." (1.704 tên miền), "Lưu tên của tôi, email…" (1.516), "Chưa có đánh giá nào." (805), reCAPTCHA (401). Ở 1.000 file, số dòng khác nhau tăng lên 279 vì ngưỡng 20 tên miền cố định; 5 dòng phổ biến nhất vẫn là chuỗi giao diện, các dòng còn lại chưa được kiểm hết |

## 7. Tầng 7: Chất lượng (17 luật)

Luật được kiểm theo thứ tự `quality.rule_order`. Ngưỡng nằm trong `configs/vie_thresholds.yaml`. "Âm tiết" là đơn vị đếm đang dùng (`quality.unit: syllable`).

### 7.1. Định nghĩa

| # | Mã | Đo gì | Loại khi | Nguồn |
|---:|---|---|---|---|
| 1 | `c4_lorem_ipsum` | Có chuỗi "lorem ipsum" | có | C4 |
| 2 | `c4_curly_bracket` | Có ký tự `{` | có | C4 |
| 3 | `gopher_word_count` | Số âm tiết | `< 53` hoặc `> 100000` | Gopher (gốc: 50); hiệu chỉnh, mục 7.4 |
| 4 | `gopher_mean_word_length` | Số ký tự trung bình mỗi âm tiết | `< 3` hoặc `> 10` | Gopher |
| 5 | `gopher_symbol_ratio` | (số `#` + `...` + `…`) / số âm tiết | `> 0.1` | Gopher |
| 6 | `gopher_bullet_lines` | Tỉ lệ dòng bắt đầu bằng ký hiệu đầu dòng | `> 0.9` | Gopher |
| 7 | `gopher_ellipsis_lines` | Tỉ lệ dòng kết thúc bằng `...` hoặc `…` | `> 0.3` | Gopher |
| 8 | `gopher_alpha_words` | Tỉ lệ từ (tách theo khoảng trắng) có ít nhất một chữ cái | `< 0.8` | Gopher |
| 9 | `gopher_stopwords` | Số từ dừng khác nhau (danh sách 53 từ trong `stopwords_vi.txt`) | `< 4` | Gopher (gốc: 2, trên 8 từ dừng tiếng Anh); hiệu chỉnh, mục 7.4 |
| 10 | `gopher_dup_lines` | Tỉ lệ dòng trùng trong tài liệu | `> 0.3` | Gopher |
| 11 | `gopher_dup_paragraphs` | Tỉ lệ đoạn trùng (đoạn tách bằng dòng trống) | `> 0.3` | Gopher |
| 12 | `gopher_top_2gram` | Tỉ lệ ký tự thuộc 2-gram âm tiết xuất hiện nhiều nhất | `> 0.20` | Gopher |
| 13 | `gopher_top_3gram` | Như trên, 3-gram | `> 0.18` | Gopher |
| 14 | `gopher_top_4gram` | Như trên, 4-gram | `> 0.16` | Gopher |
| 15 | `fineweb_line_punct` | Tỉ lệ dòng kết thúc bằng dấu câu | `<= 0.12` | FineWeb |
| 16 | `fineweb_dup_line_chars` | Tỉ lệ ký tự nằm trong dòng trùng | tắt (`enabled: false`) | FineWeb (gốc: 0,1); tắt, mục 7.4 |
| 17 | `fineweb_short_lines` | Tỉ lệ dòng ngắn hơn 30 ký tự | `>= 0.67` | FineWeb |

### 7.2. Số liệu ban đầu (`baseline_wet_10`, ngưỡng gốc, chưa có tầng 3b)

Có 1.843 tài liệu vào tầng 7; 1.406 (76,3%) trượt ít nhất một luật.

Ý nghĩa các cột (dùng cho cả mục 7.6):
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

### 7.3. Nhận xét về số liệu ban đầu

1. **Ba luật FineWeb (15–17) trượt 49–59% tài liệu.**
   - Nguyên nhân chính: văn bản WET còn nguyên menu, sidebar và footer, trong khi FineWeb đặt ngưỡng trên văn bản đã được trafilatura trích từ WARC.
   - 755 tài liệu chỉ trượt ba luật này, không trượt luật nào khác.
   - Vì vậy tầng 3b được thêm trước khi hiệu chỉnh ngưỡng (mục 3b). Ở `wet_50_bp`, ba luật này còn trượt lần lượt 10,0% / 8,5% / 11,7%.
2. **Cột *Bị loại* không dùng được để so sánh các luật.** Ví dụ: `gopher_dup_lines` đứng trước ba luật FineWeb nên nhận 516 tài liệu, dù chỉ 11 tài liệu trượt riêng luật này. So sánh các luật bằng cột *Trượt* và *Chỉ trượt luật này*.
3. **Bốn luật không loại tài liệu nào:** 5, 6, 7 và 11. Với luật 11: chỉ 0,2% tài liệu WET có dòng trống ngăn đoạn, nên luật này gần như không có tác dụng trên WET.
4. **Luật 9 với ngưỡng gốc coi như tắt.** p10 là 10 từ dừng khác nhau, trong khi ngưỡng chỉ là 2.
5. **Luật 4:** âm tiết tiếng Việt ngắn hơn từ tiếng Anh (p50 = 3,55 ký tự). Ngưỡng trên 10 không có tác dụng với âm tiết; ngưỡng dưới 3 thấp hơn p10 (3,35).
6. **Luật 2:** 11 tài liệu bị loại chỉ vì có `{`. Ở FineWeb-2, phần lớn trang bị luật này loại có JavaScript trong văn bản WET (mục 12).
7. **Chi phí:** luật 8 (2.505 µs/tài liệu) và ba luật n-gram (khoảng 1.500 µs/tài liệu) đắt nhất. `python -m vietweb order-filters` cho thứ tự theo chi phí (mục 7.5).

### 7.4. Kết quả hiệu chỉnh ngưỡng (RQ1)

Cách làm:
- Dữ liệu: `wet_200`, sau tầng 3b `c4_lines`.
- Chia theo file: 150 file đầu là tập dev (dùng để chọn ngưỡng), 50 file sau là tập test (dùng để kiểm tra).
- Với mỗi luật, gán nhãn mù các trang **chỉ bị luật đó loại** và các trang được giữ, đều nằm sát ngưỡng (`scripts/calibration_sample.py`). Nhãn: 1 = trang kém, 0 = chấp nhận được. Tổng cộng 409 trang: 260 trang dev (hai vòng), 149 trang test.
- Quy tắc dời ngưỡng: chỉ dời khi tỉ lệ trang kém trong nhóm đổi trạng thái đạt khoảng 0,8.

| Luật | Ngưỡng gốc → cuối | Dev: tỉ lệ kém ở trang bị loại | Test: tỉ lệ kém ở trang bị loại (khoảng tin cậy Wilson 95%) | Test: tỉ lệ kém ở trang được giữ sát ngưỡng |
|---|---|---|---|---|
| `gopher_word_count` | `< 50` → `< 53` | 0,79 (39) | 0,87 (13/15; 0,62–0,96) | 0,93 |
| `gopher_stopwords` | `< 2` → `< 4` | 0,89 (38) | 0,93 (14/15; 0,70–0,99) | 0,80 |
| `gopher_top_4gram` | `> 0,16` (giữ) | 0,85 (20) | 0,87 (13/15; 0,62–0,96) | 0,67 |
| `gopher_mean_word_length` | `< 3` (giữ) | 0,75 (20) | 0,73 (11/15; 0,48–0,89) | 0,33 |
| `fineweb_dup_line_chars` | `≥ 0,1` → tắt | 0,56 (50) | 0,33 (5/15; 0,15–0,58) tại ngưỡng thử 0,23 | 0,47 |
| `fineweb_line_punct`, `fineweb_short_lines`, `gopher_ellipsis_lines`, `gopher_dup_paragraphs` | giữ | — | — | — |

Nhận xét:
- Bốn luật FineWeb và Gopher ở dòng cuối gần như không loại trang nào. Tầng 3b `c4_lines` đã làm thay việc của chúng.
- Trang được giữ ngay trên ngưỡng `gopher_word_count` và `gopher_stopwords` vẫn phần lớn là trang kém (0,80–0,93). Các luật này chỉ loại được trang **rất** ngắn hoặc rất ít từ dừng; phần còn lại cần một bộ phân loại chất lượng (mục 14.5).
- Precision chỉ đo trên dải sát ngưỡng, không phải trên toàn bộ dữ liệu.
- Với `gopher_mean_word_length`, nếu áp đúng quy tắc 0,8 thì phải nới xuống khoảng 2,95 (nhóm 2,956–3,0 có 7/11 trang kém). Ngưỡng vẫn giữ 3 vì thay đổi chỉ ảnh hưởng khoảng 40 trang.

### 7.5. Thứ tự luật theo chi phí (RQ4)

Đo bằng `scripts/time_quality_order.py` trên 28.948 trang vào tầng 7 của `wet_200_final`: chế độ `save_stats: false`; hai thứ tự chạy xen kẽ 5 lần, lấy trung vị; CPU Intel Core i5-12450H.

| Thứ tự | Trung vị | ms/tài liệu | Chi phí luật dự tính |
|---|---:|---:|---:|
| Hiện tại (`rule_order`) | 42,96 s | 1,484 | 1,075 ms |
| Theo chi phí, xếp theo (1 − p)/c | 44,22 s | 1,528 | 1,014 ms |

- **Không có lợi ích đo được.** Đo được 0,97 lần; dự tính chỉ 1,06 lần. Chênh lệch nằm trong mức dao động giữa các lần chạy: lần chạy đầu của mỗi thứ tự mất 106 và 118 giây. Tập trang được giữ giống hệt nhau.
- **Vì sao lợi ích nhỏ:**
  - Sau tầng 3b và sau khi hiệu chỉnh ngưỡng, luật nào cũng cho qua ít nhất 94% số trang. Gần như mọi trang đều phải qua đủ các luật, nên đổi thứ tự không bớt được bao nhiêu phép tính.
  - Các luật tốn nhất (`gopher_alpha_words` 608 µs, ba luật n-gram mỗi luật khoảng 320 µs) cho qua 98–99% số trang, nên dù sắp kiểu nào chúng cũng đứng cuối.
  - Khoảng 28% thời gian tầng 7 là phần tách âm tiết: 1,48 so với 1,075 ms mỗi tài liệu. Phần này không phụ thuộc thứ tự luật.
- **Cùng phép tính ở `wet_50`** (jusText, ngưỡng gốc, các luật loại nhiều hơn) cho dự tính 1,41 lần. Lợi ích biến mất khi tầng 3b đã gánh phần lớn việc lọc.
- **Tầng 7 chỉ chiếm 5% tổng thời gian** (43/835 giây); tầng chuẩn hóa chiếm 76% (636 giây). Muốn nhanh hơn phải tăng tốc tầng chuẩn hóa hoặc chạy song song (mục 14.1), chứ không phải đổi thứ tự luật.

### 7.6. Số liệu từng luật ở `wet_200_final`

28.948 tài liệu vào tầng 7; 3.693 (12,8%) trượt ít nhất một luật. Cột như mục 7.2. Luật `fineweb_dup_line_chars` đã tắt nên không có trong bảng.

| # | Mã | Trượt | Bị loại | Chỉ trượt luật này | p10 / p50 / p90 | µs/tài liệu |
|---:|---|---:|---:|---:|---|---:|
| 1 | `c4_lorem_ipsum` | 63 (0,2%) | 63 | 49 | 0 / 0 / 0 | 21 |
| 2 | `c4_curly_bracket` | 90 (0,3%) | 89 | 80 | 0 / 0 / 0 | 2 |
| 3 | `gopher_word_count` | 1.614 (5,6%) | 1.609 | 762 | 69 / 464 / 1.596 | 1 |
| 4 | `gopher_mean_word_length` | 344 (1,2%) | 296 | 101 | 3,28 / 3,45 / 3,68 | 66 |
| 5 | `gopher_symbol_ratio` | 14 (0,0%) | 11 | 11 | 0 / 0 / 0,00242 | 6 |
| 6 | `gopher_bullet_lines` | 161 (0,6%) | 135 | 115 | 0 / 0 / 0,143 | 5 |
| 7 | `gopher_ellipsis_lines` | 0 | 0 | 0 | 0 / 0 / 0 | 3 |
| 8 | `gopher_alpha_words` | 326 (1,1%) | 115 | 59 | 0,928 / 0,979 / 0,998 | 415 |
| 9 | `gopher_stopwords` | 1.131 (3,9%) | 365 | 242 | 7 / 30 / 47 | 37 |
| 10 | `gopher_dup_lines` | 985 (3,4%) | 763 | 674 | 0 / 0 / 0,115 | 5 |
| 11 | `gopher_dup_paragraphs` | 0 | 0 | 0 | 0 / 0 / 0 | 5 |
| 12 | `gopher_top_2gram` | 256 (0,9%) | 23 | 16 | 0,0193 / 0,04 / 0,087 | 218 |
| 13 | `gopher_top_3gram` | 428 (1,5%) | 68 | 38 | 0,0139 / 0,0338 / 0,0864 | 215 |
| 14 | `gopher_top_4gram` | 983 (3,4%) | 142 | 142 | 0,0125 / 0,0336 / 0,0966 | 217 |
| 15 | `fineweb_line_punct` | 0 | 0 | 0 | 1 / 1 / 1 | 4 |
| 17 | `fineweb_short_lines` | 44 (0,2%) | 14 | 14 | 0 / 0 / 0,111 | 3 |

## 8. Tầng 8: PII

Tầng này che thông tin chứ không loại tài liệu. Các mẫu chạy lần lượt theo thứ tự trong bảng; chuỗi đã bị mẫu trước che thì mẫu sau không còn bắt được.

| Mã | Mẫu | Thay bằng | Ban đầu | `wet_200_final` | `wet_1000` | Ghi chú (xem tay trên văn bản gốc, lần chạy ban đầu) |
|---|---|---|---:|---:|---:|---|
| `email` | `[\w.+-]+@[\w-]+(\.[\w-]+)+` | `<EMAIL>` | 425 | 442 | 1.547 | |
| `ipv4` | 4 số 0–255 nối bằng dấu chấm | `<IP>` | 3 | 173 | 1.029 | 1/3 là số điện thoại dạng "09.67.68.69"; 2/3 là DNS công cộng 1.1.1.1, không phải dữ liệu cá nhân |
| `phone_vn` | `0`, `84` hoặc `+84`, đầu số 3/5/7/8/9, thêm 8 chữ số; cho phép cách bằng khoảng trắng, chấm, gạch | `<PHONE>` | 1.207 | 3.651 | 14.197 | Phần lớn là hotline doanh nghiệp. Trong 8 mẫu có 1 mã số doanh nghiệp 10 chữ số (CNKD) bị bắt nhầm |
| `cccd` | 12 chữ số liền nhau | `<ID>` | 2 | 23 | 100 | Cả 2 không phải CCCD: một số tài khoản ngân hàng, một số giấy phép kinh doanh |

Số lần che là cận trên của số dữ liệu cá nhân thật.

## 9. Đề xuất chưa áp dụng

Các đề xuất rút ra từ kết quả, chưa đưa vào pipeline:

| Đề xuất | Tầng | Căn cứ |
|---|---|---|
| Thêm từ khóa cờ bạc không dấu, rồi mới đổi nhận diện ngôn ngữ sang GlotLID | 4, 5 | Mục 14.3 |
| Chuyển TCVN3/VNI theo từng đoạn hoặc từng dòng thay vì cả trang | 3 | Mục 14.2: trang trộn Unicode và TCVN3 bị hỏng phần Unicode |
| Nâng `gopher_word_count` lên khoảng 73 âm tiết, sau khi có nhãn ở dải 53–72 | 7 | Mục 14.4 |
| Bộ lọc chất lượng thứ hai, học từ nhãn tốt/kém thay vì Wikipedia/web | 7 | Mục 7.4, 14.5 |
| Loại tài liệu chứa ≥ 50% câu hỏi của một câu benchmark trước khi đánh giá trên VMLU | sau tầng 9 | Mục 14.7 |
| Kiểm tra lại Jaccard của cặp ứng viên MinHash-LSH | 6 | Mục 13: precision 0,64–0,77 |
| So khớp từ khóa spam theo ranh giới âm tiết | 5 | Mục 5: "cá độ" khớp cả "cá độc" |
| Dùng danh sách tên miền UT1 | 5 | `blocklist_domains.txt` chỉ có một mục mẫu |
| PII: bỏ qua số đứng sau "MST", "CNKD", "GPKD", "Số tài khoản"; đổi tên nhãn `cccd` thành "dãy 12 số" | 8 | Mục 8 |
| Tách số bản ghi bị loại bởi CLD2 và bởi `min_chars` trong funnel | 1–2 | Mục 2 |
| Luật "ít hơn 3 câu" của C4; các luật lặp còn thiếu của Gopher (tỉ lệ ký tự trong đoạn trùng 0,20; tỉ lệ ký tự thuộc n-gram trùng, từ 5-gram 0,15 đến 10-gram 0,10) | 3b, 7 | C4, Gopher |

## 10. Thay đổi so với cấu hình ban đầu

Các dòng xếp theo thứ tự thay đổi.

| Luật | Cũ → mới | Lý do, bằng chứng | Lần chạy kiểm |
|---|---|---|---|
| tất cả | — | Cấu hình ban đầu với ngưỡng gốc | `baseline_wet_10` |
| tầng 3b (mới) | — → jusText theo dòng: `length_low 70`, `length_high 150`, `stopwords_low 0.08`, `stopwords_high 0.12`, `min_chars_after 200` | Ở `wet_50`, ba luật FineWeb trượt 47–59% vì WET còn menu (mục 7.3). `length_high` hạ từ 200 (giá trị của jusText) xuống 150 để giảm số trang tốt bị xóa sạch: từ 198 xuống 133 trên 2.300 trang được giữ ở `wet_50` | `wet_50_bp` |
| tầng 3b | jusText → `method: c4_lines` (`c4_min_words 5`, `min_chars_after 200`); tham số jusText giữ nguyên để có thể quay lại | `extract-eval` trên 3 file WARC (mục 3b): F1 0,756 so với 0,728 (+0,028, khoảng tin cậy 95% +0,005 đến +0,051); bỏ sót 42 thay vì 120 trên 562 trang có nội dung. Đánh đổi: mất tiêu đề và mục liệt kê, giữ boilerplate dạng câu, `fineweb_line_punct` và `fineweb_short_lines` gần như không còn tác dụng | `wet_50_c4` |
| tầng 3b, tầng 6 | Thêm `boilerplate.c4_drop_ellipsis: true` và `dedup.line.min_domains: 20` | Chạy trên 50 file, so với `wet_50_c4`. Khi tắt hai luật, kết quả khớp `wet_50_c4` (6.116). Khi bật: giữ 6.501 tài liệu (+385); tầng 7 loại 1.114/7.615 (14,6%, trước là 22,9%); số ký tự giữ lại gần như không đổi (23,8 triệu). Được thêm 505 tài liệu, trong đó 426 trước đây bị `gopher_ellipsis_lines` loại. Mất 120 tài liệu; trong 8 trang mẫu, 6 là trang sản phẩm chỉ còn chuỗi giỏ hàng, footer, cờ bạc, 2 là bài viết thật bị luật tầng 7 loại sát ngưỡng (`fineweb_dup_line_chars`, `gopher_top_4gram`) | 50 file; `wet_200` |
| `gopher_word_count`, `gopher_stopwords` | `min 50` → `53`; `min 2` → `4` | Gán nhãn vòng 1, tập dev (150 file đầu của `wet_200`, 200 trang sát ngưỡng): trang có 50–52 âm tiết kém 16/19, trang có 2–3 từ dừng kém 15/18 (khoảng tin cậy 95% khoảng 0,62–0,95). Giữ nguyên `gopher_mean_word_length` và `gopher_top_4gram`: dời ngưỡng không cải thiện rõ. Ước tính loại thêm 350 trong 24.621 trang được giữ ở `wet_200` (1,4%) | `wet_200_cal` |
| `fineweb_dup_line_chars`; `gopher_word_count` (xem lại) | `max 0.1` → `0.23`; `gopher_word_count` giữ `53` | Gán nhãn vòng 2 (60 trang, dải rộng hơn). `fineweb_dup_line_chars`: trang chỉ bị luật này loại, giá trị 0,10–0,23, chỉ 28/50 là trang kém, và tỉ lệ này gần như không đổi (0,50–0,56) ở mọi ngưỡng trong dải. Trang tốt bị loại thường chỉ có 2–3 dòng lặp hai lần (mục liệt kê, tiêu đề bài liên quan, dòng đăng ký nhận tin). Ở mức ≥ 0,23, 814/1.077 trang cũng trượt `gopher_dup_lines`. `gopher_word_count`: trang được giữ có 53–66 âm tiết kém 24/31 (0,77), dưới mức 0,8, nên giữ 53 | `wet_200_cal` |
| `fineweb_dup_line_chars` | `max 0.23` → tắt | Tập test (50 file cuối của `wet_200`): trong 15 trang bị loại sát ngưỡng 0,23, chỉ 5 trang kém (0,33; khoảng tin cậy 95% 0,15–0,58). Ở tập dev, tỉ lệ trang kém không vượt 0,56 ở bất kỳ ngưỡng nào trong dải 0,10–0,23. Trang lặp nhiều vẫn bị `gopher_dup_lines` bắt: ở mức ≥ 0,23, 814/1.077 trang trượt cả luật này | `wet_200_final` |
| tầng 3 | `legacy_encoding_action: flag` → `convert` | Chuyển TCVN3/VNI sang Unicode khi văn bản giải mã đọc được như tiếng Việt (`text/legacy.py`). Thử tổng hợp: 99,3–99,5% văn bản viết bằng TCVN3/VNI được nhận ra; 0/2.000 văn bản sạch bị đổi nhầm (mục 14.2) | `wet_200_par` (0 trang được chuyển) |
| tầng 3, 3b, 4, 6, 7, 8 | Chạy một tiến trình → `parallel.workers: 8`; ftfy chạy theo dòng; `memory.batch_files: 50` | Kết quả không đổi (`compare_runs.py`: IDENTICAL); tầng 3 nhanh 4,9 lần ở một tiến trình (mục 14.1) | `wet_200_par`, `wet_1000` |

## 11. Các lần chạy

Kết quả của từng lần chạy được sao lưu ở `outputs/runs/<lần chạy>/` (`funnel.csv`, `filter_costs.csv`, `run_info.json`, `rule_stats.md`).

| Lần chạy | Dữ liệu | Khác lần chạy trước ở đâu | Vào | Giữ lại | Ghi chú |
|---|---|---|---:|---:|---|
| `baseline_wet_10` | CC-MAIN-2026-39, 10 file WET | Ngưỡng gốc, chưa có tầng 3b | 2.414 | 437 (18,1%) | Tầng 7 loại 76,3% số tài liệu vào tầng |
| `wet_50` | CC-MAIN-2026-39, 50 file WET (gồm 10 file trên) | Chỉ thêm dữ liệu | 12.304 | 2.300 (18,7%) | Tầng 7 loại 74,9%; tỉ lệ trượt từng luật lệch `baseline_wet_10` tối đa 1,8 điểm %. Lọc dòng lặp xóa 122.365 dòng. Near-dup 334, 95% cùng tên miền với bản đại diện |
| `wet_50_bp` | Như `wet_50` | Thêm tầng 3b (jusText) | 12.304 | 5.125 (41,7%) | Tầng 3b loại 4.507 (1.358 trang có ngôn ngữ chính không phải tiếng Việt); tầng 4 chỉ còn loại 7; tầng 7 loại 26,0%. Tổng khoảng 12 phút (tầng 3b 313 giây, chuẩn hóa 258 giây) |
| `wet_50_c4` | Như `wet_50` | Tầng 3b đổi sang `method: c4_lines` | 12.304 | 6.116 (49,7%) | Tầng 3b loại 2.249 (369 trang có ngôn ngữ chính không phải tiếng Việt), chạy 5,8 giây (jusText: 313 giây). Tầng 4 loại 1.230, vì tầng 3b không còn gánh việc lọc trang ngoại ngữ. Spam 597; trùng chính xác 127, gần đúng 151. Tầng 7 loại 1.814/7.930 (22,9%): luật loại nhiều nhất là `gopher_ellipsis_lines` (772), `fineweb_line_punct` không loại trang nào. Tổng khoảng 190 giây |
| `wet_200` | CC-MAIN-2026-39, 200 file WET (gồm 50 file trên) | Thêm bỏ dòng "…" và dòng lặp liên website | 48.815 | 24.621 (50,4%) | Tầng 7 loại 14,9%; 73 dòng lặp liên website, tất cả là boilerplate; tổng 717 giây (chuẩn hóa 435 giây) |
| `wet_200_cal` | Như `wet_200` | Ngưỡng: `gopher_word_count` 53, `gopher_stopwords` 4, `fineweb_dup_line_chars` 0,23 | 48.815 | 25.054 (51,3%) | Khớp số dự tính từ `quality_stats.parquet` |
| `wet_200_final` | Như `wet_200` | Tắt `fineweb_dup_line_chars` | 48.815 | 25.255 (51,7%) | Tầng 7 loại 3.693/28.948 (12,8%); tổng 835 giây ở một tiến trình, chuẩn hóa 636 giây (76%), tầng 7 43 giây |
| `wet_2024_10_50` | CC-MAIN-2024-10, 50 file WET | Cấu hình như `wet_200_final`; dùng để đối chiếu với FineWeb-2 (mục 12) | 18.576 | 10.050 (54,1%) | Bản crawl này có nhiều bản ghi tiếng Việt hơn trên mỗi file so với CC-MAIN-2026-39 (18.576 so với 12.304 trên 50 file) |
| `wet_200_par` | Như `wet_200` | 12 tiến trình, ftfy theo dòng, bật chuyển TCVN3/VNI | 48.815 | 25.255 (51,7%) | Giống hệt `wet_200_final` (`compare_runs.py`: IDENTICAL). Tổng 368 giây: chuẩn hóa 146 giây, tầng 7 127 giây |
| `wet_1000` | CC-MAIN-2026-39, 1.000 file WET (gồm 200 file trên) | 8 tiến trình, `batch_files: 50` | 246.833 | 118.069 (47,8%) | Tỉ lệ loại của tầng 3b, 4, 5, 7 lệch 200 file dưới 1 điểm %; trùng chính xác 6,65%, gần đúng 6,43% (mục 14.6). Tổng 1.038 giây (4,2 ms/tài liệu) |

## 12. Đối chiếu với FineWeb-2 (RQ3)

**Dữ liệu và cách đo:**
- Lần chạy `wet_2024_10_50`: CC-MAIN-2024-10, 50 file, 18.575 tài liệu (giữ 10.050).
- Ghép theo URL với FineWeb-2 của cùng bản crawl. FineWeb-2 có 6,35 triệu dòng của bản crawl này: 2,43 triệu ở `vie_Latn`, 3,93 triệu ở `vie_Latn_removed`.
- Lệnh `fw2-urls` đọc 0,52 GB qua mạng, mất khoảng 2,9 giờ.
- Kết quả gốc nằm ở `outputs/eval/fineweb2_CC-MAIN-2024-10.md` và `fineweb2_pii_vie_Latn.md`.

**Độ phủ:**
- **Chỉ 3.096 trong 18.575 URL (16,7%) có trong FineWeb-2.** Trong cùng 50 file WARC, FineWeb-2 chỉ có 3.085 tài liệu tiếng Việt.
- Giả định, chưa kiểm chứng: phần lớn số còn lại bị FineWeb-2 loại khi khử trùng lặp trên 96 bản crawl. Một phần có thể do trafilatura trích ra văn bản rỗng (9% ở thí nghiệm WARC, mục 3b) hoặc do GlotLID không nhận là tiếng Việt.
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
- Đọc tay 15 trang mẫu: khoảng một nửa là nội dung dùng được (bài báo thể thao, thông báo của trường, bài phong thủy, mô tả sản phẩm). Nửa còn lại là boilerplate hoặc rác: form mật khẩu, thống kê xổ số, một trang soi kèo mà luật spam bỏ sót.

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
- Trang mẫu chỉ được đọc tay, chưa gán nhãn.
- Không lấy văn bản FineWeb-2 để so trực tiếp, chỉ so quyết định giữ/loại theo URL.

## 13. Mức trùng lặp (RQ2)

Số liệu của `wet_200_final` (CC-MAIN-2026-39, 200 file), tính bằng `scripts/dedup_stats.py`. Kết quả gốc nằm ở `outputs/eval/dedup_stats_wet_200_final.md`. Số liệu 1.000 file: mục 14.6.

| Mức | Tài liệu vào | Bị loại hoặc bị xóa | Tỉ lệ | Cùng một tên miền |
|---|---:|---:|---:|---:|
| Trùng chính xác (SHA-1) | 31.152 | 1.005 bản sao | 3,23% | 89,0% số bản sao |
| Trùng gần đúng (MinHash-LSH, ngưỡng ≈ 0,72) | 30.147 | 1.013 | 3,36% | 75,0% số cặp |
| Dòng lặp ≥ 3 trang cùng tên miền | 29.134 | 36.704 dòng | — | 100% (theo định nghĩa) |
| Dòng lặp ≥ 20 tên miền | 29.134 | 11.394 dòng (73 dòng khác nhau, ở 5.809 tài liệu) | — | 0% (theo định nghĩa) |
| Tài liệu rỗng sau khi xóa dòng | 29.134 | 186 | 0,64% | — |

Ngoài ra, tầng 3b bỏ 65,7% số ký tự: phần lớn là menu, footer, lặp lại trên mọi trang của một website.

**Tỉ lệ trùng theo lượng dữ liệu** (tập con lồng nhau chọn ngẫu nhiên từ 200 file, 5 lần):

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
- **Tỉ lệ trùng tăng theo lượng dữ liệu:** trong 200 file, mỗi lần gấp đôi số file, tỉ lệ tăng khoảng 1,5 lần. Trên 1.000 file, tốc độ tăng chậm dần (mục 14.6). Khi khử trùng lặp trên cả bản crawl và trên nhiều bản crawl như FineWeb-2, tỉ lệ sẽ cao hơn nhiều; điều này khớp với việc 83% URL của pipeline không có trong FineWeb-2 (mục 12).
- Với tập con, trùng gần đúng chỉ được tính khi tài liệu được khớp cũng nằm trong tập con, nên con số thấp hơn thực tế. Ở 200 file con số là chính xác.

**Đơn vị shingle** (`dedup-eval`): 3.000 tài liệu đã làm sạch của `wet_200_final`, bỏ các tài liệu rỗng (các tài liệu rỗng có cùng chữ ký MinHash và sẽ tạo cặp trùng giả); nhãn đúng là Jaccard chính xác ≥ 0,75 trên mọi cặp. Kết quả nằm ở `outputs/eval/dedup_units.csv`.

| Đơn vị | Cặp đúng | Cặp LSH | Precision | Recall | F1 | Giây |
|---|---:|---:|---:|---:|---:|---:|
| 5-gram âm tiết (đang dùng) | 43 | 66 | 0,636 | 0,977 | 0,771 | 251 |
| 3-gram âm tiết | 55 | 68 | 0,750 | 0,927 | 0,829 | 225 |
| 15-gram ký tự | 45 | 53 | 0,774 | 0,911 | 0,837 | 1.345 |

- LSH gần như không bỏ sót cặp trùng, nhưng báo cả các cặp có Jaccard dưới 0,75. Lý do: ngưỡng hiệu dụng của cấu hình 14 × 8 (khoảng 0,72) thấp hơn 0,75, và pipeline không kiểm tra lại Jaccard của cặp ứng viên.
- Chênh lệch F1 giữa các đơn vị chưa đủ để đổi đơn vị, vì mỗi đơn vị chỉ có 43–55 cặp. Đơn vị ký tự chậm hơn khoảng 5 lần.

## 14. Thí nghiệm mở rộng

### 14.1. Chạy song song và Spark

`scripts/bench_parallel.py --n 10000` trên CPU Intel Core i5-12450H (8 lõi = 4P + 4E, 12 luồng):

| Cách chạy tầng 3 | ms/tài liệu | So với cách cũ |
|---|---:|---:|
| ftfy trên cả văn bản, 1 tiến trình (cách cũ) | 14,36 | 1,0 |
| ftfy theo dòng, 1 tiến trình | 2,91 | 4,9 |
| ftfy theo dòng, 2 tiến trình | 1,19 | 12,0 |
| ftfy theo dòng, 4 tiến trình | 0,74 | 19,3 |
| ftfy theo dòng, 8 tiến trình | 0,58 | 24,9 |
| ftfy theo dòng, 12 tiến trình | 0,74 | 19,5 |

- 8 tiến trình nhanh nhất; 12 tiến trình chậm hơn, có lẽ vì 4 luồng thêm là siêu luồng của lõi P (giả định). Cấu hình đặt `workers: 8`.
- `wet_200_par` (12 tiến trình) chạy 368 giây thay vì 835 giây, kết quả giống hệt `wet_200_final`.
- Trong `wet_200_par`, các tầng chỉ chạy một tiến trình lại chậm hơn 2–3 lần so với `wet_200_final`: tầng 7 127 giây thay vì 43 giây, xuất dữ liệu 25 giây thay vì 9 giây. Giả định (chưa kiểm): CPU hạ xung sau khi chạy hết các lõi một lúc lâu.
- Tầng 7 cũng chạy song song, và điểm bảng mã cũ được tính trong tiến trình con. Kiểm trên 55 file trong máy ảo 2 lõi: kết quả, `quality_stats.parquet` và tỉ lệ qua từng luật giống hệt bản một tiến trình; thời gian tầng 7 giảm từ 11,3 xuống 5,9 giây. `memory.batch_files: 10` cũng cho kết quả giống hệt.
- `spark_runner.py` chạy tầng 3–9:
  - Tầng theo từng tài liệu chạy bằng `mapInPandas`; trùng chính xác dùng cửa sổ theo SHA-1.
  - Trùng gần đúng: Spark tìm các dải MinHash có ở hơn một tài liệu, rồi driver duyệt những tài liệu đó theo thứ tự như tầng 6. Có test so với datasketch: `tests/test_spark_runner.py`.
  - Trên 55 file (13.520 tài liệu vào, 7.342 giữ lại): giống hệt bản pandas.
  - Máy ảo 2 lõi: Spark 75 giây (179 tài liệu/giây), pandas 2 tiến trình 54 giây, pandas 1 tiến trình 92 giây. Số này chỉ dùng để kiểm tính đúng; thông lượng của Spark theo số lõi chưa đo.
  - Spark 3.5 lỗi ở `mapInPandas` với Java 21 nên dùng Spark 4.0.

### 14.2. Chuyển TCVN3/VNI

- Thử tổng hợp (`scripts/legacy_eval.py`): lấy 2.000 tài liệu sạch, viết lại bằng TCVN3 hoặc VNI, rồi cho tầng 3 khôi phục (`outputs/eval/legacy_eval.md`).
  - Nhận ra đúng bảng mã: 99,5% (TCVN3) và 99,3% (VNI).
  - Độ chính xác ký tự trung bình: 0,998.
  - TCVN3 chỉ khôi phục đúng nguyên văn 60% vì bảng mã này không phân biệt chữ hoa có dấu; nếu bỏ qua hoa thường thì đúng 99,3%.
  - 0/2.000 văn bản sạch bị đổi nhầm.
- Dữ liệu thật:
  - 0 trong 48.815 tài liệu của 200 file được chuyển.
  - `scripts/legacy_scan.py`: 0 trong 101.322 bản ghi (mọi ngôn ngữ) của 5 file WET khác.
  - 1.000 file (`wet_1000`): 1 trong 246.833 bản ghi được chuyển. Đó là trang trộn văn bản Unicode với một đoạn TCVN3; chuyển cả trang làm hỏng phần Unicode ("nói" thành "núi").
- Kết luận: trong bản crawl 2026, trang TCVN3/VNI gần như không còn; bước chuyển chỉ tốn khoảng 0,4 ms/tài liệu. Nên chuyển theo từng đoạn thay vì cả trang (mục 9).
- Bộ phát hiện theo tỉ lệ ký tự (`legacy_score`) vẫn báo nhầm, nhưng không ảnh hưởng vì quyết định chuyển dựa trên văn bản sau giải mã.

### 14.3. GlotLID thay heuristic (tầng 4)

`scripts/langid_compare.py` trên 37.456 tài liệu vào tầng 4 của 200 file (`outputs/eval/langid_compare.md`):

| Ngưỡng | Heuristic giữ | GlotLID giữ (P(vie_Latn)) |
|---:|---:|---:|
| 0,5 | 33.609 | 33.849 |
| 0,6 | 33.396 | 33.817 |
| 0,8 | 32.425 | 33.722 |

- Ở ngưỡng 0,6, hai bộ đồng thuận 98,8% (κ = 0,934).
- GlotLID giữ thêm 437 trang mà heuristic loại; heuristic giữ 16 trang mà GlotLID loại.
- Phân loại thô 437 trang theo 300 ký tự đầu, bằng quy tắc tự động (số gần đúng):
  - khoảng 227 trang là tiếng Việt có dấu nhưng ít từ dừng (danh mục sản phẩm, địa chỉ, catalog kỹ thuật), điểm heuristic 0,4–0,6;
  - khoảng 132 trang viết không dấu, trong đó ít nhất 65 trang là quảng cáo cờ bạc ("nha cai", "game bai doi thuong", "tai xiu");
  - khoảng 78 trang có phần đầu là tiếng Anh.
- Hệ quả: heuristic tình cờ loại được spam không dấu. Nếu đổi sang GlotLID, tầng 5 cần thêm từ khóa cờ bạc không dấu, vì danh sách hiện tại chỉ có từ có dấu.
- Đo trên `wet_1000` với 12 từ khóa không dấu ("nha cai", "ca cuoc", "tai xiu", "no hu", "soi cau", "doi thuong"...), khớp theo ranh giới từ, ngưỡng ≥ 3 lần:
  - 12 trong 118.069 tài liệu giữ lại sẽ bị loại thêm; 6/6 trang đọc thử là cờ bạc;
  - 225 trong 20.513 tài liệu bị heuristic loại ở tầng 4 khớp, tức là loại trang GlotLID sẽ cho qua.

### 14.4. Đơn vị từ (underthesea) cho tầng 7

`scripts/word_unit_eval.py` trên 28.948 tài liệu vào tầng 7 (`outputs/eval/word_unit_eval.md`):

- Tách từ tốn khoảng 32 ms CPU mỗi tài liệu, so với 0,25 ms khi tách âm tiết; trung bình 1,38 âm tiết mỗi từ.
- Giữ nguyên ngưỡng (53): đếm theo từ giữ 24.058 tài liệu, đếm theo âm tiết giữ 25.246. Chênh lệch chủ yếu do `gopher_word_count`: 11,2% tài liệu bị loại khi đếm theo từ, so với 5,6% khi đếm theo âm tiết.
- Khi nâng ngưỡng âm tiết lên 73 (53 × 1,38), chỉ còn 563 quyết định (1,9%) khác so với đếm theo từ.
- Trên 409 trang gán nhãn, tỉ lệ quyết định khớp nhãn:

| Cách đếm | Khớp nhãn |
|---|---:|
| Âm tiết, ngưỡng 53 | 0,594 |
| Từ, ngưỡng 53 | 0,707 |
| Âm tiết, ngưỡng 73 | 0,719 |

- Kết luận: đếm theo từ chủ yếu tương đương một ngưỡng độ dài cao hơn; đếm âm tiết với ngưỡng tương ứng cho kết quả ngang bằng mà rẻ hơn khoảng 130 lần.
- Các trang gán nhãn nằm sát ngưỡng âm tiết, nên con số khớp nhãn chỉ dùng để so các cách đếm với nhau.
- Nâng `gopher_word_count` lên khoảng 73 sẽ loại thêm khoảng 1.100 tài liệu (4,5%).

### 14.5. Mô hình chất lượng học từ Wikipedia

`scripts/quality_model.py` (`outputs/eval/quality_model.md`):
- Dữ liệu: 15.000 bài Wikipedia tiếng Việt (bản 20231101, 2 file) và 15.000 tài liệu web vào tầng 7, không trùng các trang đã gán nhãn. Chỉ dùng bài dài từ 1.000 ký tự sau luật dòng của tầng 3b, vì phần lớn bài Wikipedia tiếng Việt là bài sơ khai về loài sinh vật (ở file train-00002-of-00004, trung vị 193 ký tự, chỉ 4% còn từ 200 ký tự sau luật dòng).
- Bộ phân loại fastText tách được Wikipedia và web khá rõ: đúng 0,986 trên Wikipedia giữ lại, 0,952 trên web giữ lại.

| Tín hiệu | AUC, mọi trang gán nhãn | AUC, trang luật giữ | AUC, trang luật loại |
|---|---:|---:|---:|
| fastText P(web) | 0,640 | 0,676 | 0,616 |
| Perplexity trigram | 0,583 | 0,541 | 0,628 |

- Khi loại cùng số trang như các luật (181/409): tỉ lệ trang kém trong số bị loại là 0,829 với luật, 0,762 với fastText và 0,762 với perplexity. Ở điểm hoạt động này, mô hình kém hơn luật.
- Mô hình có tín hiệu bổ sung ở phần luật bỏ sót. Trong 228 trang gán nhãn mà luật giữ (59% kém), một phần tư có P(web) cao nhất kém 81%, phần còn lại kém 49%. Nhóm "một phần tư" có 73 trang thay vì 57 vì nhiều trang có cùng điểm.
- Trên 3.000 tài liệu giữ lại ngẫu nhiên, 92,5% có P(web) ≥ 0,9; perplexity trung vị 236 (Wikipedia giữ lại: 124). Bộ phân loại học thể loại "Wikipedia hay web" nhiều hơn chất lượng, nên điểm bị dồn sát 1.
- Muốn dùng làm bộ lọc thứ hai sau luật thì phải chọn ngưỡng trên các trang gán nhãn phía luật giữ, hoặc huấn luyện bộ phân loại trên nhãn tốt/kém thay vì Wikipedia/web.

### 14.6. 1.000 file (RQ2, RQ4)

Lần chạy `wet_1000`: 1.000 file WET của CC-MAIN-2026-39, gồm 200 file của `wet_200_final`.

| Chỉ số | 200 file | 1.000 file |
|---|---:|---:|
| Tài liệu vào | 48.815 | 246.833 |
| Giữ lại | 25.255 (51,7%) | 118.069 (47,8%) |
| Ký tự bị 3b bỏ | 65,7% | 65,8% |
| Tầng 4 loại (trong số vào tầng) | 10,8% | 10,8% |
| Tầng 5 loại | 6,7% | 6,8% |
| Trùng chính xác | 3,23% | 6,65% |
| Trùng gần đúng | 3,36% | 6,43% |
| Bản sao chính xác cùng tên miền | 89,0% | 89,4% |
| Cặp trùng gần đúng cùng tên miền | 75,0% | 78,8% |
| Tầng 7 loại | 12,8% | 13,0% |
| Dòng lặp ở ≥ 20 tên miền (số dòng khác nhau) | 73 | 279 |
| Thời gian | 835 giây, 1 tiến trình | 1.038 giây, 8 tiến trình |

- **Các tầng lọc ổn định theo quy mô:** tỉ lệ loại của tầng 3b, 4, 5, 7 và của từng luật tầng 7 lệch 200 file dưới 1 điểm %.
  - `gopher_word_count`: 6,4% so với 5,6%.
  - `gopher_stopwords`: 4,6% so với 3,9%.
  - `gopher_top_4gram`: 4,2% so với 3,4%.
- **Giữ lại ít hơn chủ yếu vì trùng lặp tăng:** trùng chính xác và gần đúng đều gần gấp đôi.
- **Tốc độ tăng của trùng chính xác chậm dần.** Đường cong lấy từ tập con lồng nhau của 1.000 file (`outputs/eval/dedup_stats_wet_1000.md`), đếm chính xác bằng `text_sha1`:

| Số file | 25 | 50 | 100 | 200 | 400 | 800 | 1.000 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Trùng chính xác (%) | 0,97 | 1,46 | 2,12 | 3,13 | 4,44 | 6,07 | 6,65 |

  Mỗi lần gấp đôi, tỉ lệ tăng 1,51 → 1,45 → 1,48 → 1,42 → 1,37 lần. Nếu ngoại suy theo hệ số 1,5 lần như ở mục 13, 1.000 file sẽ cho khoảng 8,3%; thực đo là 6,65%. Từ 200 lên 1.000 file, trùng gần đúng tăng 1,91 lần, tức khoảng 1,32 lần mỗi lần gấp đôi.
- **Trùng gần đúng đếm trên tập con không dùng được.** Tập con 200 file cho 1,45%, trong khi lần chạy 200 file thật cho 3,36%. Lý do: tài liệu đại diện của cụm thường không nằm trong tập con. Chỉ điểm 1.000 file là chính xác.
- **Luật dòng lặp liên website:** số dòng khác nhau bị xóa tăng từ 73 lên 279, vì ngưỡng 20 tên miền cố định trong khi dữ liệu tăng 5 lần. 5 dòng phổ biến nhất vẫn là chuỗi giao diện ("Lưu tên của tôi, email…", "Chưa có sản phẩm trong giỏ hàng.").
- **Tốc độ:** 4,2 ms/tài liệu, so với 17,1 ms ở một tiến trình (`wet_200_final`).
  - Chuẩn hóa vẫn chiếm 46% thời gian (477 giây). Tiếp theo là trùng gần đúng 130 giây, tầng 7 105 giây, 3b 89 giây.
  - Ngoại suy tuyến tính cho cả bản crawl (khoảng 24,7 triệu bản ghi tiếng Việt): khoảng 29 giờ với cấu hình này, chưa tính thời gian tải. Ở quy mô đó, khử trùng lặp trong bộ nhớ không đủ RAM; khi ấy cần `spark_runner.py`.
- Thời gian mỗi luật trong `filter_costs.csv` của lần chạy nhiều tiến trình cao hơn khoảng 3–4 lần so với một tiến trình, vì các tiến trình chia lõi P và E. Chi phí luật cho RQ4 đo bằng `scripts/time_quality_order.py`, script này luôn chạy một tiến trình.

### 14.7. Rò rỉ benchmark VMLU

`scripts/benchmark_overlap.py` với bộ Vi-MQA v1.5 tải từ vmlu.ai (dev, valid, test: 10.880 câu), so với 118.069 tài liệu giữ lại của `wet_1000` (`outputs/eval/benchmark_overlap_vmlu.md`). Một câu bị tính là trùng khi câu hỏi hoặc các phương án có chung một dãy n âm tiết với một tài liệu.

| n | Câu đủ dài để kiểm | Câu có dãy chung | Tỉ lệ |
|---:|---:|---:|---:|
| 13 | 9.095 | 380 | 4,18% |
| 8 | 10.715 | 2.404 | 22,44% |

- 340 trong 380 câu thuộc tập test.
- Phần lớn là trích dẫn chung, không phải lộ câu hỏi. Câu hỏi VMLU và trang web cùng chép một văn bản gốc: luật, nghị định, giáo trình chính trị. Các trang trùng nhiều nhất: wipo.int (văn bản luật), trang tin pháp luật, cổng thông tin nhà nước.
- Với mỗi câu trong 380 câu, lấy tài liệu khớp có tỉ lệ dãy 8 âm tiết của câu hỏi nằm trong tài liệu cao nhất:
  - Trung vị chỉ 15%.
  - 65 câu có ít nhất 50% câu hỏi nằm trong một trang.
  - 17 câu có ít nhất 80%, tức câu hỏi xuất hiện gần nguyên văn: trang ôn thi bằng lái (thegioiphuongtien.vn), trang giải bài tập (loigiaihay.com, hoc247.net), trang trắc nghiệm (vuatracnghiem.edu.vn).
  - Văn bản của đáp án đúng chỉ tìm thấy trong cùng trang ở 2 câu. Cách dò này còn thô.
- Kết luận: trong 1.000 file (khoảng 1% bản crawl), lộ gần nguyên văn ở mức 17–65 câu (0,2–0,6% số câu). Con số sẽ tăng theo lượng dữ liệu.

### 14.8. Mô hình ngôn ngữ nhỏ: dữ liệu thô so với dữ liệu sạch

`scripts/lm_ablation.py` (`outputs/eval/lm_ablation.md`).

**Thiết lập**
- Dữ liệu: cùng các trang của `wet_200_final`.
  - "Thô": văn bản WET ở tầng 1 của mọi tài liệu vào lần chạy (48.815).
  - "Sạch": 25.255 tài liệu được giữ.
- Tokenizer BPE 16.000 từ vựng, học trên lượng ký tự bằng nhau từ hai kho; không học trên Wikipedia.
- Mô hình: GPT 4 lớp, 256 chiều, 7,3 triệu tham số, ngữ cảnh 128 token, preset `cpu`. Mỗi kho được huấn luyện trên đúng 3 triệu token, đi qua một lượt, không lặp.
- Chạy 2 seed, trên máy ảo 2 lõi, mỗi lần khoảng 24 phút.
- Đo loss trên 500 nghìn token mỗi tập kiểm tra:
  - bài Wikipedia giữ lại (không có trong cả hai kho), đã qua luật dòng của 3b;
  - cùng các bài đó ở dạng nguyên văn (giữ tiêu đề, danh sách, dòng ngắn), chỉ seed 0;
  - văn bản sạch giữ lại;
  - văn bản thô giữ lại.

| Kho huấn luyện | Loss Wikipedia (perplexity) | Loss Wikipedia nguyên văn (perplexity) | Loss web sạch | Loss web thô |
|---|---:|---:|---:|---:|
| Thô (trung bình 2 seed) | 6,586 (≈ 725) | 6,709 (≈ 820) | 5,957 | 5,935 |
| Sạch (trung bình 2 seed) | 5,938 (≈ 379) | 6,164 (≈ 475) | 5,153 | 6,616 |
| Sạch − thô | −0,648 | −0,545 | −0,804 | +0,682 |

- Chênh lệch giữa 2 seed chỉ 0,02–0,06, nhỏ hơn nhiều so với chênh lệch giữa hai kho.
- Cùng số token, mô hình học trên dữ liệu sạch có perplexity trên Wikipedia thấp hơn khoảng 1,9 lần. Mô hình học trên dữ liệu thô chỉ tốt hơn trên chính văn bản thô (menu, footer, trang ngoại ngữ).
- Trên Wikipedia nguyên văn, perplexity vẫn thấp hơn khoảng 1,7 lần, nên phần lớn lợi ích không đến từ việc kho sạch có cùng định dạng "chỉ câu văn" với tập đo.
- **Giới hạn:** mô hình rất nhỏ và chỉ học 3 triệu token (khoảng 11 triệu ký tự), còn xa mức hội tụ. Chưa đo trên benchmark (VMLU): mô hình cỡ này gần như trả lời ngẫu nhiên.

## Nguồn

- Rae et al. (2021). *Scaling Language Models: Methods, Analysis & Insights from Training Gopher.* [arXiv:2112.11446](https://arxiv.org/abs/2112.11446). Phụ lục A mô tả các luật chất lượng và luật lặp.
- Raffel et al. (2020). *Exploring the Limits of Transfer Learning with a Unified Text-to-Text Transformer* (C4). [arXiv:1910.10683](https://arxiv.org/abs/1910.10683), mục 2.2.
- Penedo et al. (2024). *The FineWeb Datasets.* [arXiv:2406.17557](https://arxiv.org/abs/2406.17557); [blog FineWeb](https://huggingface.co/spaces/HuggingFaceFW/blogpost-fineweb-v1).
- [FineWeb-2](https://huggingface.co/datasets/HuggingFaceFW/fineweb-2) (GlotLID, ngưỡng theo từng ngôn ngữ).
- Pomikálek, J. (2011). *Removing Boilerplate and Duplicate Content from Web Corpora* (luận án, Masaryk University); thuật toán được cài đặt trong [jusText](https://github.com/miso-belica/jusText). Tầng 3b dùng lại các bước phân loại của jusText.
- Barbaresi, A. (2021). *Trafilatura: A Web Scraping Library and Command-Line Tool for Text Discovery and Extraction.* ACL 2021 System Demonstrations. Cấu hình FineWeb dùng: [datatrove, extractors/trafilatura.py](https://github.com/huggingface/datatrove/blob/main/src/datatrove/pipeline/extractors/trafilatura.py).
- Wenzek et al. (2020). *CCNet: Extracting High Quality Monolingual Datasets from Web Crawl Data.* LREC 2020.
- [Danh sách chặn UT1](https://dsi.ut-capitole.fr/blacklists/) (Université Toulouse Capitole).
