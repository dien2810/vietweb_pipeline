---
language:
  - vi
pretty_name: vietweb – văn bản web tiếng Việt đã làm sạch (CC-MAIN-2026-39, 200 file WET)
size_categories:
  - 10K<n<100K
task_categories:
  - text-generation
source_datasets:
  - Common Crawl CC-MAIN-2026-39
license: other   # văn bản không được phát hành lại; xem mục "Pháp lý và đạo đức"
---

# Dataset card: văn bản web tiếng Việt đã làm sạch (bản nội bộ)

Tập dữ liệu do pipeline `vietweb` tạo ra trong đề tài môn Kỹ thuật xử lý dữ liệu. Văn bản **không được phát hành lại** vì có thể chứa nội dung có bản quyền. Card này mô tả lần chạy `wet_200_final`; mã nguồn, cấu hình, nhãn gán tay và số liệu tổng hợp nằm ở https://github.com/dien2810/vietweb_pipeline.

## Tóm tắt

| Mục | Giá trị |
|---|---|
| Nguồn | File WET của Common Crawl, bản crawl `CC-MAIN-2026-39` |
| Số file WET đã xử lý | 200 trên 100.000 file, chọn ngẫu nhiên (seed 42); 12,9 GB tải về |
| Ngày crawl của các trang | 04/09/2026 – 17/09/2026 |
| Tài liệu đầu vào | 48.815 bản ghi có nhãn CLD2 `vie`, ít nhất 200 ký tự |
| Tài liệu giữ lại | **25.255** (51,7%) |
| Tài liệu bị loại (tập kiểm toán) | 23.560, mỗi tài liệu có tầng và lý do loại |
| Kích thước | 93,2 triệu ký tự; 20,3 triệu âm tiết; 65,5 MB Parquet (tập giữ), 27,9 MB (tập loại) |
| Tên miền | 17.491; `.vn` 49,7%, `.com` 37,1%, `.net` 4,6%; 10 tên miền lớn nhất chỉ chiếm 1,5% số tài liệu |
| Độ dài tài liệu | Trung vị 2.466 ký tự (536 âm tiết); p10 469 ký tự, p90 7.566 ký tự |
| Ngày chạy | 28/10/2026, 17:07 UTC (`outputs/runs/wet_200_final/run_info.json`) |
| Phiên bản code | Commit `f366cf7` cộng các thay đổi chưa commit lúc chạy. Cập nhật mã commit sau khi đẩy code lên GitHub |
| Máy chạy | Intel Core i5-12450H, RAM 16 GB, Windows; một tiến trình; tổng 835 giây |

## Quy trình

Mười tầng: thu thập → lưu thô → chuẩn hóa → bỏ boilerplate (3b) → nhận diện ngôn ngữ → lọc URL và spam → khử trùng lặp → lọc chất lượng → che thông tin cá nhân → xuất dữ liệu. Tài liệu bị loại không bị xóa mà được chuyển sang tập kiểm toán cùng lý do loại đầu tiên. Cấu hình đầy đủ ở `configs/pipeline.yaml`, ngưỡng tiếng Việt ở `configs/vie_thresholds.yaml`, danh mục luật và nhật ký thay đổi ở `LUAT_LOC.md`.

| Tầng | Còn lại | Bị loại | Lý do loại chính |
|---|---:|---:|---|
| Đầu vào | 48.815 | – | – |
| 3b Bỏ boilerplate | 37.456 | 11.359 | còn dưới 200 ký tự sau khi bỏ dòng boilerplate (2.672 trang có ngôn ngữ CLD2 chính không phải tiếng Việt) |
| 4 Nhận diện ngôn ngữ | 33.396 | 4.060 | điểm tiếng Việt < 0,6 |
| 5 URL và spam | 31.152 | 2.244 | ≥ 3 lần xuất hiện từ khóa cờ bạc |
| 6 Khử trùng lặp | 28.948 | 2.204 | 1.005 trùng chính xác, 1.013 trùng gần đúng, 186 rỗng sau khi xóa dòng lặp |
| 7 Lọc chất lượng | 25.255 | 3.693 | `gopher_word_count` (1.609), `gopher_dup_lines` (763), `gopher_stopwords` (365) |
| 8 Che thông tin cá nhân | 25.255 | 0 | chỉ thay thế, không loại |

## Cấu trúc dữ liệu

Hai thư mục Parquet: `processed/kept/kept-0000N.parquet` và `processed/dropped/dropped-0000N.parquet`, tối đa 20.000 dòng mỗi file.

