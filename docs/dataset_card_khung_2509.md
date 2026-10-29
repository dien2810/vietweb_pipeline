# Dataset card — Văn bản web tiếng Việt đã làm sạch (bản nội bộ)

> Mẫu cần điền sau lần chạy chính thức. Không phát hành lại văn bản vì có thể chứa nội dung có bản quyền.

## Tóm tắt
- **Nguồn:** file WET của Common Crawl, bản crawl: `[điền]`
- **Số file WET đã xử lý:** `[điền]` · **Tài liệu đầu vào:** `[điền]` · **Tài liệu giữ lại:** `[điền]`
- **Ngày chạy:** `[điền]` · **Phiên bản code:** commit `[điền]`

## Quy trình
Chín tầng: thu thập → lưu thô → chuẩn hóa → nhận diện ngôn ngữ → lọc URL → khử trùng lặp (chính xác, MinHash-LSH, cấp dòng) → lọc chất lượng → che thông tin cá nhân → xuất dữ liệu. Cấu hình đầy đủ: `configs/pipeline.yaml`, ngưỡng: `configs/vie_thresholds.yaml`.

## Cấu trúc dữ liệu
| Cột | Ý nghĩa |
|---|---|
| `doc_id` | Mã tài liệu (sha1 của record ID + URL, 20 ký tự) |
| `url`, `domain` | URL gốc và tên miền |
| `snapshot`, `warc_record_id`, `crawl_date` | Nguồn gốc trong Common Crawl |
| `text` | Văn bản đã chuẩn hóa, đã che thông tin cá nhân |
| `lang_score` | Điểm nhận diện tiếng Việt |
| `drop_stage`, `drop_reason` | Chỉ có trong tập bị loại |

## Các lựa chọn riêng cho tiếng Việt
- Unicode NFC; dấu thanh chuẩn hóa theo kiểu `[old/new]`.
- Đơn vị đếm cho luật chất lượng: `[syllable/word]`; shingle khử trùng lặp: `[đơn vị, n]`.
- Ngưỡng đã hiệu chỉnh: xem bảng A1 trong báo cáo.

## Hạn chế đã biết
- Văn bản WET còn menu và chân trang; khử dòng lặp chỉ loại được một phần.
- Nhận diện ngôn ngữ `[backend]` có thể bỏ sót văn bản không dấu.
- Mẫu PII dựa trên biểu thức chính quy, có thể nhận nhầm dãy 12 chữ số.

## Pháp lý và đạo đức
Dữ liệu Common Crawl tuân theo điều khoản sử dụng của Common Crawl. Thông tin cá nhân đã được che; kết quả chỉ báo cáo ở dạng số liệu tổng hợp.
