"""Demo app of the vietweb pipeline, for presentations.

Install: pip install streamlit
Run from the repository root: streamlit run dashboard/demo.py

Pages:
1. Thử một trang      runs stages 3, 3b, 4, 5, 7 and 8 on one page with the real stage code (src/vietweb/explain.py)
                      and shows every decision: removed lines, language score, spam keywords, quality rules, PII.
2. Trùng lặp gần đúng MinHash-LSH on two texts with the stage-6 settings (14 bands x 8 rows).
3. Kết quả            funnel, duplicate growth, speed and extended experiments, read from outputs/.
4. Duyệt dữ liệu      kept and removed documents of a finished run.
"""
from __future__ import annotations

import html
import math
import random
import re
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT / "src", ROOT / "dashboard"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from vietweb.config import load_config  # noqa: E402
from vietweb.explain import (candidate_probability, explain, first_drop, load_resources, minhash_pair,  # noqa: E402
                             text_sha1)
import demo_examples as ex  # noqa: E402

OUT = ROOT / "outputs"
RUNS = OUT / "runs"
EVAL = OUT / "eval"

STAGE_TITLE = {"normalize": "3 · Chuẩn hóa", "boilerplate": "3b · Bỏ boilerplate", "langid": "4 · Nhận diện ngôn ngữ",
               "url_filter": "5 · Lọc URL và spam", "quality": "7 · Lọc chất lượng", "pii": "8 · Che thông tin cá nhân"}
REASON_VI = {"boilerplate_too_short": "sau khi bỏ boilerplate còn quá ít chữ",
             "langid_low_score": "điểm tiếng Việt thấp hơn ngưỡng",
             "url_blocklist": "tên miền nằm trong danh sách chặn",
             "spam_keywords": "chứa nhiều từ khóa cờ bạc",
             "legacy_encoding": "viết bằng bảng mã cũ"}
LINE_REASON_VI = {"no_terminal_punct": "không kết thúc bằng dấu câu", "too_few_syllables": "dưới 5 âm tiết",
                  "javascript": "nhắc tới javascript", "ellipsis": "kết thúc bằng dấu ba chấm", "other": "khác",
                  "justext_bad": "jusText: xấu", "justext_short": "jusText: ngắn", "justext_neargood": "jusText: gần tốt"}
RULE_VI = {
    "c4_lorem_ipsum": "Có chữ “lorem ipsum”",
    "c4_curly_bracket": "Có dấu ngoặc nhọn “{”",
    "gopher_word_count": "Số âm tiết",
    "gopher_mean_word_length": "Độ dài trung bình của âm tiết (ký tự)",
    "gopher_symbol_ratio": "Tỉ lệ ký hiệu # và … trên số âm tiết",
    "gopher_bullet_lines": "Tỉ lệ dòng bắt đầu bằng gạch đầu dòng",
    "gopher_ellipsis_lines": "Tỉ lệ dòng kết thúc bằng dấu ba chấm",
    "gopher_alpha_words": "Tỉ lệ từ có chữ cái",
    "gopher_stopwords": "Số từ dừng khác nhau",
    "gopher_dup_lines": "Tỉ lệ dòng trùng nhau",
    "gopher_dup_paragraphs": "Tỉ lệ đoạn trùng nhau",
    "gopher_top_2gram": "Tỉ lệ ký tự của 2-gram nhiều nhất",
    "gopher_top_3gram": "Tỉ lệ ký tự của 3-gram nhiều nhất",
    "gopher_top_4gram": "Tỉ lệ ký tự của 4-gram nhiều nhất",
    "fineweb_line_punct": "Tỉ lệ dòng kết thúc bằng dấu câu",
    "fineweb_dup_line_chars": "Tỉ lệ ký tự thuộc dòng trùng",
    "fineweb_short_lines": "Tỉ lệ dòng ngắn (dưới 30 ký tự)",
}
PII_VI = {"email": "Email", "ipv4": "Địa chỉ IPv4", "phone_vn": "Số điện thoại", "cccd": "Dãy 12 chữ số (CCCD)"}

