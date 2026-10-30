# Hướng dẫn tái lập kết quả `vietweb`

Lệnh dưới đây chạy trong PowerShell trên Windows, tại thư mục `vietweb` (thư mục chứa `pyproject.toml`). Trên Linux hoặc macOS, thay `\` trong đường dẫn bằng `/`.

Số liệu của từng lần chạy và từng thí nghiệm được tổng hợp trong [LUAT_LOC.md](LUAT_LOC.md). File kết quả gốc nằm trong `outputs/`: `outputs/runs/<lần chạy>/` cho các lần chạy pipeline, `outputs/eval/` cho các thí nghiệm.

## 1. Cài đặt

Yêu cầu: Python 3.10–3.12, khoảng 5 GB ổ đĩa trống cho 200 file WET và khoảng 15 GB cho 1.000 file.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
$env:PYTHONUTF8 = "1"                         # in tiếng Việt đúng trên console
```

- Nếu `Activate.ps1` báo lỗi *running scripts is disabled*, chạy một lần `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.
- Gói cho các thí nghiệm mở rộng nằm trong `requirements-extra.txt`:
  - `underthesea`: đếm theo từ;
  - `fasttext-wheel`, `huggingface_hub`: GlotLID, mô hình chất lượng, đọc FineWeb-2;
  - `pyspark`: bản chạy trên Spark (mục 5.7);
  - `streamlit`: ứng dụng demo (mục 6).
- Mô hình ngôn ngữ nhỏ (mục 5.9) cần thêm `torch` và `tokenizers`.

Kiểm tra cài đặt (chạy offline, vài giây):

```powershell
pytest -q
```

Kết quả mong đợi: 42 test đạt. `test_reference.py` bị bỏ qua nếu thiếu `trafilatura`.

## 2. Chạy thử trên dữ liệu giả lập

Không cần mạng. Dùng để kiểm tra cả pipeline chạy được trước khi tải dữ liệu thật.

```powershell
python scripts\make_sample_wet.py data\sample\sample.warc.wet.gz
python -m vietweb collect-local data\sample\sample.warc.wet.gz --crawl SAMPLE
python -m vietweb run --crawl SAMPLE
python -m vietweb status
```

File giả lập có 12 bản ghi, mỗi bản ghi thử một tầng. Bản ghi tiếng Anh bị lọc sơ bộ theo CLD2 và bản ghi menu dưới 200 ký tự bị bỏ khi thu thập, nên còn 10 đầu vào:

```
      stage  docs_in  removed  docs_out  pct_of_input            top_reason
      input       10        0        10         100.0
  normalize       10        0        10         100.0
boilerplate       10        2         8          80.0 boilerplate_too_short   <- danh sách sản phẩm, văn bản TCVN3 lỗi mã
     langid        8        0         8          80.0
 url_filter        8        1         7          70.0         spam_keywords   <- trang cờ bạc
dedup_exact        7        2         5          50.0       exact_duplicate   <- trang sao chép; bản dấu kiểu mới
 dedup_near        5        1         4          40.0        near_duplicate   <- bản sửa vài chữ
 dedup_line        4        0         4          40.0
    quality        4        0         4          40.0
        pii        4        0         4          40.0                         <- số điện thoại, email bị che