| Cột | Ý nghĩa |
|---|---|
| `doc_id` | Mã tài liệu: 20 ký tự đầu của SHA-1(`record_id` + `url`) |
| `url`, `domain` | URL gốc và tên miền |
| `snapshot`, `warc_record_id`, `warc_refers_to`, `crawl_date` | Nguồn gốc trong Common Crawl; `warc_refers_to` trỏ tới bản ghi WARC tương ứng |
| `cld2_langs` | Nhãn ngôn ngữ CLD2 trong header WET, ngôn ngữ chính đứng đầu |
| `text` | Văn bản đã chuẩn hóa, đã bỏ boilerplate và dòng lặp, đã che thông tin cá nhân |
| `legacy_score` | Điểm nghi ngờ bảng mã cũ TCVN3/VNI (tầng 3) |
| `bp_chars_ratio` | Tỉ lệ ký tự còn lại sau tầng 3b |
| `lang_score` | Điểm tiếng Việt (tầng 4); trung vị 1,0, thấp nhất 0,601 trong tập giữ |
| `spam_kw_hits` | Số lần xuất hiện từ khóa cờ bạc (tầng 5) |
| `text_sha1` | SHA-1 của văn bản đã chuẩn hóa, dùng để khử trùng lặp chính xác |
| `near_dup_cluster` | `doc_id` của tài liệu đại diện cho cụm trùng gần đúng |
| `pii_email`, `pii_ipv4`, `pii_phone_vn`, `pii_cccd` | Số chuỗi đã che theo từng loại |
| `drop_stage`, `drop_reason` | Chỉ có trong tập bị loại |

## Các lựa chọn riêng cho tiếng Việt

- **Chuẩn hóa:** ftfy sửa lỗi giải mã, Unicode NFC, thống nhất vị trí dấu thanh theo kiểu cũ (*thuỷ* → *thủy*).
- **Bỏ boilerplate:** luật dòng kiểu C4. Chỉ giữ dòng kết thúc bằng dấu câu và có ít nhất 5 âm tiết; bỏ dòng chứa "javascript" và dòng kết thúc bằng dấu ba chấm. Cách này được chọn vì khớp với văn bản trafilatura tốt hơn jusText (F1 theo ký tự 0,756 so với 0,728 trên 737 trang).
- **Đơn vị đếm:** "từ" trong các luật Gopher được tính bằng âm tiết (tách theo khoảng trắng). Chưa thử đếm theo từ tách bằng underthesea.
- **Khử trùng lặp gần đúng:** MinHash-LSH, shingle 5-gram âm tiết, 112 hàm băm (14 dải × 8 hàng, ngưỡng hiệu dụng ≈ 0,72).
- **Dòng lặp:** xóa dòng ≥ 10 ký tự lặp ở ≥ 3 trang cùng tên miền (36.704 dòng) và dòng xuất hiện ở ≥ 20 tên miền (11.394 dòng, 73 dòng khác nhau như "Chưa có sản phẩm trong giỏ hàng.").
- **Ngưỡng đã hiệu chỉnh:** `gopher_word_count` ≥ 53 âm tiết (gốc 50), `gopher_stopwords` ≥ 4 từ dừng tiếng Việt (gốc 2 từ dừng tiếng Anh; danh sách 53 từ), tắt `fineweb_dup_line_chars`. Bảng đầy đủ: phụ lục A của báo cáo.
- **Che thông tin cá nhân:** email → `<EMAIL>`, IPv4 → `<IP>`, số điện thoại di động Việt Nam (0/84/+84) → `<PHONE>`, dãy 12 chữ số → `<ID>`.

## Đánh giá chất lượng

| Chỉ số | Kết quả | Nguồn |
|---|---|---|
| Tỉ lệ trang kém trong số trang bị loại gần ngưỡng (tập test) | `gopher_stopwords` 0,93 · `gopher_word_count` 0,87 · `gopher_top_4gram` 0,87 · `gopher_mean_word_length` 0,73 | 149 trang gán nhãn tay, một người gán |
| MinHash-LSH so với Jaccard chính xác ≥ 0,75 (3.000 tài liệu) | Recall 0,977; precision 0,636 | `outputs/eval/dedup_units.csv` |
| Trùng lặp trong 200 file | 3,23% trùng chính xác, 3,36% trùng gần đúng; 89% và 75% nằm trong cùng một website | `outputs/eval/dedup_stats_wet_200_final.md` |
| Thông tin cá nhân đã che | SĐT 3.651 lần (2.278 tài liệu); email 442 (373); IPv4 173 (39); dãy 12 số 23 (16) | `funnel.csv` |