GREEN, RED, GREY = "#e6f4ea", "#fde8e6", "#f1f3f4"


# ----------------------------------------------------------------------------------------------- helpers
def vn(x: float, d: int = 0) -> str:
    """Vietnamese number format: 1.234,5"""
    s = f"{x:,.{d}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def num(x) -> str:
    x = float(x)
    return vn(x, 0) if x.is_integer() else str(round(x, 4)).replace(".", ",")


def keep_condition(rule: str, t: dict) -> str:
    if rule in ("c4_lorem_ipsum", "c4_curly_bracket"):
        return "không có"
    if "min" in t and "max" in t:
        return f"{num(t['min'])} – {num(t['max'])}"
    if rule == "fineweb_line_punct":
        return f"> {num(t['min'])}"
    if "min" in t:
        return f"≥ {num(t['min'])}"
    if rule in ("fineweb_dup_line_chars", "fineweb_short_lines"):
        return f"< {num(t['max'])}"
    return f"≤ {num(t['max'])}"


def pill(text: str, bg: str, fg: str = "#202124") -> str:
    return (f"<span style='background:{bg};color:{fg};padding:2px 10px;border-radius:12px;font-size:0.85em;"
            f"white-space:nowrap'>{html.escape(text)}</span>")


@st.cache_resource
def resources():
    cfg = load_config(ROOT / "configs" / "pipeline.yaml")
    cfg["_root"] = str(ROOT)
    return load_resources(cfg)


@st.cache_data
def raw_files() -> list[str]:
    return sorted(str(p) for p in (ROOT / "data" / "raw").glob("*/*.parquet"))


@st.cache_data
def read_parquet(path: str, columns: tuple[str, ...] | None = None) -> pd.DataFrame:
    return pd.read_parquet(path, columns=list(columns) if columns else None)


def read_text(path: Path) -> str | None:
    return path.read_text(encoding="utf-8") if path.exists() else None


# ------------------------------------------------------------------------------------- page 1: one page
def page_try():
    st.title("Thử pipeline trên một trang")
    st.caption("Ứng dụng gọi đúng mã của các tầng 3, 3b, 4, 5, 7 và 8 với cấu hình `configs/pipeline.yaml`. "
               "Tầng 6 (khử trùng lặp) cần cả kho dữ liệu nên được minh họa ở trang “Trùng lặp gần đúng”.")
    res = resources()

    source = st.radio("Nguồn trang", ["Ví dụ có sẵn", "Bản ghi WET thật (ngẫu nhiên)", "Tự dán văn bản"],
                      horizontal=True)
    url, text, key = "", "", source
    if source == "Ví dụ có sẵn":
        label = st.selectbox("Ví dụ", list(ex.EXAMPLES))
        url, text, note = ex.EXAMPLES[label]
        st.info(note)
        key = label
    elif source == "Bản ghi WET thật (ngẫu nhiên)":
        files = raw_files()
        if not files:
            st.warning("Không tìm thấy dữ liệu thô trong `data/raw/`. Chạy `python -m vietweb collect` trước.")
            return
        if st.button("Lấy bản ghi khác"):
            st.session_state["seed"] = st.session_state.get("seed", 0) + 1
        rng = random.Random(st.session_state.get("seed", 0))
        f = rng.choice(files)
        df = read_parquet(f, ("url", "snapshot", "cld2_langs", "text"))
        row = df.iloc[rng.randrange(len(df))]
        url, text = row["url"], row["text"]
        st.caption(f"{row['snapshot']} · CLD2: {row['cld2_langs']} · {Path(f).name}")
        key = f"raw{st.session_state.get('seed', 0)}"
    else:
        url = st.text_input("URL (không bắt buộc, dùng cho danh sách chặn tên miền)", "https://example.vn/bai-viet")

    url = st.text_input("URL", url, key=f"url_{key}") if source != "Tự dán văn bản" else url
    text = st.text_area("Văn bản đầu vào (sửa trực tiếp để thử)", text, height=260, key=f"text_{key}")
    if not text.strip():
        st.stop()

    views = explain(text, url, res)
    end = first_drop(views)
    if end is None:
        st.success(f"**Được giữ lại.** Văn bản cuối có {vn(len(views[-1].text_after))} ký tự "
                   f"(đầu vào {vn(len(text))} ký tự).")
    else:
        stage, reason = end
        why = REASON_VI.get(reason, f"vi phạm luật `{reason}`")
        st.error(f"**Bị loại ở tầng {STAGE_TITLE[stage]}:** {why}.")

    # one status pill per stage
    cells, dropped = [], False
    for v in views:
        if dropped:
            cells.append(pill(f"{STAGE_TITLE[v.key]}: không chạy", GREY, "#5f6368"))
        elif v.drop_reason:
            cells.append(pill(f"{STAGE_TITLE[v.key]}: loại", RED, "#a50e0e"))
            dropped = True
        else:
            cells.append(pill(f"{STAGE_TITLE[v.key]}: qua", GREEN, "#137333"))
    st.markdown(" → ".join(cells), unsafe_allow_html=True)
    st.caption(f"Khóa của tầng 6 (SHA-1 của văn bản viết thường): `{text_sha1(views[-1].text_after)[:16]}…` — "
               "hai trang có cùng khóa là bản sao chính xác.")

    expand_all = st.checkbox("Mở chi tiết tất cả các tầng")
    stop_at = STAGES_ORDER.index(end[0]) if end else len(STAGES_ORDER)
    for i, v in enumerate(views):
        after_drop = i > stop_at
        with st.expander(STAGE_TITLE[v.key] + (" (sau khi đã bị loại, chỉ để tham khảo)" if after_drop else ""),
                         expanded=expand_all or (not after_drop and notable(v)) or bool(end and v.key == end[0])):
            RENDER[v.key](v)