```

Xóa dữ liệu giả lập trước khi chạy dữ liệu thật, để lệnh `run` không trộn chúng vào:

```powershell
Remove-Item -Recurse -Force data\raw\SAMPLE, data\processed, outputs\stats
```

## 3. Thu thập dữ liệu

```powershell
python -m vietweb paths                                       # danh sách file WET của CC-MAIN-2026-39 (khoảng 100.000 file)
python -m vietweb collect --n-files 200                       # 200 file chọn ngẫu nhiên, seed 42
python -m vietweb collect --crawl CC-MAIN-2024-10 --n-files 50   # cho phần đối chiếu FineWeb-2
```

- Bản crawl mặc định và các tham số thu thập nằm ở mục `collect` của `configs/pipeline.yaml`.
- Mỗi file WET khoảng 60 MB (nén), được tải vào `data\tmp` và xóa sau khi đọc. Chỉ giữ bản ghi có trường `WARC-Identified-Content-Language` chứa `vie` và dài từ 200 ký tự. Dữ liệu thô nằm ở `data\raw\<bản crawl>\`.
- File được chọn bằng `random.sample` với seed 42, nên `collect --n-files 1000` chọn đúng 200 file trên cộng thêm 800 file.
- Bị ngắt giữa chừng thì chạy lại lệnh: file đã có trong `data\raw\<bản crawl>\_manifest.jsonl` không bị tải lại. Máy chủ Common Crawl đôi khi trả lỗi 503; code tự thử lại với thời gian chờ tăng dần.

## 4. Chạy pipeline và sao lưu kết quả

```powershell
python -m vietweb run --crawl CC-MAIN-2026-39
python scripts\rule_stats.py --out outputs\stats\rule_stats.md
```

| Đầu ra | Nội dung |
|---|---|
| `outputs\stats\funnel.csv` | Số tài liệu vào/ra, thời gian và lý do loại chính của từng tầng |
| `outputs\stats\filter_costs.csv` | Tỉ lệ qua và thời gian của từng luật chất lượng |
| `outputs\stats\quality_stats.parquet` | Giá trị mọi chỉ số chất lượng của từng tài liệu (khi `quality.save_stats: true`) |
| `outputs\stats\run_info.json` | Cấu hình chính của lần chạy |
| `outputs\stats\rule_stats.md` | Funnel và thống kê từng luật dạng bảng |
| `data\processed\kept\`, `data\processed\dropped\` | Tài liệu giữ lại; tài liệu bị loại kèm `drop_stage`, `drop_reason` |

Lệnh `run` ghi đè `outputs\stats` và `data\processed`. Sao lưu sau mỗi lần chạy, mỗi lần một tên mới (nếu thư mục đích đã có, `Copy-Item` chép lồng vào bên trong thay vì ghi đè):

```powershell
$name = "wet_200_final"
Copy-Item -Recurse outputs\stats "outputs\runs\$name"
Copy-Item -Recurse data\processed "outputs\runs\$name\processed"
```

Các lần chạy dùng trong báo cáo:

| Lần chạy | Dữ liệu | Cấu hình |
|---|---|---|
| `wet_200_final` | 200 file CC-MAIN-2026-39 | `configs/` hiện tại. Số tiến trình không làm đổi kết quả |
| `wet_1000` | 1.000 file CC-MAIN-2026-39 (`collect --n-files 1000`) | `configs/` hiện tại: `parallel.workers: 8`, `memory.batch_files: 50` |
| `wet_2024_10_50` | 50 file CC-MAIN-2024-10 | `configs/` hiện tại; chạy với `run --crawl CC-MAIN-2024-10` |

- Kiểm tra một lần chạy lại cho đúng kết quả cũ: `python scripts\compare_runs.py outputs\runs\wet_200_final\processed data\processed` phải in `IDENTICAL`.
- Các lần chạy trung gian (`baseline_wet_10`, `wet_50`, `wet_50_bp`, `wet_50_c4`, `wet_200`, `wet_200_cal`) dùng cấu hình trước khi hiệu chỉnh. Khác biệt cấu hình của từng lần ghi ở `LUAT_LOC.md`, mục 10 và 11; muốn chạy lại thì đặt lại các khóa đó trong `configs/pipeline.yaml` và `configs/vie_thresholds.yaml`.

Xem nhanh kết quả của lần chạy gần nhất:

```powershell
python -m vietweb status                                  # funnel
python -m vietweb peek --reason gopher_word_count -n 5    # tài liệu bị loại theo một lý do
python -m vietweb peek --kept -n 2                        # tài liệu giữ lại
```

## 5. Tái lập từng kết quả

| Kết quả | Mục | File kết quả |
|---|---|---|
| Phễu xử lý 200 và 1.000 file | 4 | `outputs/runs/wet_200_final/`, `outputs/runs/wet_1000/` |
| Chọn phương pháp bỏ boilerplate | 5.1 | `outputs/eval/extraction_eval.md`, `extraction_grid.csv`, `extraction_quality.csv` |
| Hiệu chỉnh ngưỡng tầng 7 | 5.2 | `outputs/eval/calibration_*.csv` |
| Đếm theo âm tiết hay theo từ | 5.3 | `outputs/eval/word_unit_eval.md`, `word_unit_scores.csv` |
| Đơn vị shingle cho MinHash-LSH | 5.4 | `outputs/eval/dedup_units.csv` |
| Mức trùng lặp theo số file | 5.4 | `outputs/eval/dedup_stats_wet_200_final.md`, `dedup_stats_wet_1000.md` |
| Đối chiếu FineWeb-2, thông tin cá nhân còn lại | 5.5 | `outputs/eval/fineweb2_CC-MAIN-2024-10.md`, `fineweb2_pii_vie_Latn.md` |
| Thứ tự luật theo chi phí | 5.6 | in ra màn hình (số liệu ở `LUAT_LOC.md`, mục 7.5) |
| Chạy song song, bản Spark | 5.7 | `outputs/eval/parallel_bench.csv`, `data/spark_out/spark_runs.csv` |
| GlotLID, bảng mã TCVN3/VNI | 5.8 | `outputs/eval/langid_compare.md`, `legacy_eval.md`, `legacy_scan.md` |
| Mô hình chất lượng, rò rỉ VMLU, mô hình ngôn ngữ nhỏ | 5.9 | `outputs/eval/quality_model.md`, `benchmark_overlap_vmlu.md`, `lm_ablation.md` |
| Hình trong báo cáo | 5.10 | `../report/figures/` |

### 5.1. Chọn phương pháp bỏ boilerplate (tầng 3b)

Văn bản tham chiếu là văn bản chính trích từ file WARC bằng trafilatura, với cấu hình của FineWeb (datatrove): `favor_precision=True`, `include_comments=False`, `deduplicate=True`. Cần mạng.

```powershell
python -m vietweb reference --n-files 3
python -m vietweb extract-eval
```

- `reference` lấy 3 file đầu (theo tên) trong số file đã thu thập, tải file WARC tương ứng (khoảng 1 GB mỗi file), trích văn bản các bản ghi tiếng Việt rồi xóa file WARC (`--keep-warc` để giữ). Kết quả ở `data\reference\<bản crawl>\`. Bản ghi được ghép theo `warc_refers_to`, hoặc theo URL nếu thiếu cột này.
- `extract-eval` chấm 26 cấu hình: 24 tổ hợp tham số jusText, luật dòng C4 (`c4_lines`) và giữ nguyên (`none`).
  - Một dòng WET là nội dung nếu nó (khi dài từ 30 ký tự) là chuỗi con của văn bản tham chiếu, hoặc (khi ngắn hơn) trùng một dòng của văn bản tham chiếu.
  - Precision và recall tính theo số ký tự.
  - Bảng thứ hai cho tỉ lệ trượt từng luật tầng 7 trên WET thô, WET sau tầng 3b và văn bản trafilatura.
- Phương pháp và tham số của tầng 3b nằm ở mục `boilerplate` trong `configs/pipeline.yaml` (`method: c4_lines`, `c4_min_words: 5`, `c4_drop_ellipsis: true`, `min_chars_after: 200`). `method: justext` và `method: none` cho hai phương án còn lại.

### 5.2. Hiệu chỉnh ngưỡng tầng 7

Lấy mẫu trên lần chạy `wet_200`, tức 200 file với ngưỡng gốc của `gopher_word_count` (50), `gopher_stopwords` (2) và `fineweb_dup_line_chars` (0,1). Script đọc lần chạy gần nhất (`outputs\stats\quality_stats.parquet`, `data\processed`), nên chạy ngay sau `run` với các ngưỡng đó.

```powershell
python scripts\calibration_sample.py                                   # tập dev (150 file đầu)
python scripts\calibration_sample.py --score outputs\eval\calibration_dev.csv
python scripts\calibration_sample.py --tag r2 --band 600 --n 30 --bounds fineweb_dup_line_chars:max:fail,gopher_word_count:min:pass
python scripts\calibration_sample.py --score outputs\eval\calibration_dev.csv outputs\eval\calibration_dev_r2.csv
python scripts\calibration_sample.py --split test                      # tập test (50 file sau), sau khi đổi ngưỡng
python scripts\calibration_sample.py --score outputs\eval\calibration_test.csv
```

- Với mỗi luật, script lấy 20 trang trong 150 trang gần ngưỡng nhất ở hai nhóm: trang chỉ bị luật đó loại, và trang qua mọi luật. Tập dev và tập test chia theo thứ tự file trong `_manifest.jsonl`. Trang đã có trong vòng trước được bỏ qua.
- File gán nhãn (`calibration_dev.csv`, `calibration_dev_r2.csv`, `calibration_test.csv`) chứa URL, văn bản và cột `label`; file `*_key.csv` ghi luật, phía ngưỡng và giá trị chỉ số của từng trang. Nhãn được gán khi chưa mở file key.
- Hướng dẫn gán nhãn (cột `label`; dòng để trống không được tính):
  - `1`: kém chất lượng, nên loại: danh sách sản phẩm và giá, menu, bảng số, chuỗi giao diện website, spam, văn bản vô nghĩa hoặc dịch máy.
  - `0`: chấp nhận được.
  - Trang lẫn (vừa có đoạn văn có ích, vừa có nhiều bảng giá, danh sách, menu): `0` nếu phần văn bản có ích chiếm khoảng một nửa trở lên, ngược lại `1`. Nhãn là quyết định giữ hay bỏ cả trang.
  - Trang quảng cáo sản phẩm chấm theo chất lượng văn bản: viết thành đoạn văn có thông tin thì `0`; chủ yếu là tên sản phẩm, giá, "Mua ngay", thông số rời rạc, nhồi từ khóa thì `1`; cờ bạc hoặc quảng cáo kiểu "khỏi bệnh 100%" thì `1`.
  - Chỉ chấm theo 2.000 ký tự đầu hiện trong file.
- Lưu file bằng **CSV UTF-8**; lưu kiểu CSV thường làm hỏng chữ tiếng Việt.
- Bảng điểm tính theo ngưỡng đang có trong `configs/vie_thresholds.yaml`. Đổi ngưỡng rồi chấm lại không cần chạy lại pipeline, vì giá trị chỉ số đã lưu trong `quality_stats.parquet`.
- Quy tắc dời ngưỡng: chỉ dời khi tỉ lệ trang kém trong nhóm trang đổi trạng thái đạt khoảng 0,8. Kết quả: `LUAT_LOC.md`, mục 7.4.

### 5.3. Đếm theo âm tiết hay theo từ

```powershell
pip install underthesea
python scripts\word_unit_eval.py --workers 0
```

Chạy trên mọi tài liệu vào tầng 7 của `outputs\runs\wet_200_final\processed` và trên 409 trang có nhãn. `--workers 0` dùng mọi lõi; tách từ bằng underthesea chậm hơn tách âm tiết khoảng 130 lần. Thêm `--n 3000` để chạy trên mẫu ngẫu nhiên.

### 5.4. Trùng lặp và đơn vị shingle

```powershell
python scripts\dedup_stats.py --run outputs\runs\wet_200_final --crawl CC-MAIN-2026-39
python scripts\dedup_stats.py --run outputs\runs\wet_1000 --crawl CC-MAIN-2026-39
python -m vietweb dedup-eval --n 3000 --units syllable:3,syllable:5,char:15 --processed-dir outputs\runs\wet_200_final\processed
```

- `dedup_stats.py`: funnel ba bước khử trùng lặp, tỉ lệ trùng trong cùng tên miền, và tỉ lệ trùng trên các tập con lồng nhau chọn ngẫu nhiên (5 lần). Trùng chính xác trên tập con được đếm lại chính xác từ `text_sha1`; trùng gần đúng trên tập con bị đếm thiếu vì tài liệu đại diện của cụm có thể nằm ngoài tập con.
- `dedup-eval`: với mỗi đơn vị shingle, so MinHash-LSH với Jaccard chính xác (≥ 0,75) trên mọi cặp của 3.000 tài liệu đã làm sạch, bỏ các tài liệu rỗng. Số cặp tăng theo bình phương số tài liệu: khoảng 30 phút, phần lớn cho `char:15`.

### 5.5. Đối chiếu với FineWeb-2

FineWeb-2 không có CC-MAIN-2026-39, nên phần này dùng 50 file CC-MAIN-2024-10 (lần chạy `wet_2024_10_50`, mục 4). Cần mạng và `huggingface_hub`.

```powershell
python -m vietweb fw2-urls --dump CC-MAIN-2024-10 --probe      # ước lượng dung lượng phải đọc
python -m vietweb fw2-urls --dump CC-MAIN-2024-10              # khoảng 0,52 GB, khoảng 3 giờ
python -m vietweb fw2-compare --dump CC-MAIN-2024-10
python -m vietweb fw2-pii --n 10000
```

- `fw2-urls` không tải cả file FineWeb-2 (`vie_Latn` khoảng 130 GB, `vie_Latn_removed` khoảng 178 GB) mà chỉ đọc qua mạng các cột `url`, `dump`, `file_path` (và lý do loại) rồi giữ các dòng của một bản crawl. Kết quả ở `data\fineweb2\CC-MAIN-2024-10\`; bị ngắt thì chạy lại, file đã xong không đọc lại. Bị lỗi 429 thì đăng nhập bằng `huggingface-cli login`.
- `fw2-compare` ghép theo URL với `outputs\runs\wet_2024_10_50` và ghi `outputs\eval\fineweb2_CC-MAIN-2024-10.md`: độ phủ, mức đồng thuận A và κ, bảng chéo quyết định, các trang hai bên bất đồng theo lý do loại, số trang tiếng Việt của FineWeb-2 trong cùng các file WARC mà bộ lọc sơ bộ CLD2 bỏ sót.
- `fw2-pii` đọc văn bản của 10.000 tài liệu `vie_Latn` rải trên 10 file và đếm các mẫu thông tin cá nhân của tầng 8.

### 5.6. Thứ tự luật theo chi phí

```powershell
python scripts\time_quality_order.py --repeats 5
```

Chạy ngay sau lần chạy `wet_200_final` (đọc `data\processed` và `outputs\stats`). Script chạy tầng 7 ở chế độ dừng tại luật vi phạm đầu tiên (`save_stats: false`), luân phiên thứ tự hiện tại và thứ tự sắp theo (1 − p)/c, in trung vị và kiểm tra tập tài liệu được giữ giống nhau. Script luôn chạy một tiến trình. Kết quả dao động khi máy đang chạy việc khác.

### 5.7. Chạy song song và chạy trên Spark

```powershell
python scripts\bench_parallel.py --n 10000 --workers 1 2 4 8 12
```

Đo tầng 3 (ftfy trên cả văn bản và ftfy theo dòng) và tầng 3b với số tiến trình khác nhau trên 10.000 tài liệu thô (seed 42) → `outputs\eval\parallel_bench.csv`. Số tiến trình của pipeline đặt ở `parallel.workers`; từ 1.000 file trở lên đặt `memory.batch_files: 50` để tầng 3–5 chạy theo từng nhóm 50 file thô.

Spark: PySpark trên Windows cần Java và winutils, nên chạy trong WSL2 (Ubuntu). Trong Ubuntu:

```bash
sudo apt update && sudo apt install -y openjdk-17-jre-headless python3-venv
cd /mnt/<ổ đĩa>/<đường dẫn tới>/vietweb
python3 -m venv .venv-wsl && source .venv-wsl/bin/activate
pip install -r requirements.txt pyspark==4.0.1
export PYTHONPATH=src
python -m vietweb.spark_runner --cores 8 --out data/spark_out
python scripts/compare_runs.py outputs/runs/wet_1000/processed data/spark_out     # mong đợi IDENTICAL (đã kiểm trên 55 file)
python -m vietweb.spark_runner --cores 1 2 4 8 --out data/spark_out            # thông lượng theo số lõi
```

- `spark_runner.py` chạy tầng 3–9 với kết quả giống `python -m vietweb run`: tầng theo từng tài liệu chạy bằng `mapInPandas`; trùng chính xác dùng cửa sổ theo SHA-1; trùng gần đúng tìm các dải MinHash có ở hơn một tài liệu rồi duyệt các tài liệu đó theo thứ tự như tầng 6.
- Kết quả ở `data/spark_out/` (`kept`, `dropped`, `funnel.csv`, `run_info.json`, `spark_runs.csv` với số giây từng pha và số tài liệu mỗi giây).
- Dùng Spark 4.0: Spark 3.5 lỗi ở `mapInPandas` khi chạy với Java 21. WSL mặc định dùng tối đa một nửa RAM; thiếu bộ nhớ thì thêm `--driver-memory 3g`.

### 5.8. GlotLID và bảng mã TCVN3/VNI

```powershell
pip install fasttext-wheel huggingface_hub
python scripts\langid_compare.py --download            # tải mô hình GlotLID (khoảng 1,6 GB) vào models\glotlid\
python scripts\langid_compare.py --workers 0
python scripts\legacy_eval.py --processed outputs\runs\wet_200_final\processed --n 2000
python scripts\legacy_scan.py --n-files 5
```

- `langid_compare.py` chạy tầng 3–3b trên dữ liệu thô của bản crawl trong cấu hình, rồi so heuristic với xác suất `vie_Latn` của GlotLID ở nhiều ngưỡng. Số trong báo cáo đo khi `data\raw\CC-MAIN-2026-39` có 200 file (37.456 tài liệu vào tầng 4).
- `legacy_eval.py`: thử tổng hợp (viết lại 2.000 tài liệu sạch bằng TCVN3 và VNI rồi cho tầng 3 khôi phục) và đếm số tài liệu thật được chuyển. `--skip-real` chỉ chạy phần tổng hợp.
- `legacy_scan.py`: tải 5 file WET khác (seed 7), đọc mọi bản ghi của mọi ngôn ngữ và đếm bản ghi mà tầng 3 sẽ chuyển.

### 5.9. Mô hình chất lượng, rò rỉ VMLU, mô hình ngôn ngữ nhỏ

```powershell
python scripts\quality_model.py --download             # tải các file Wikipedia tiếng Việt (bản 20231101) vào data\wikipedia
python scripts\quality_model.py
python scripts\benchmark_overlap.py data\benchmarks\vmlu --name VMLU --processed outputs\runs\wet_1000\processed
```

- `quality_model.py`: bộ phân loại fastText Wikipedia/web và mô hình trigram âm tiết, học trên 15.000 bài Wikipedia dài từ 1.000 ký tự (sau luật dòng của tầng 3b) và 15.000 tài liệu vào tầng 7; chấm trên các trang có nhãn của mục 5.2.
- VMLU: tải file zip ở https://vmlu.ai (mục Data), giải nén vào `data\benchmarks\vmlu`. Script so mọi trường văn bản của từng câu với tài liệu giữ lại theo dãy 13 và 8 âm tiết, sau khi chuẩn hóa hai phía như tầng 3.

Mô hình ngôn ngữ nhỏ (cần `torch`, `tokenizers`):

```powershell
python scripts\lm_ablation.py prepare --processed outputs\runs\wet_200_final\processed
python scripts\lm_ablation.py train --corpus raw   --seed 0 --preset cpu
python scripts\lm_ablation.py train --corpus clean --seed 0 --preset cpu
python scripts\lm_ablation.py train --corpus raw   --seed 1 --preset cpu
python scripts\lm_ablation.py train --corpus clean --seed 1 --preset cpu
python scripts\lm_ablation.py report
```

- `prepare` ghi vào `data\lm\`: kho "thô" (văn bản WET của mọi tài liệu vào lần chạy), kho "sạch" (tài liệu được giữ), một tokenizer BPE 16.000 từ vựng học trên lượng ký tự bằng nhau từ hai kho, và bốn tập đo: Wikipedia sau luật dòng 3b, Wikipedia nguyên văn, web sạch, web thô (500 nghìn token mỗi tập).
- Preset `cpu`: GPT 4 lớp, 256 chiều, 7,3 triệu tham số, ngữ cảnh 128 token, đúng 3 triệu token mỗi lần huấn luyện; khoảng 24 phút mỗi lần trên 2 lõi CPU. Bước `train` chỉ cần `torch` và `numpy`, nên chạy được trên Colab sau khi tải lên `data\lm` và file script.
- `report` ghi `outputs\eval\lm_ablation.md` và các file `lm_ablation_<kho>_s<seed>_cpu.csv/json`.

Một số số đo phụ trong `LUAT_LOC.md` được tính bằng lệnh tạm trên đầu ra của các script trên, chưa có script riêng:
- phân loại thô 437 trang mà GlotLID giữ còn heuristic loại (mục 14.3);
- số trang khớp từ khóa cờ bạc không dấu trên `wet_1000` (mục 14.3);
- tỉ lệ câu hỏi VMLU nằm trong trang khớp (mục 14.7);
- tỉ lệ trang kém theo phần tư điểm P(web) (mục 14.5).

### 5.10. Hình trong báo cáo

```powershell
python scripts\plot_results_figures.py --out ..\report\figures
python scripts\plot_results_figures.py --out ..\report\ieee\figures --column
```

Số liệu trong hình được chép từ `LUAT_LOC.md` (mục 7.4 và 14.6) vào đầu script. `--column` vẽ bản một cột cho bản báo cáo 5 trang.

## 6. Ứng dụng demo và dashboard

```powershell
pip install streamlit
streamlit run dashboard\demo.py
```

Trình duyệt mở `http://localhost:8501`. Ứng dụng không cần mạng và có bốn trang:

