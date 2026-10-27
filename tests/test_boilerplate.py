"""Tests for stage 3b (boilerplate removal). Vietnamese strings are test inputs."""
import copy

import pandas as pd

from vietweb.config import load_config
from vietweb.stages.s03b_boilerplate import (_params, clean_text, load_params_and_stopwords, revise_classes,
                                             run)

MENU = ["Trang chủ", "Giới thiệu", "Sản phẩm", "Tin tức", "Liên hệ", "Đăng nhập", "Giỏ hàng"]
PARA1 = ("Khi tham gia một buổi tiệc, việc lựa chọn kiểu tóc phù hợp không chỉ giúp bạn trở nên nổi bật mà còn "
         "tạo điểm nhấn cho trang phục. Dưới đây là những gợi ý được nhiều người áp dụng và có thể làm tại nhà.")
HEADING = "1. Tóc búi cao thanh lịch cho váy dạ hội"
PARA2 = ("Váy dạ hội dài thường đi kèm phong cách trang trọng và quý phái. Một kiểu tóc búi cao, bóng mượt sẽ là "
         "lựa chọn hoàn hảo để tôn lên chiếc cổ thon dài và vẻ đẹp sang trọng của bạn trong buổi tiệc.")
FOOTER = ["Copyright 2026 © Example. Bản quyền thuộc về công ty, mọi hình thức sao chép phải được cho phép trước.",
          "Hotline: 0974 586 855", "Email: lienhe@example.com"]


def _justext_cfg():
    """The project config with method: justext, so these tests do not depend on the method chosen in the YAML."""
    cfg = copy.deepcopy(load_config())
    cfg["boilerplate"]["method"] = "justext"
    return cfg


def _p_stop():
    return load_params_and_stopwords(_justext_cfg())


def test_menu_and_footer_removed_article_kept():
    p, stop = _p_stop()
    page = "\n".join(["Tiêu đề trang - Example"] + MENU + [PARA1, HEADING, PARA2] + FOOTER)
    out = clean_text(page, p, stop).split("\n")
    assert out == [PARA1, HEADING, PARA2]       # the heading between two good paragraphs is kept


def test_page_with_only_short_lines_becomes_empty():
    p, stop = _p_stop()
    assert clean_text("\n".join(MENU * 3), p, stop) == ""


def test_url_line_is_bad():
    p, stop = _p_stop()
    urls = " ".join(f"https://site{i}.example.vn/" for i in range(10))
    out = clean_text("\n".join([urls, PARA1, PARA2]), p, stop)
    assert "https://" not in out and PARA1 in out


def test_revise_classes_follows_justext():
    assert revise_classes(["good", "short", "good"]) == ["good", "good", "good"]
    assert revise_classes(["bad", "short", "bad"]) == ["bad", "bad", "bad"]
    assert revise_classes(["bad", "short", "good"]) == ["bad", "bad", "good"]
    # a short line next to a near-good line that leads to a bad line becomes good
    assert revise_classes(["good", "short", "neargood", "bad"]) == ["good", "good", "good", "bad"]
    assert revise_classes(["bad", "neargood", "bad"]) == ["bad", "bad", "bad"]
    assert revise_classes(["neargood"]) == ["bad"]              # page edges count as bad


def test_c4_lines_method():
    p = _params({"method": "c4_lines"})
    _, stop = _p_stop()
    lines = ["Trang chủ", "Bật javascript để xem nội dung này.", "Câu này có đủ năm âm tiết.", "Ngắn quá."]
    assert clean_text("\n".join(lines), p, stop) == "Câu này có đủ năm âm tiết."


def test_c4_lines_drops_truncated_excerpts():
    _, stop = _p_stop()
    lines = ["Câu này có đủ năm âm tiết.", "Bài viết liên quan về chủ đề kiểu tóc dự tiệc…",
             "Xem thêm các mẹo hay để làm đẹp tại nhà..."]
    text = "\n".join(lines)
    assert clean_text(text, _params({"method": "c4_lines", "c4_drop_ellipsis": True}), stop) == lines[0]
    assert clean_text(text, _params({"method": "c4_lines", "c4_drop_ellipsis": False}), stop) == text


def test_stage_drops_pages_left_too_short():
    cfg = _justext_cfg()
    df = pd.DataFrame({"text": ["\n".join(MENU + [PARA1, HEADING, PARA2]), "\n".join(MENU)]}, index=[3, 7])
    res = run(df, cfg)
    assert res.drop_reason.tolist() == [None, "boilerplate_too_short"]
    assert res.text[3].startswith(PARA1)
    assert 0 < res.extra["bp_chars_ratio"][3] < 1
    assert res.stats["removed_lines"] == 2 * len(MENU)