def notable(v) -> bool:
    """Open a stage's panel by default when it did something worth showing."""
    d = v.details
    return {"normalize": bool(d.get("encoding")), "boilerplate": True, "langid": False,
            "url_filter": bool(d.get("keyword_hits")) or d.get("domain_blocked", False),
            "quality": False, "pii": any(d.get("counts", {}).values())}[v.key]


def show_normalize(v):
    d = v.details
    c1, c2, c3 = st.columns(3)
    c1.metric("Ký tự vào → ra", f"{vn(d['chars_in'])} → {vn(d['chars_out'])}")
    c2.metric("Văn bản bị sửa", "có" if d["changed"] else "không")
    c3.metric("Bảng mã cũ", {"tcvn3": "TCVN3", "vni": "VNI"}.get(d["encoding"], "không"))
    st.caption("ftfy sửa lỗi mã hóa theo từng dòng, đưa về Unicode NFC và đặt dấu thanh kiểu cũ (thuỷ → thủy). "
               "Văn bản chỉ được chuyển từ TCVN3/VNI khi bản giải mã đọc được như tiếng Việt.")
    if d["encoding"]:
        a, b = st.columns(2)
        a.markdown("**Trước khi chuyển**")
        a.text(d["text_in"][:600])
        b.markdown("**Sau khi chuyển**")
        b.text(v.text_after[:600])


def show_boilerplate(v):
    d = v.details
    lines = d["lines"]
    kept = sum(r is None for _, r in lines)
    c1, c2, c3 = st.columns(3)
    c1.metric("Dòng giữ / tổng", f"{kept} / {len(lines)}")
    c2.metric("Ký tự còn lại", vn(d["chars_out"]), help=f"Trang bị loại nếu còn dưới {d['min_chars_after']} ký tự")
    share = 1 - d["chars_out"] / max(d["chars_in"], 1)
    c3.metric("Ký tự bị bỏ", f"{vn(100 * share, 1)}%")
    rows = []
    for ln, r in lines:
        txt = html.escape(ln)
        if r is None:
            rows.append(f"<div style='background:{GREEN};border-left:4px solid #34a853;padding:3px 8px;margin:2px 0'>"
                        f"{txt}</div>")
        else:
            rows.append(f"<div style='background:{RED};border-left:4px solid #ea4335;padding:3px 8px;margin:2px 0;"
                        f"color:#5f6368'><s>{txt}</s> &nbsp;{pill(LINE_REASON_VI.get(r, r), '#ffffff', '#a50e0e')}"
                        f"</div>")
    st.markdown("".join(rows[:400]), unsafe_allow_html=True)
    if len(rows) > 400:
        st.caption(f"Chỉ hiện 400 trên {len(rows)} dòng.")
    st.caption(f"Phương pháp: `{d['method']}` — giữ dòng kết thúc bằng dấu câu và có từ 5 âm tiết; bỏ dòng nhắc "
               "javascript hoặc kết thúc bằng dấu ba chấm.")