| Trang | Nội dung |
|---|---|
| Thử một trang | Chạy tầng 3, 3b, 4, 5, 7, 8 trên một trang bằng đúng mã của pipeline (`src/vietweb/explain.py`) và cấu hình `configs/pipeline.yaml`: dòng bị bỏ kèm lý do, điểm tiếng Việt, từ khóa spam, bảng 16 luật chất lượng, văn bản sau khi che thông tin cá nhân. Nguồn trang: 6 ví dụ có sẵn (mỗi ví dụ dừng ở một tầng khác nhau), một bản ghi WET thật lấy ngẫu nhiên trong `data/raw`, hoặc văn bản tự dán. |
| Trùng lặp gần đúng | MinHash-LSH trên hai văn bản với cấu hình tầng 6 (14 dải × 8 hàng): Jaccard thật, ước lượng MinHash, dải trùng, đường xác suất thành ứng viên. |
| Kết quả | Phễu 200 và 1.000 file, trùng lặp theo số file, tốc độ, bản Spark, và các file `outputs/eval/*.md`. |
| Duyệt dữ liệu | Tài liệu giữ lại và bị loại của một lần chạy (`outputs/runs/*/processed` hoặc `data/processed`). |

- Quyết định của trang "Thử một trang" khớp với chạy các tầng thật trên cùng văn bản: `pytest tests\test_explain.py`.
- Tầng 6 cần cả kho dữ liệu nên không có trong trang "Thử một trang"; trang này chỉ hiện khóa SHA-1 dùng cho trùng chính xác.
- Bản ghi WET thật có thể chứa số điện thoại hoặc email thật.
- `streamlit run dashboard\app.py` mở dashboard chỉ để duyệt kết quả của lần chạy gần nhất.

