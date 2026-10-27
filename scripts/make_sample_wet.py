"""Create a small synthetic WET file to try the pipeline before downloading real data.

The file contains good Vietnamese records, an exact and a near duplicate, gambling spam, a short menu page,
a page with a phone number and e-mail, a product listing with many short lines, TCVN3 text decoded
incorrectly, an English record (removed by the language pre-filter), and a record using new-style
tone-mark placement.

Run: python scripts/make_sample_wet.py data/sample/sample.warc.wet.gz
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

from warcio.warcwriter import WARCWriter

# The sample texts below are Vietnamese on purpose: they are the input data the pipeline must process.
GOOD = [
    "Hà Nội là thủ đô của nước Cộng hòa Xã hội Chủ nghĩa Việt Nam. Thành phố có lịch sử hơn một nghìn năm "
    "và là trung tâm chính trị, văn hóa của cả nước. Người dân ở đây rất thân thiện và mến khách, luôn sẵn lòng chỉ đường cho du khách.\n"
    "Mùa thu Hà Nội được nhiều người yêu thích vì thời tiết mát mẻ, trời trong xanh. Các con phố cổ vẫn giữ "
    "được nét đẹp truyền thống với những ngôi nhà ống và mái ngói rêu phong.\n"
    "Du khách có thể thưởng thức phở, bún chả và nhiều món ăn đặc sắc khác khi đến thăm thành phố này.",
    "Trí tuệ nhân tạo đang thay đổi cách chúng ta làm việc và học tập. Các mô hình ngôn ngữ lớn được huấn luyện "
    "trên lượng văn bản khổng lồ thu thập từ internet, vì vậy chất lượng dữ liệu có vai trò rất quan trọng đối với kết quả cuối cùng.\n"
    "Nếu dữ liệu chứa nhiều văn bản trùng lặp hoặc spam, mô hình sẽ học những mẫu không mong muốn. Do đó các "
    "nhóm nghiên cứu đã xây dựng nhiều pipeline để làm sạch dữ liệu trước khi huấn luyện.\n"
    "Việc khử trùng lặp và lọc chất lượng giúp mô hình học hiệu quả hơn và giảm hiện tượng ghi nhớ nguyên văn.",
    "Bóng đá là môn thể thao được yêu thích nhất tại Việt Nam. Mỗi khi đội tuyển quốc gia thi đấu, hàng triệu "
    "người hâm mộ theo dõi trên truyền hình và cổ vũ nhiệt tình trên khắp các con phố, từ thành thị đến nông thôn.\n"
    "Những chiến thắng tại các giải đấu khu vực đã mang lại niềm vui lớn cho người hâm mộ cả nước. Các cầu thủ "
    "trẻ ngày càng được đào tạo bài bản hơn tại các học viện bóng đá.\n"
    "Nhiều chuyên gia cho rằng bóng đá Việt Nam cần đầu tư nhiều hơn vào hệ thống giải trẻ để phát triển bền vững.",
]
# Near duplicate of GOOD[1]: two words changed
NEAR_DUP = GOOD[1].replace("rất quan trọng", "vô cùng quan trọng")
# GOOD[0] rewritten with new-style tone-mark placement; after normalization it becomes a near duplicate
NEW_STYLE = GOOD[0].replace("Cộng hòa", "Cộng hoà").replace("văn hóa", "văn hoá")
# A distinct article that ends with contact details (phone number and e-mail to be masked)
PHONE = ("Cửa hàng chúng tôi chuyên cung cấp sách giáo khoa và sách tham khảo cho học sinh trên toàn quốc. "
         "Mỗi năm học mới, chúng tôi cập nhật đầy đủ các đầu sách theo chương trình của Bộ Giáo dục và Đào tạo "
         "để phục vụ nhu cầu của các em.\n"
         "Khách hàng có thể đặt mua trực tuyến và nhận hàng tại nhà trong vòng hai đến ba ngày làm việc. "
         "Chúng tôi cũng có chính sách đổi trả trong bảy ngày nếu sách bị lỗi in ấn.\n"
         "Liên hệ: 0912 345 678 hoặc email lienhe@example.com để được tư vấn chi tiết.")
# Product listing: many short lines
LISTING = "\n".join(f"Áo thun nam mẫu {i} - giá {i}9.000đ" for i in range(1, 25))
# TCVN3-encoded text misread as Latin-1 (contains soft hyphens, written as escapes)
LEGACY = ("Hµ Néi lµ thñ ®« cña n\u00adíc Céng hßa x· héi chñ nghÜa ViÖt Nam. Thµnh phè cã lÞch sö h¬n mét "
          "ngh×n n¨m vµ lµ trung t©m chÝnh trÞ, v¨n hãa cña c¶ n\u00adíc. ") * 3
# Gambling spam written as fluent sentences (as on real SEO spam pages), so it passes the boilerplate stage
# and is caught by the spam-keyword filter
SPAM = ("Nhà cái uy tín số 1 hiện nay là lựa chọn của rất nhiều người chơi khi tham gia cá cược bóng đá trực tuyến. "
        "Người chơi mới sẽ được nhận khuyến mãi nạp đầu và có thể chơi nổ hũ, tài xỉu hay lô đề ngay trên điện thoại.\n"
        "Link vào nhà cái được cập nhật mỗi ngày để người chơi không bị chặn khi truy cập. Đội ngũ hỗ trợ luôn sẵn "
        "sàng giải đáp mọi thắc mắc của khách hàng về cá cược và soi cầu trong suốt cả ngày lẫn đêm.")
# Navigation menu (shorter than collect.min_chars)
MENU = "Trang chủ\nGiới thiệu\nLiên hệ\nĐăng nhập\nĐăng ký\nTin tức\nSản phẩm\nGiỏ hàng"
ENGLISH = ("Common Crawl maintains a free, open repository of web crawl data that can be used by anyone. "
           "The corpus contains petabytes of data collected since 2008. ") * 4
# Extra sentence appended to the new-style copy ("This article was last updated this year.")
UPDATED_NOTE = "\nBài viết được cập nhật lần cuối vào năm nay."

RECORDS = [
    ("https://vi.example.org/ha-noi", "vie", GOOD[0]),
    ("https://news.example.vn/ai-du-lieu", "vie", GOOD[1]),
    ("https://thethao.example.vn/bong-da", "vie,eng", GOOD[2]),
    ("https://mirror.example.net/ha-noi-copy", "vie", GOOD[0]),          # exact duplicate
    ("https://blog.example.vn/ai-du-lieu-2", "vie", NEAR_DUP),           # near duplicate
    ("https://old.example.vn/ha-noi-kieu-moi", "vie", NEW_STYLE + UPDATED_NOTE),
    ("https://ads.example.vn/lien-he", "vie", PHONE),
    ("https://nhacai.example.com/", "vie", SPAM),
    ("https://shop.example.vn/menu", "vie", MENU),                       # too short, dropped at collection
    ("https://shop.example.vn/ao-thun", "vie", LISTING),                 # many short lines -> quality filter
    ("https://cu.example.vn/tcvn3", "vie", LEGACY),                      # misdecoded TCVN3
    ("https://en.example.com/about", "eng", ENGLISH),
]


def make(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        writer = WARCWriter(f, gzip=True)
        for url, lang, text in RECORDS:
            headers = {
                "WARC-Target-URI": url,
                "WARC-Date": "2026-09-10T12:00:00Z",
                "WARC-Identified-Content-Language": lang,
                "Content-Type": "text/plain",
            }
            rec = writer.create_warc_record(url, "conversion", payload=io.BytesIO(text.encode("utf-8")),
                                            warc_headers_dict=headers)
            writer.write_record(rec)
    return path


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "data/sample/sample.warc.wet.gz")
    print(f"Created {make(out)} with {len(RECORDS)} records")
