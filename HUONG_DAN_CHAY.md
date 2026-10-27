# Hướng dẫn chạy pipeline `vietweb`

Mọi lệnh dưới đây chạy trong **PowerShell** trên Windows, tại thư mục repo:

```powershell
cd E:\Dien\Saudh\uit\mon_hoc\data_processing\Project\vietweb
```

## Chạy phần nào trước

| Thứ tự | Việc | Mất bao lâu (ước tính) | Cần mạng |
|---|---|---|---|
| 1 | Cài môi trường Python (mục 1) | 10–15 phút | Có |
| 2 | Chạy `pytest` để kiểm tra cài đặt (mục 2) | vài giây | Không |
| 3 | Chạy thử toàn bộ pipeline trên dữ liệu giả lập (mục 3) | 1 phút | Không |
| 4 | **Thu thập dữ liệu thật: 1 file WET, rồi 10 file** (mục 4) | 5–20 phút | Có |
| 5 | Chạy pipeline trên 10 file, xem funnel và tài liệu bị loại (mục 5) | vài phút | Không |

Bước 4–5 là mốc "tải thử 10 file" của tuần 1–2 trong đề cương. Sau đó làm theo lịch ở mục 6.

Đã có 50 file: làm mục 5b (bỏ boilerplate và đối chiếu với WARC) trước khi tăng lên 200 file.

---

## 1. Cài đặt

**Yêu cầu:** Python 3.10–3.12 (khuyên 3.11), khoảng 5 GB ổ đĩa trống cho giai đoạn đầu.

```powershell
py --version                                  # kiểm tra Python
py -3.11 -m venv .venv                        # tạo môi trường ảo
.\.venv\Scripts\Activate.ps1                  # kích hoạt (dòng lệnh sẽ có tiền tố (.venv))
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .                              # cài gói vietweb ở chế độ phát triển
$env:PYTHONUTF8 = "1"                         # in tiếng Việt đúng trên console
```

- Nếu `Activate.ps1` báo lỗi *running scripts is disabled*, chạy một lần: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, rồi kích hoạt lại.
- Mỗi lần mở PowerShell mới: `cd` vào thư mục repo, chạy `.\.venv\Scripts\Activate.ps1` và `$env:PYTHONUTF8 = "1"`.
- Nên dùng Git ngay từ đầu: `git init`, `git add .`, `git commit -m "Khung code ban dau"`. Thư mục `data/` đã nằm trong `.gitignore`.

## 2. Kiểm tra cài đặt

```powershell
pytest -q
```

Kết quả mong đợi: `23 passed`. Các test chạy hoàn toàn offline:
- `test_text.py`: chuẩn hóa NFC, dấu thanh (hoà → hòa, giữ nguyên quý / hoàn), phát hiện TCVN3, tách âm tiết.
- `test_stages.py`: nhận diện ngôn ngữ, khử trùng lặp chính xác / gần đúng / cấp dòng, luật chất lượng, che PII.
- `test_collect_http.py`: giả lập máy chủ Common Crawl để kiểm tra lệnh `collect`, kể cả thử lại và không tải trùng.
- `test_end_to_end.py`: chạy toàn bộ pipeline trên file WET giả lập.
- `test_rule_stats.py`: kiểm tra script thống kê từng luật (`scripts/rule_stats.py`).
- `test_boilerplate.py`: tầng 3b bỏ menu, footer, giữ đoạn nội dung; các bước phân loại của jusText; phương án `c4_lines`.
- `test_reference.py`: giả lập máy chủ có file WARC để kiểm tra lệnh `reference` (trafilatura) và `extract-eval`. Cần `trafilatura` (đã có trong `requirements.txt`); thiếu thì test này bị bỏ qua.

Nếu có test lỗi, dừng lại và xử lý trước khi tải dữ liệu thật.

## 3. Chạy thử trên dữ liệu giả lập

```powershell
python scripts\make_sample_wet.py data\sample\sample.warc.wet.gz
python -m vietweb collect-local data\sample\sample.warc.wet.gz --crawl SAMPLE
python -m vietweb run --crawl SAMPLE
```

File giả lập có 12 bản ghi, mỗi bản ghi thử một tầng. Funnel mong đợi:

```
      stage  docs_in  removed  docs_out  pct_of_input            top_reason
      input       10        0        10         100.0
  normalize       10        0        10         100.0
boilerplate       10        2         8          80.0 boilerplate_too_short   <- danh sách sản phẩm, văn bản TCVN3 lỗi mã
     langid        8        0         8          80.0
 url_filter        8        1         7          70.0         spam_keywords   <- trang cờ bạc
dedup_exact        7        2         5          50.0       exact_duplicate   <- trang sao chép; bản dấu kiểu mới (sau khi bỏ dòng ghi chú cuối)
 dedup_near        5        1         4          40.0        near_duplicate   <- bản sửa vài chữ
 dedup_line        4        0         4          40.0
    quality        4        0         4          40.0
        pii        4        0         4          40.0                         <- số điện thoại, email bị che
```

(Chỉ có 10 đầu vào vì bản ghi tiếng Anh bị lọc sơ bộ theo CLD2 và bản ghi menu dưới 200 ký tự bị bỏ khi thu thập.)

Xem thử kết quả:

```powershell
python -m vietweb status
python -m vietweb peek --reason near_duplicate -n 2
python -m vietweb peek --kept -n 2
```

**Quan trọng:** xóa dữ liệu giả lập trước khi chạy dữ liệu thật, để lệnh `run` không trộn chúng vào:

```powershell
Remove-Item -Recurse -Force data\raw\SAMPLE, data\processed, outputs
```

## 4. Thu thập dữ liệu thật (bước chạy đầu tiên với Common Crawl)

**4.1. Tải danh sách file WET** của bản crawl trong `configs/pipeline.yaml` (mặc định CC-MAIN-2026-39):

```powershell
python -m vietweb paths
```

Mong đợi: khoảng 100.000 file WET.

**4.2. Tải 1 file trước** để đo tốc độ mạng và kiểm tra mọi thứ chạy đúng:

```powershell
python -m vietweb collect --n-files 1
python -m vietweb status
```

- Mỗi file WET khoảng 60 MB (nén). File được tải vào `data\tmp`, đọc xong thì xóa.
- Chỉ giữ bản ghi có trường `WARC-Identified-Content-Language` chứa `vie`. Theo thống kê của Common Crawl, tiếng Việt chiếm khoảng 1% số trang, nên một file thường cho khoảng 200 bản ghi (ước tính, mỗi file sẽ khác nhau).
- `status` in tỉ lệ bản ghi tiếng Việt trên tổng số. Hãy ghi lại con số này cho báo cáo (Bảng 2).

**4.3. Tăng lên 10 file:**

```powershell
python -m vietweb collect --n-files 10
```

- Các file được chọn ngẫu nhiên với seed 42, nên file đã tải ở bước 4.2 nằm trong 10 file này và được bỏ qua.
- Bị ngắt giữa chừng thì cứ chạy lại lệnh: file nào đã xong (có trong `data\raw\<crawl>\_manifest.jsonl`) sẽ không tải lại.
- Máy chủ Common Crawl đôi khi trả lỗi 503 khi quá tải. Code tự thử lại với thời gian chờ tăng dần (5, 10, 20… giây). Nếu lỗi liên tục, tăng `collect.http.pause_between_files` trong cấu hình và thử lại sau.

## 5. Chạy pipeline và đọc kết quả

```powershell
python -m vietweb run --crawl CC-MAIN-2026-39
```

Đầu ra:

| File | Nội dung |
|---|---|
| `outputs\stats\funnel.csv` | Số tài liệu vào/ra, thời gian và lý do loại chính của từng tầng (Bảng 5, Hình 3) |
| `outputs\stats\filter_costs.csv` | Tỉ lệ qua và thời gian của từng luật chất lượng (RQ4) |
| `outputs\stats\quality_stats.parquet` | Giá trị mọi chỉ số chất lượng của từng tài liệu (để hiệu chỉnh ngưỡng, RQ1) |
| `outputs\stats\run_info.json` | Cấu hình chính của lần chạy |
| `data\processed\kept\` | Tài liệu giữ lại |
| `data\processed\dropped\` | Tài liệu bị loại, kèm `drop_stage` và `drop_reason` |

Việc cần làm ngay sau lần chạy đầu tiên:

1. **Xem tầng nào loại nhiều nhất:** `python -m vietweb status`.
2. **Đọc tài liệu bị loại theo từng lý do**, ví dụ:
   ```powershell
   python -m vietweb peek --reason gopher_mean_word_length -n 5
   python -m vietweb peek --reason langid_low_score -n 5
   ```
   Ngưỡng hiện tại là ngưỡng gốc cho tiếng Anh. Rất có thể có luật loại nhầm nhiều văn bản tiếng Việt tốt; ghi lại quan sát này, vì đó là dữ liệu cho RQ1.
3. **Vẽ hình:** `python scripts\plot_report_figures.py --out ..\report\figures`, rồi mở `fig_rule_hist.pdf` để xem phân phối từng chỉ số.
4. **Ghi số liệu từng luật:** `python scripts\rule_stats.py --out outputs\stats\rule_stats.md`, rồi cập nhật [LUAT_LOC.md](LUAT_LOC.md): danh mục mọi luật, ngưỡng, số liệu, nhật ký thay đổi ngưỡng và lịch sử lần chạy.
5. **Dashboard** (tùy chọn): `pip install streamlit`, rồi `streamlit run dashboard\app.py`.

Mỗi lần `run` ghi đè `outputs\` và `data\processed\`. Muốn giữ kết quả cũ để so sánh thì chép `outputs\stats` sang thư mục khác trước khi chạy lại (lệnh sao lưu có trong mục *Cách dùng* của [LUAT_LOC.md](LUAT_LOC.md)).

## 5b. Bỏ boilerplate (tầng 3b) và đối chiếu với WARC

File WET chứa toàn bộ chữ trên trang, kể cả menu, sidebar và footer. Vì vậy ở lần chạy 50 file, tầng 7 loại 74,9% số tài liệu, chủ yếu do ba luật FineWeb theo dòng (xem `LUAT_LOC.md`, mục 7.3).

Lệnh `run` giờ có thêm **tầng 3b (`boilerplate`)** ngay sau tầng chuẩn hóa:
- Từ 26/10/2026 tầng này dùng `method: c4_lines`: chỉ giữ dòng kết thúc bằng dấu câu và có ít nhất 5 âm tiết, bỏ dòng chứa "javascript". Phương pháp này được chọn vì có F1 cao nhất khi đối chiếu với trafilatura (`LUAT_LOC.md`, mục 3b).
- Trang còn dưới 200 ký tự sau khi bỏ boilerplate bị loại, với lý do `boilerplate_too_short`.
- Tham số nằm ở mục `boilerplate` trong `configs/pipeline.yaml`.
  - `method: none` tắt tầng này (chạy giống trước đây).
  - `method: justext` dùng thuật toán jusText: phân loại từng dòng theo độ dài, tỉ lệ từ dừng và các dòng xung quanh (phương pháp dùng trước 26/10/2026).
- Chi tiết các luật: `LUAT_LOC.md`, mục 3b.

### Bước 1. Chạy lại 50 file với tầng 3b

Mất khoảng 10 phút.

```powershell
pip install -r requirements.txt          # có thêm trafilatura cho bước 2
python -m vietweb run --crawl CC-MAIN-2026-39
python scripts\rule_stats.py --out outputs\stats\rule_stats.md
$name = "wet_50_bp"                      # mỗi lần chạy một tên mới (ví dụ wet_50_c4); không dùng lại tên đã có
Copy-Item -Recurse outputs\stats "outputs\runs\$name"
Copy-Item -Recurse data\processed "outputs\runs\$name\processed"
```

Hai lệnh `Copy-Item` chỉ sao lưu kết quả của lần `run` vừa xong. Chạy chúng sau mỗi lần `run`; chỉ sửa `pipeline.yaml` thì không cần. Nếu thư mục đích đã có, PowerShell chép `stats` vào bên trong thư mục đó thay vì ghi đè, nên kết quả hai lần chạy sẽ lẫn vào nhau.

Kết quả chạy thử trên đúng 50 file này. Trên máy bạn, số tài liệu sẽ giống, chỉ thời gian chạy khác.

| | `wet_50` (chưa có 3b) | `wet_50_bp` (có 3b) |
|---|---:|---:|
| Tài liệu giữ lại | 2.300 (18,7%) | 5.125 (41,7%) |
| Tổng số ký tự giữ lại | 22,4 triệu (còn lẫn menu) | 25,4 triệu |
| Bị tầng 3b loại | — | 4.507, trong đó 1.358 trang có ngôn ngữ chính không phải tiếng Việt |
| Bị tầng nhận diện ngôn ngữ loại | 1.883 | 7 |
| Tầng 7 loại (% số tài liệu vào tầng) | 74,9% | 26,0% |
| Trượt `fineweb_short_lines` / `line_punct` / `dup_line_chars` | 58,6% / 48,6% / 46,8% | 11,7% / 10,0% / 8,5% |

Lưu ý khi đọc kết quả:
- **Tầng 3b gánh luôn phần lớn việc lọc ngôn ngữ.** Cách phân loại dựa trên từ dừng tiếng Việt, nên trang tiếng Anh hay tiếng Trung mất gần hết các dòng ở tầng này. Khi viết funnel trong báo cáo, dùng số `too_short_cld2_not_vie` trong cột `details` của `funnel.csv` để tách hai loại trang.
- **Có tài liệu tốt bị mất.** 245 tài liệu được giữ ở `wet_50` nay bị loại, trong đó 127 tài liệu do tầng 3b. Xem các trang bị loại bằng:
  ```powershell
  python -m vietweb peek --reason boilerplate_too_short -n 5
  ```

### Bước 2. Tạo bản tham chiếu từ WARC

Bước này cần mạng.

```powershell
python -m vietweb reference --n-files 3
```

- **Lệnh làm gì:**
  - Lấy 3 file đầu (theo tên) trong 50 file đã thu thập và tải file WARC tương ứng. Mỗi file WARC khoảng 1 GB; ước tính mất 2–3 phút mỗi file theo tốc độ lần tải WET vừa rồi.
  - Tìm HTML của các bản ghi tiếng Việt, rồi trích văn bản chính bằng trafilatura. Cấu hình trích giống FineWeb (datatrove): `favor_precision=True`, `include_comments=False`, `deduplicate=True`.
- **Kết quả:** nằm trong `data\reference\CC-MAIN-2026-39\`. File WARC bị xóa sau khi xử lý; thêm `--keep-warc` nếu muốn giữ.
- **Cách ghép bản ghi:** dữ liệu đã thu thập được ghép với WARC theo URL. Từ bản này, `collect` lưu thêm cột `warc_refers_to` để ghép theo ID bản ghi.
- **Muốn thêm dữ liệu:** dùng `--n-files 5`. File đã xong không bị tải lại.

### Bước 3. So sánh tầng 3b với trafilatura

```powershell
python -m vietweb extract-eval
```

Kết quả nằm trong `outputs\eval\`. Đọc `extraction_eval.md` trước; số liệu đầy đủ ở `extraction_grid.csv` và `extraction_quality.csv`.

1. **Bảng độ khớp theo dòng.**
   - Một dòng WET được coi là nội dung nếu nó cũng có trong văn bản trafilatura. Precision và recall được tính theo số ký tự.
   - Bảng có 26 cấu hình: 24 tổ hợp tham số jusText, cộng `c4_lines`, cộng `none` (giữ hết). Dòng `none` cho biết tỉ lệ nội dung thật trong WET.
2. **Bảng luật chất lượng.** Cho biết tỉ lệ trượt từng luật trên ba phiên bản của cùng các trang: WET thô, WET sau tầng 3b, và văn bản trafilatura. WET sau 3b càng gần trafilatura thì ngưỡng hiệu chỉnh trên dữ liệu đã qua 3b càng đáng tin.

**Chọn tham số:**
- Lấy cấu hình có F1 cao nhất, hoặc ưu tiên precision nếu cần dữ liệu sạch hơn.
- Sửa 4 tham số `length_high`, `stopwords_high`, `stopwords_low`, `method` trong `configs/pipeline.yaml`.
- Ghi thay đổi vào `LUAT_LOC.md` (mục 10), rồi chạy lại bước 1.

**Giới hạn:** trafilatura là bản tham chiếu, không phải nhãn đúng tuyệt đối. Với `favor_precision`, trafilatura có thể bỏ sót một phần nội dung. Cần ghi rõ điều này trong báo cáo.

Xong mục này mới hiệu chỉnh ngưỡng tầng 7 và tăng lên 200 file (tuần 6–7).

## 5c. Hiệu chỉnh ngưỡng tầng 7 (RQ1)

Làm trên lần chạy 200 file (`wet_200`). Script `scripts\calibration_sample.py` lấy các trang nằm sát ngưỡng của 5 luật có ảnh hưởng nhất. Ở `wet_200`, ba luật đầu là luật duy nhất làm trượt lần lượt 757 / 1.009 / 98 trang:

- `gopher_word_count` (< 50 âm tiết)
- `fineweb_dup_line_chars` (≥ 0,1)
- `gopher_mean_word_length` (< 3)
- `gopher_top_4gram` (> 0,16)
- `gopher_stopwords` (< 2)

Các luật còn lại gần như không loại trang nào sau tầng 3b, nên không cần hiệu chỉnh.

Với mỗi luật, script lấy 20 trang chỉ bị luật đó loại (trong 150 trang gần ngưỡng nhất) và 20 trang được giữ gần ngưỡng nhất. 150 file đầu (theo thứ tự thu thập) dùng để chọn ngưỡng; 50 file sau để kiểm tra.

### Bước 1. Tạo file gán nhãn

```powershell
python scripts\calibration_sample.py
```

Kết quả: `outputs\eval\calibration_dev.csv` (200 trang) và `calibration_dev_key.csv`. File key ghi luật, phía ngưỡng và giá trị của từng trang. **Không mở file key khi đang gán nhãn**, để nhãn không bị ảnh hưởng.

### Bước 2. Gán nhãn

Mở `calibration_dev.csv` bằng Excel và điền cột `label` cho từng dòng:
- `1`: kém chất lượng, nên loại. Ví dụ: danh sách sản phẩm và giá, menu, bảng số, chuỗi giao diện website, spam, văn bản vô nghĩa hoặc dịch máy.
- `0`: chấp nhận được.
- Khi phân vân, tự hỏi: *nếu bỏ trang này, tập dữ liệu có mất một đoạn văn tiếng Việt có ích không?* Có thì điền 0, không thì điền 1.
- Cột `note` để ghi chú tùy ý. Bỏ trống `label` nếu không quyết được; dòng trống không được tính.

Khi lưu, chọn **CSV UTF-8 (Comma delimited)**. Lưu kiểu CSV thường sẽ làm hỏng chữ tiếng Việt.

Mất khoảng 1,5–2 giờ (khoảng 30 giây mỗi trang). Nếu có người thứ hai, nên để người đó gán nhãn trên một bản sao riêng để tính κ.

### Bước 3. Tính điểm và chọn ngưỡng

```powershell
python scripts\calibration_sample.py --score outputs\eval\calibration_dev.csv
```

Với mỗi luật, lệnh in ra:
- `share poor` phía bị loại: precision của việc loại gần ngưỡng.
- `share poor` phía được giữ: tỉ lệ rác còn sót gần ngưỡng.
- Một bảng các ngưỡng thử, mỗi ngưỡng có: số trang có nhãn bị loại, precision, số trang tốt bị loại, số trang kém được giữ, và số trang cả lần chạy sẽ bị loại.

Chọn ngưỡng:
- Nếu precision phía bị loại dưới mục tiêu (ví dụ 0,9), nới ngưỡng ra.
- Nếu phía được giữ còn nhiều trang kém, siết ngưỡng lại.
- Precision chỉ đo trên dải sát ngưỡng và hai phía được lấy mẫu bằng nhau, nên chỉ dùng làm định hướng. Không coi đó là precision trên toàn bộ dữ liệu.

### Bước 4. Áp dụng và kiểm tra

1. Sửa `configs\vie_thresholds.yaml` và ghi lý do vào `LUAT_LOC.md` (mục 10).
2. Chạy lại `run`, rồi sao lưu với `$name = "wet_200_cal"` (mục 5b, bước 1).
3. Kiểm tra một lần trên 50 file còn lại:
   ```powershell
   python scripts\calibration_sample.py --split test
   python scripts\calibration_sample.py --score outputs\eval\calibration_test.csv
   ```
   Số liệu trên tập test này là số đưa vào báo cáo.
4. Sau đó chạy `python -m vietweb order-filters` (RQ4), vì thứ tự tối ưu phụ thuộc vào tỉ lệ qua của từng luật sau khi đã đổi ngưỡng.

## 6. Lịch công việc theo tuần

| Tuần | Việc | Lệnh / file liên quan |
|---|---|---|
| 1–2 | Mục 1–5 ở trên; đọc paper | `collect --n-files 10`, `run` |
| 3–5 | Tăng lên 50 file; **bỏ boilerplate (tầng 3b) và đối chiếu với WARC + trafilatura (mục 5b)**; đọc tài liệu bị loại theo từng lý do; bổ sung từ dừng, từ khóa spam | `collect --n-files 50`, `reference`, `extract-eval`, `peek`, `configs/*.txt` |
| 6–7 | Tăng lên 200 file; vẽ phân phối chỉ số **trên văn bản đã qua tầng 3b**, đề xuất ngưỡng tiếng Việt; chạy `order-filters`; **báo cáo giữa kỳ** | `plot_report_figures.py`, `configs/vie_thresholds.yaml`, `order-filters` |
| 8–10 | Chuyển sang GlotLID; chuyển đổi TCVN3/VNI (`text/normalize.py: convert_legacy`); đơn vị `word` (underthesea); danh sách chặn UT1; Spark trong WSL2; mở rộng 1.000+ file | mục 7, mục 8 |
| 11–12 | Gán nhãn và đánh giá; so sánh đơn vị shingle; đối chiếu FineWeb-2 (`eval/fineweb2.py`); đo thời gian thật với `save_stats: false` | `sample-labels`, `score-labels`, `dedup-eval` |
| 13–15 | Dashboard, dataset card (`docs/dataset_card.md`), điền báo cáo | `report/CONTENTS.md` |

Lệnh cho tuần 11–12:

```powershell
python -m vietweb sample-labels --per-reason 150        # -> outputs\eval\labels_to_annotate.csv
# Hai người điền cột label_a, label_b: 1 = kém chất lượng, 0 = chấp nhận được
python -m vietweb score-labels outputs\eval\labels_to_annotate.csv
python -m vietweb dedup-eval --n 3000 --units syllable:5,word:5,char:15
```

## 7. Cấu hình hay chỉnh (`configs/pipeline.yaml`)

| Mục | Ý nghĩa | Khi nào đổi |
|---|---|---|
| `stages` | Thứ tự các tầng | Thử nghiệm thứ tự tầng |
| `boilerplate.method`, `length_high`, `stopwords_low`, `stopwords_high` | Tầng 3b: phương pháp (`justext` / `c4_lines` / `none`) và tham số | Sau khi chạy `extract-eval` (mục 5b) |
| `boilerplate.c4_drop_ellipsis` | Tầng 3b, phương pháp `c4_lines`: bỏ cả dòng kết thúc bằng "..." hoặc "…" | Muốn giữ đúng luật gốc của C4 thì đặt `false` |
| `dedup.line.min_domains` | Tầng 6: xóa dòng xuất hiện trên từ chừng này tên miền trở lên (0 = tắt) | Khi tăng số file: xem `cross_site_top` trong cột `details` của `funnel.csv` để chắc các dòng bị xóa đều là boilerplate |
| `langid.backend` | `heuristic` (mặc định, không cần mô hình) / `fasttext` / `glotlid` | Tuần 8–10 chuyển sang `glotlid` |
| `quality.unit` | Đếm "từ" theo `syllable` hay `word` | RQ1 (`word` cần `pip install underthesea`, chậm hơn nhiều) |
| `dedup.near.unit`, `ngram` | Đơn vị shingle cho MinHash | RQ1 (ví dụ `char` với `ngram: 15`) |
| `quality.rule_order` | Thứ tự luật chất lượng | Dán kết quả của `order-filters` (RQ4) |
| `quality.save_stats` | `true`: tính mọi chỉ số; `false`: dừng ở luật đầu tiên vi phạm | `false` khi đo thời gian thật cho Bảng 8 |
| `normalize.legacy_encoding_action` | `flag` hoặc `drop` văn bản TCVN3/VNI | Sau khi có bộ chuyển đổi |

**Nhận diện ngôn ngữ bằng mô hình (tuần 8–10):**

```powershell
pip install fasttext-wheel huggingface_hub
python -c "from huggingface_hub import hf_hub_download; print(hf_hub_download('cis-lmu/glotlid', 'model.bin', local_dir='models'))"
```

Sau đó đặt `langid.backend: glotlid` và `langid.model_path: models/model.bin`. Muốn dùng fastText lid.176 thì tải `https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.bin` vào `models\` và đặt `backend: fasttext`.

## 8. Chuyển sang Spark (tuần 8–10)

Bản hiện tại xử lý trong bộ nhớ bằng pandas, đủ cho vài chục nghìn tài liệu. Khi lên 1.000+ file (khoảng 200–400 nghìn tài liệu), `run` có thể thiếu RAM; tạm thời dùng `--limit` hoặc chạy từng `--crawl`.

PySpark trên Windows cần Java và winutils, rất dễ lỗi. Cách ít rắc rối nhất là chạy trong WSL2:

```powershell
wsl --install -d Ubuntu      # một lần, cần khởi động lại máy
```

Trong Ubuntu (WSL):

```bash
sudo apt update && sudo apt install -y openjdk-17-jre-headless python3-venv
cd /mnt/e/Dien/Saudh/uit/mon_hoc/data_processing/Project/vietweb
python3 -m venv .venv-wsl && source .venv-wsl/bin/activate
pip install -r requirements.txt pyspark && pip install -e .
python -c "from vietweb.spark_runner import run_per_doc_stages_spark; run_per_doc_stages_spark()"
```

`spark_runner.py` là khung **chưa kiểm thử**: đã có phần chạy các tầng theo từng tài liệu bằng `mapInPandas`; phần khử trùng lặp trên Spark (groupBy sha1, banding MinHash) cần viết thêm.

## 9. Lỗi thường gặp

| Hiện tượng | Cách xử lý |
|---|---|
| `UnicodeEncodeError` hoặc chữ tiếng Việt bị lỗi trên console | `$env:PYTHONUTF8 = "1"` |
| Lỗi 403 / 503 / timeout khi `collect` | Code tự thử lại; nếu vẫn lỗi, chờ một lúc rồi chạy lại (file đã xong không tải lại) |
| `FileNotFoundError: No Parquet files found` | Chưa chạy `collect`, hoặc `--crawl` sai tên |
| `MemoryError` khi `run` | Dùng `--limit 20000` hoặc `--crawl`; về lâu dài chuyển sang Spark |
| Excel hiển thị sai tiếng Việt trong CSV | File đã ghi UTF-8 có BOM; nếu vẫn lỗi, mở bằng Data → From Text/CSV, chọn UTF-8 |
| Muốn chạy lại từ đầu | Xóa `data\raw\<crawl>`, `data\processed`, `outputs` |
| `ImportError: The reference command needs trafilatura` | `pip install -r requirements.txt` |
| `reference` báo `Not a Common Crawl WET path` | Dữ liệu lấy bằng `collect-local` không có file WARC; chỉ dùng với dữ liệu từ `collect` |
| Muốn chạy lại pipeline như trước khi có tầng 3b | Đặt `boilerplate.method: none` trong `configs/pipeline.yaml` |

## 10. Trạng thái khung code

| Thành phần | Trạng thái |
|---|---|
| Thu thập WET (thử lại, manifest, lọc sơ bộ CLD2) | Chạy được, có test |
| Chuẩn hóa NFC, ftfy, dấu thanh | Chạy được, có test |
| Phát hiện TCVN3/VNI | Bộ phát hiện đơn giản; **chuyển đổi chưa viết** (`convert_legacy`) |
| Bỏ boilerplate trên WET (tầng 3b: `c4_lines`, phương án jusText) | Chạy được, có test; đã chọn phương pháp bằng `extract-eval` trên 3 file WARC (26/10/2026); cần chạy lại 50 file |
| Bản tham chiếu WARC + trafilatura, so sánh với tầng 3b | Chạy được với máy chủ giả lập (có test); **chưa chạy với Common Crawl thật** |
| Nhận diện ngôn ngữ | `heuristic` chạy được; `fasttext`/`glotlid` đã viết, cần tải mô hình |
| Lọc URL / từ khóa | Chạy được; danh sách còn sơ sài |
| Khử trùng lặp chính xác, MinHash-LSH, cấp dòng | Chạy được trong bộ nhớ; bản Spark chưa viết |
| 17 luật chất lượng + đo chi phí từng luật | Chạy được; ngưỡng đang là ngưỡng gốc tiếng Anh |
| Che PII (email, IPv4, số điện thoại, CCCD) | Chạy được; cần đo tỉ lệ nhận nhầm |
| Funnel, xuất Parquet, kiểm tra đầu ra | Chạy được |
| Gợi ý thứ tự luật (RQ4) | Chạy được |
| Gán nhãn, precision, kappa, so sánh shingle | Chạy được |
| Đối chiếu FineWeb-2 | Hàm tính đồng thuận đã có; **phần tải dữ liệu chưa viết** |
| Dashboard Streamlit | Chạy được |
| Spark, Prefect | Khung, **chưa kiểm thử** |