## 7. Cấu hình (`configs/pipeline.yaml`)

| Khóa | Ý nghĩa |
|---|---|
| `collect.crawl`, `seed` | Bản crawl mặc định; seed chọn file và lấy mẫu (42) |
| `stages` | Thứ tự các tầng |
| `normalize.legacy_encoding_action` | `convert`: chuyển TCVN3/VNI sang Unicode khi bản giải mã đọc được như tiếng Việt; `flag`: chỉ ghi điểm; `drop`: loại |
| `boilerplate.method` | Tầng 3b: `c4_lines` (đang dùng), `justext` hoặc `none` |
| `boilerplate.c4_drop_ellipsis` | `c4_lines`: bỏ cả dòng kết thúc bằng "..." hoặc "…"; `false` để giữ đúng luật gốc của C4 |
| `langid.backend`, `langid.model_path` | `heuristic` (đang dùng), `glotlid` (`models/glotlid/model.bin`) hoặc `fasttext` (lid.176) |
| `dedup.near.unit`, `dedup.near.ngram` | Đơn vị và độ dài shingle cho MinHash (đang dùng: âm tiết, 5) |
| `dedup.line.min_domains` | Xóa dòng xuất hiện trên từ chừng này tên miền trở lên (0 = tắt) |
| `quality.unit` | Đếm "từ" theo `syllable` (đang dùng) hoặc `word` (cần underthesea) |
| `quality.rule_order` | Thứ tự luật chất lượng |
| `quality.save_stats` | `true`: tính mọi chỉ số (cần cho mục 5.2); `false`: dừng ở luật vi phạm đầu tiên |
| `parallel.workers` | Số tiến trình cho các tầng xử lý từng tài liệu |
| `memory.batch_files` | Số file thô mỗi nhóm cho tầng 3–5 (0 = đọc tất cả một lần) |