def show_langid(v):
    d = v.details
    c1, c2, c3 = st.columns(3)
    c1.metric("Điểm tiếng Việt", num(d["score"]), help=f"Ngưỡng giữ: {num(d['threshold'])}")
    c2.metric("Âm tiết có dấu", f"{vn(100 * d['diacritic_share'], 1)}%")
    c3.metric("Từ dừng", f"{vn(100 * d['stopword_share'], 1)}%")
    st.progress(min(max(float(d["score"]), 0.0), 1.0))
    if d["backend"] == "heuristic":
        st.caption("Điểm = 0,6 × min(1; tỉ lệ âm tiết có dấu / 0,5) + 0,4 × min(1; tỉ lệ từ dừng / 0,12). "
                   f"Trang bị loại khi điểm dưới {num(d['threshold'])}.")
    else:
        st.caption(f"Bộ nhận diện: {d['backend']}; điểm là xác suất của nhãn tiếng Việt.")


def show_url_filter(v):
    d = v.details
    c1, c2, c3 = st.columns(3)
    c1.metric("Tên miền", d["domain"] or "—")
    c2.metric("Trong danh sách chặn", "có" if d["domain_blocked"] else "không")
    c3.metric("Lần xuất hiện từ khóa", f"{sum(d['keyword_hits'].values())} (loại khi ≥ {d['min_hits']})")
    if d["keyword_hits"]:
        st.dataframe(pd.DataFrame({"Từ khóa": list(d["keyword_hits"]), "Số lần": list(d["keyword_hits"].values())}),
                     hide_index=True)


def show_quality(v):
    d = v.details
    rows = [{"Luật": r["rule"], "Ý nghĩa": RULE_VI.get(r["rule"], ""), "Giá trị": num(r["value"]),
             "Giữ khi": keep_condition(r["rule"], r["threshold"]), "Kết quả": "qua" if r["passed"] else "LOẠI"}
            for r in d["rules"]]
    df = pd.DataFrame(rows)
    st.dataframe(df.style.apply(lambda s: [f"background-color: {RED}" if x == "LOẠI" else "" for x in s],
                                subset=["Kết quả"]), hide_index=True, height=36 * (len(df) + 1) + 4)
    note = f"“Từ” được đếm theo {'âm tiết' if d['unit'] == 'syllable' else 'từ (underthesea)'}. "
    if d["disabled"]:
        note += "Luật đã tắt sau hiệu chỉnh: " + ", ".join(f"`{r}`" for r in d["disabled"]) + ". "
    note += "Pipeline thật dừng ở luật vi phạm đầu tiên theo thứ tự trong bảng."
    st.caption(note)


def show_pii(v):
    d = v.details
    cols = st.columns(len(d["counts"]) or 1)
    for c, (k, n) in zip(cols, d["counts"].items()):
        c.metric(PII_VI.get(k, k), n)
    st.markdown("**Văn bản cuối cùng**")
    st.text(v.text_after[:5000])


STAGES_ORDER = ["normalize", "boilerplate", "langid", "url_filter", "quality", "pii"]
RENDER = {"normalize": show_normalize, "boilerplate": show_boilerplate, "langid": show_langid,
          "url_filter": show_url_filter, "quality": show_quality, "pii": show_pii}