Số lần che là cận trên: mẫu IPv4 khớp cả DNS công cộng, dãy 12 số khớp cả số tài khoản ngân hàng.

## Mục đích sử dụng

- **Phù hợp:** nghiên cứu về làm sạch và kiểm định dữ liệu web tiếng Việt; so sánh với FineWeb-2 và các bộ dữ liệu khác; làm tập thử cho các bước lọc mới. Tập kiểm toán phù hợp để đọc lại và gán nhãn.
- **Không phù hợp:** phát hành lại văn bản; huấn luyện mô hình dùng thật khi chưa lọc thêm; bất kỳ việc gì nhằm nhận diện cá nhân.

## Hạn chế đã biết

- **Quy mô nhỏ:** 200 file của một bản crawl (0,2% bản crawl). Tỉ lệ trùng tăng khoảng 1,5 lần mỗi khi dữ liệu gấp đôi, nên tỉ lệ trùng thật trên toàn bản crawl cao hơn nhiều. Chưa khử trùng lặp giữa các bản crawl.
- **Đầu vào là WET:** luật dòng C4 bỏ cả tiêu đề, mục danh sách và bảng, vì các dòng này không kết thúc bằng dấu câu. Văn bản giữ lại vì thế thiếu cấu trúc. Một số trang có JavaScript trong WET bị loại dù nội dung thật vẫn trích được từ HTML.
- **Còn rác:** ngay trên ngưỡng `gopher_word_count` và `gopher_stopwords`, 80–93% trang được giữ trong mẫu gán nhãn vẫn kém. Các luật dựa trên hình thức chỉ loại được trang rất ngắn hoặc rất ít từ dừng; cần thêm bộ phân loại chất lượng.
- **Nhận diện ngôn ngữ:** dùng heuristic tự viết (tỉ lệ âm tiết có dấu và từ dừng), chưa dùng GlotLID; có thể bỏ sót văn bản không dấu. Đã thấy một trang tiếng Việt thật bị loại nhầm.
- **Bảng mã cũ:** bộ phát hiện TCVN3/VNI báo nhầm (trong mẫu 50 file, cả 8 trang bị gắn cờ đều là tiếng Thổ Nhĩ Kỳ hoặc tiếng Kurd) và chưa có bước chuyển đổi.
- **Thông tin cá nhân:** chỉ che 4 loại bằng biểu thức chính quy; tên người, địa chỉ, số điện thoại bàn không được che.
- **Gán nhãn:** chỉ một người gán nên chưa đo được độ đồng thuận giữa người gán. Chưa huấn luyện mô hình ngôn ngữ để kiểm chứng chất lượng.

## Tái tạo

```powershell
python -m vietweb collect --n-files 200        # chọn ngẫu nhiên 200 file WET (seed 42), chỉ giữ bản ghi tiếng Việt
python -m vietweb run --crawl CC-MAIN-2026-39  # chạy các tầng 3–9, ghi data\processed
python -m vietweb status                       # xem funnel
```

Chi tiết ở `HUONG_DAN_CHAY.md`. Kết quả của lần chạy này đã được sao lưu ở `outputs/runs/wet_200_final`.

## Pháp lý và đạo đức

- Dữ liệu Common Crawl tuân theo [điều khoản sử dụng của Common Crawl](https://commoncrawl.org/terms-of-use).
- Thông tin cá nhân được che trước khi xuất. Kết quả chỉ được báo cáo ở dạng số liệu tổng hợp, có tham chiếu Luật Bảo vệ dữ liệu cá nhân (hiệu lực từ 01/01/2026). Đề tài không đánh giá việc tuân thủ pháp luật.
- Văn bản đã xử lý không được phát hành lại. Kho mã công khai chỉ nên chứa mã nguồn, cấu hình, số liệu tổng hợp và nhãn gán tay ở dạng mã + nhãn (`calibration_*_key.csv` và cột `label`). Các file mẫu có cột `text` (`outputs/eval/calibration_*.csv`, `outputs/eval/*_examples.csv`) chứa văn bản gốc, URL và có thể có số điện thoại, nên cần giữ ở máy cá nhân.

## Trích dẫn

Nguyễn An Trần Điền (2026). *Xây dựng pipeline thu thập, làm sạch và kiểm định chất lượng dữ liệu văn bản web tiếng Việt từ Common Crawl phục vụ huấn luyện mô hình ngôn ngữ.* Báo cáo cuối kì môn Kỹ thuật xử lý dữ liệu, Trường Đại học Công nghệ Thông tin, Thành phố Hồ Chí Minh.