Ngưỡng của 17 luật chất lượng nằm trong `configs/vie_thresholds.yaml`; từ dừng và danh sách chặn nằm trong `configs/*.txt`.

## 8. Lỗi thường gặp

| Hiện tượng | Cách xử lý |
|---|---|
| `UnicodeEncodeError` hoặc chữ tiếng Việt bị lỗi trên console | `$env:PYTHONUTF8 = "1"` |
| Lỗi 403 / 503 / timeout khi `collect` | Code tự thử lại; nếu vẫn lỗi, chạy lại lệnh sau (file đã xong không tải lại) |
| `FileNotFoundError: No Parquet files found` | Chưa chạy `collect`, hoặc `--crawl` sai tên |
| `MemoryError` khi `run` | Đặt `memory.batch_files`, dùng `--crawl` hoặc `--limit`, hoặc chạy bản Spark (mục 5.7) |
| Excel hiển thị sai tiếng Việt trong CSV | Mở bằng Data → From Text/CSV, chọn UTF-8 |
| `ImportError: The reference command needs trafilatura` | `pip install -r requirements.txt` |
| `reference` báo `Not a Common Crawl WET path` | Dữ liệu lấy bằng `collect-local` không có file WARC; chỉ dùng với dữ liệu từ `collect` |
| Chạy lại pipeline như khi chưa có tầng 3b | Đặt `boilerplate.method: none` |