# --------------------------------------------------------------------------------- page 2: near duplicates
def page_minhash():
    st.title("Trùng lặp gần đúng với MinHash-LSH")
    st.caption("Cùng cấu hình với tầng 6: chữ ký 112 hàm băm chia thành 14 dải × 8 hàng. Hai văn bản trở thành "
               "cặp ứng viên khi trùng ít nhất một dải; khi đó văn bản đến sau bị loại.")
    preset = st.radio("Cặp văn bản", list(ex.PAIRS) + ["Tự nhập"], horizontal=True)
    a0, b0 = ex.PAIRS.get(preset, ("", ""))
    c1, c2 = st.columns(2)
    a = c1.text_area("Văn bản A", a0, height=220, key=f"a_{preset}")
    b = c2.text_area("Văn bản B", b0, height=220, key=f"b_{preset}")
    u1, u2 = st.columns(2)
    unit = u1.selectbox("Đơn vị shingle", ["syllable", "char"], format_func={"syllable": "âm tiết", "char": "ký tự"}.get)
    n = u2.number_input("Độ dài n-gram", 1, 30, 5 if unit == "syllable" else 15)
    if not a.strip() or not b.strip():
        st.stop()
    r = minhash_pair(a, b, unit=unit, n=int(n))

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Jaccard thật", num(round(r["jaccard"], 3)), help=f"{r['shared']} shingle chung")
    m2.metric("Ước lượng MinHash", num(round(r["minhash_estimate"], 3)), help="Tỉ lệ hàm băm cho cùng giá trị nhỏ nhất")
    m3.metric("Dải trùng", f"{len(r['bands_matched'])} / {r['bands']}")
    m4.metric("Xác suất thành ứng viên", f"{vn(100 * r['p_candidate'], 1)}%", help="P(s) = 1 − (1 − s⁸)¹⁴")
    if r["candidate"]:
        st.warning("**Là cặp ứng viên trùng:** tầng 6 giữ văn bản đến trước và loại văn bản còn lại.")
    else:
        st.success("**Không phải cặp ứng viên:** cả hai văn bản được giữ.")

    boxes = "".join(
        f"<span style='display:inline-block;width:34px;height:34px;margin:2px;border-radius:6px;text-align:center;"
        f"line-height:34px;font-size:0.8em;background:{'#fbbc04' if i in r['bands_matched'] else '#e8eaed'}'>{i + 1}</span>"
        for i in range(r["bands"]))
    st.markdown(f"**14 dải của chữ ký** (vàng = trùng): <br>{boxes}", unsafe_allow_html=True)

    s = [i / 100 for i in range(101)]
    curve = pd.DataFrame({"Jaccard": s, "Xác suất thành ứng viên": [candidate_probability(x) for x in s]})
    st.line_chart(curve, x="Jaccard", y="Xác suất thành ứng viên", height=260)
    st.caption(f"Ngưỡng hiệu dụng (1/14)^(1/8) ≈ {num(round(r['threshold'], 2))}: dưới mức này, cặp hiếm khi bị "
               f"bắt; trên mức này, gần như chắc chắn bị bắt. Cặp hiện tại có Jaccard {num(round(r['jaccard'], 2))}. "
               f"Shingle: {r['shingles_a']} (A) và {r['shingles_b']} (B).")


# ------------------------------------------------------------------------------------------ page 3: results
# funnel stage -> label that sorts in pipeline order in the charts
STAGE_LABEL = {"input": "0 đầu vào", "normalize": "3 chuẩn hóa", "boilerplate": "3b boilerplate", "langid": "4 ngôn ngữ",
               "url_filter": "5 spam", "dedup_exact": "6a trùng chính xác", "dedup_near": "6b trùng gần đúng",
               "dedup_line": "6c dòng lặp", "quality": "7 chất lượng", "pii": "8 che PII"}


def funnel(run: str) -> pd.DataFrame | None:
    f = RUNS / run / "funnel.csv"
    return pd.read_csv(f) if f.exists() else None


def page_results():
    st.title("Kết quả chính")
    f200, f1000 = funnel("wet_200_final"), funnel("wet_1000")
    lm = read_text(EVAL / "lm_ablation.md")

    cols = st.columns(4)
    if f1000 is not None:
        cols[0].metric("Giữ lại (1.000 file)", f"{vn(f1000.iloc[-1]['pct_of_input'], 1)}%",
                       help=f"{vn(f1000.iloc[-1]['docs_out'])} / {vn(f1000.iloc[0]['docs_in'])} tài liệu")
        ex_row = f1000[f1000.stage == "dedup_exact"].iloc[0]
        cols[1].metric("Trùng chính xác (1.000 file)", f"{vn(100 * ex_row['removed'] / ex_row['docs_in'], 2)}%")
        cols[2].metric("Thời gian mỗi tài liệu", f"{vn(1000 * f1000['seconds'].sum() / f1000.iloc[0]['docs_in'], 1)} ms",
                       help="8 tiến trình, nhóm 50 file")
    if lm:
        m = re.search(r"Wikipedia: (-?[\d.]+) \(clean ([\d.]+).*?raw ([\d.]+)", lm)
        if m:
            cols[3].metric("Perplexity Wikipedia: sạch / thô",
                           f"{vn(math.exp(float(m.group(2))))} / {vn(math.exp(float(m.group(3))))}")

    st.subheader("Phễu xử lý: 200 file và 1.000 file")
    frames = {name: f for name, f in (("200 file", f200), ("1.000 file", f1000)) if f is not None}
    if frames:
        tbl = pd.concat({k: f.set_index("stage")[["docs_out", "pct_of_input"]] for k, f in frames.items()}, axis=1)
        tbl = tbl.loc[[s for s in STAGE_LABEL if s in tbl.index]].rename(index=STAGE_LABEL)
        st.line_chart(tbl.xs("pct_of_input", axis=1, level=1), height=280)
        show = pd.DataFrame(index=tbl.index)
        for name in frames:
            show[f"{name} · còn lại"] = tbl[(name, "docs_out")].map(lambda x: vn(x))
            show[f"{name} · % đầu vào"] = tbl[(name, "pct_of_input")].map(lambda x: vn(x, 1))
        st.dataframe(show)
        st.caption("Trục ngang: các tầng theo thứ tự; trục dọc: % số tài liệu đầu vào còn lại sau tầng đó.")
    else:
        st.info("Chưa có `outputs/runs/*/funnel.csv`.")

    st.subheader("Trùng lặp theo số file WET")
    md = read_text(EVAL / "dedup_stats_wet_1000.md")
    if md:
        rows = re.findall(r"^\s*(\d+)\s+[\d.]+\s+[\d.]+\s+([\d.]+)\s+[\d.]+\s+[\d.]+\s+[\d.]+\s*$", md, flags=re.M)
        if rows:
            dup = pd.DataFrame({"Số file": [int(a) for a, _ in rows], "Trùng chính xác (%)": [float(b) for _, b in rows]})
            st.line_chart(dup, x="Số file", y="Trùng chính xác (%)", height=260)
            st.caption("Tập con ngẫu nhiên lồng nhau của 1.000 file, trung bình 5 lần. Mỗi lần số file gấp đôi, "
                       "tỉ lệ tăng 1,51 → 1,37 lần. Trùng gần đúng của hai lần chạy đầy đủ: 3,36% (200 file), "
                       "6,43% (1.000 file).")

    st.subheader("Tốc độ")
    speed = []
    for run, label in (("wet_200_final", "200 file, 1 tiến trình"), ("wet_200_par", "200 file, 12 tiến trình"),
                       ("wet_1000", "1.000 file, 8 tiến trình")):
        f = funnel(run)
        if f is not None:
            total = f["seconds"].sum()
            speed.append({"Lần chạy": label, "Tổng (giây)": vn(total),
                          "ms/tài liệu": vn(1000 * total / f.iloc[0]["docs_in"], 1)})
    if speed:
        st.dataframe(pd.DataFrame(speed), hide_index=True)
    bench = EVAL / "parallel_bench.csv"
    if bench.exists():
        b = pd.read_csv(bench)
        b = b[b.stage.str.startswith("normalize")]
        st.dataframe(pd.DataFrame({
            "Cách chạy": b.stage.map(lambda s: "ftfy cả văn bản" if "whole" in s else "ftfy theo dòng"),
            "Tiến trình": b.workers, "ms/tài liệu": b.ms_per_doc.map(lambda x: vn(x, 2)),
            "Nhanh hơn cách cũ": b.speedup_vs_before.map(lambda x: f"{vn(x, 1)} lần")}), hide_index=True)
        st.caption("Tầng chuẩn hóa trên 10.000 tài liệu. CPU có 8 lõi vật lý và 12 luồng, nên 8 tiến trình nhanh nhất.")
    spark = ROOT / "data" / "spark_out" / "spark_runs.csv"
    if spark.exists():
        st.markdown("**Bản Spark** (`python -m vietweb.spark_runner`)")
        st.dataframe(pd.read_csv(spark), hide_index=True)

    st.subheader("Chi tiết các thí nghiệm")
    for name, title in (("extraction_eval.md", "Chọn phương pháp bỏ boilerplate"),
                        ("fineweb2_CC-MAIN-2024-10.md", "Đối chiếu FineWeb-2"),
                        ("langid_compare.md", "GlotLID và heuristic"),
                        ("legacy_eval.md", "Chuyển bảng mã TCVN3/VNI"),
                        ("word_unit_eval.md", "Đếm theo từ (underthesea)"),
                        ("quality_model.md", "Mô hình chất lượng học từ Wikipedia"),
                        ("benchmark_overlap_vmlu.md", "Rò rỉ VMLU"),
                        ("lm_ablation.md", "Mô hình ngôn ngữ nhỏ: dữ liệu thô và dữ liệu sạch")):
        txt = read_text(EVAL / name)
        if txt:
            with st.expander(title):
                st.markdown(txt)


# -------------------------------------------------------------------------------------------- page 4: browse
def page_browse():
    st.title("Duyệt dữ liệu đã xử lý")
    dirs = [d for d in [*sorted(RUNS.glob("*/processed")), ROOT / "data" / "processed"] if (d / "kept").exists()]
    if not dirs:
        st.info("Chưa có dữ liệu đã xử lý. Chạy `python -m vietweb run` trước.")
        return
    d = Path(st.selectbox("Lần chạy", [str(x) for x in dirs],
                          format_func=lambda s: str(Path(s).relative_to(ROOT))))
    kind = st.radio("Tập", ["kept", "dropped"], horizontal=True,
                    format_func={"kept": "giữ lại", "dropped": "bị loại"}.get)
    shards = sorted((d / kind).glob("*.parquet"))
    if not shards:
        st.info("Tập này trống.")
        return
    shard = st.selectbox("File", [str(s) for s in shards], format_func=lambda s: Path(s).name)
    df = read_parquet(shard)
    if kind == "dropped" and "drop_reason" in df:
        counts = df["drop_reason"].value_counts()
        st.bar_chart(counts, height=220)
        reason = st.selectbox("Lý do loại", list(counts.index))
        df = df[df["drop_reason"] == reason]
    if df.empty:
        return
    i = st.number_input(f"Tài liệu (0–{len(df) - 1})", 0, len(df) - 1, 0)
    row = df.iloc[int(i)]
    st.caption(row.get("url", ""))
    st.text(str(row.get("text", ""))[:4000])


# ------------------------------------------------------------------------------------------------------ main
def main():
    st.set_page_config(page_title="VietWeb demo", layout="wide")
    st.sidebar.title("VietWeb")
    st.sidebar.caption("Pipeline làm sạch văn bản web tiếng Việt từ Common Crawl")
    page = st.sidebar.radio("Trang", ["Thử một trang", "Trùng lặp gần đúng", "Kết quả", "Duyệt dữ liệu"])
    cfg = resources().cfg
    st.sidebar.caption(
        f"Cấu hình: bỏ boilerplate `{cfg['boilerplate'].get('method')}` · nhận diện ngôn ngữ "
        f"`{cfg['langid'].get('backend')}` (ngưỡng {num(cfg['langid'].get('threshold', 0.6))}) · "
        f"đếm theo `{cfg['quality'].get('unit')}`")
    {"Thử một trang": page_try, "Trùng lặp gần đúng": page_minhash, "Kết quả": page_results,
     "Duyệt dữ liệu": page_browse}[page]()


main()
