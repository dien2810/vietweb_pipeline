"""Made-up example pages for the demo app (dashboard/demo.py). Each one ends at a different stage.

The texts, names, phone numbers and e-mail addresses are invented for the demo.
"""
from __future__ import annotations

from vietweb.text.legacy import encode_tcvn3

ARTICLE = """Từ đầu tháng tới, thành phố sẽ đưa vào khai thác ba tuyến xe buýt điện mới, nối các khu dân cư ở phía đông với trung tâm và các nhà ga đường sắt đô thị.
Theo sở giao thông, mỗi tuyến có khoảng hai mươi xe, chạy từ năm giờ sáng đến mười giờ tối, tần suất mười lăm phút một chuyến vào giờ cao điểm.
Giá vé được giữ ở mức bảy nghìn đồng một lượt, học sinh và người cao tuổi được giảm một nửa khi dùng thẻ đi lại điện tử.
Đại diện đơn vị vận hành cho biết các tuyến mới được thiết kế để người dân có thể đổi sang tàu điện mà không phải đi bộ quá năm trăm mét."""

NEWS = f"""Trang chủ
Thời sự
Kinh tế
Thể thao
Giải trí
Đăng nhập | Đăng ký
Thành phố mở thêm ba tuyến xe buýt điện nối các khu dân cư mới
Thứ năm, 29/10/2026 08:15
{ARTICLE}
Người dân cần hỗ trợ có thể gọi đường dây nóng 0912 345 678 hoặc gửi thư tới hotro@xebuyt-thanhpho.vn để được giải đáp.
Tin liên quan
Giá xăng giảm lần thứ ba trong tháng, nhiều tài xế vui mừng…
Xem thêm
© 2026 Báo Thành Phố"""

LIBRARY = """Thư viện tỉnh vừa mở thêm một phòng đọc dành cho thiếu nhi với hơn ba nghìn đầu sách mới.
Phòng đọc mở cửa từ tám giờ sáng đến năm giờ chiều, kể cả ngày thứ bảy và chủ nhật.
Các em có thể mượn sách về nhà trong hai tuần nếu có thẻ thư viện do nhà trường cấp.
Mỗi tháng, thư viện còn tổ chức một buổi kể chuyện và một cuộc thi vẽ tranh cho các em nhỏ."""

SPAM = """Nhà cái uy tín nhất hiện nay, đăng ký là nhận ngay khuyến mãi nạp đầu lên tới một trăm phần trăm.
Chơi tài xỉu, nổ hũ và bắn cá đổi thưởng mọi lúc mọi nơi, rút tiền nhanh chỉ trong năm phút.
Link vào nhà cái mới nhất được cập nhật liên tục để người chơi không bị chặn.
Đội ngũ chăm sóc khách hàng làm việc cả ngày lẫn đêm và hỗ trợ người chơi mới từng bước.
Hãy đăng ký tài khoản ngay hôm nay để nhận thêm nhiều phần quà hấp dẫn từ nhà cái."""

ENGLISH = """The city will open three new electric bus routes next month, linking new residential areas in the east with the centre and the metro stations.
Each route will have about twenty buses running from five in the morning until ten at night, every fifteen minutes during rush hours.
Tickets will stay at seven thousand dong per ride, and students and older residents will pay half when they use the electronic travel card."""

MENU = """Trang chủ
Giới thiệu
Sản phẩm
Tin tức
Liên hệ
Đăng nhập
Giỏ hàng (0)
Chưa có sản phẩm trong giỏ hàng.
Hotline: 0909 000 111"""

_AD = "Bán nhà mặt tiền đường lớn, sổ hồng chính chủ, giá tốt cho khách thiện chí, liên hệ ngay."
REPEATED = "\n".join([_AD] * 6 + ["Nhận ký gửi nhà đất tại khu trung tâm, hỗ trợ thủ tục sang tên nhanh gọn."])

# label -> (url, text, what the example shows)
EXAMPLES: dict[str, tuple[str, str, str]] = {
    "Trang tin có menu và chân trang": (
        "https://baothanhpho.example/thoi-su/xe-buyt-dien.html", NEWS,
        "Tầng 3b bỏ menu, tiêu đề và chân trang; tầng 8 che số điện thoại và email. Trang được giữ."),
    "Trang viết bằng bảng mã TCVN3": (
        "http://thuvien.example/tin-tuc.htm", encode_tcvn3(LIBRARY),
        "Văn bản hiện thành ký tự lạ; tầng 3 nhận ra TCVN3 và chuyển về Unicode."),
    "Trang quảng cáo cờ bạc": (
        "https://nhacai.example/khuyen-mai", SPAM,
        "Câu văn trôi chảy nên qua tầng 3b và tầng 4, nhưng tầng 5 đếm được nhiều từ khóa cờ bạc."),
    "Trang tiếng Anh": (
        "https://citynews.example/buses", ENGLISH,
        "Câu đủ dài và có dấu câu nên qua tầng 3b; tầng 4 cho điểm tiếng Việt thấp."),
    "Trang chỉ có menu": (
        "https://shop.example/", MENU,
        "Gần như mọi dòng đều là menu; sau tầng 3b còn dưới 200 ký tự."),
    "Trang rao vặt lặp lại": (
        "https://raovat.example/nha-dat", REPEATED,
        "Các dòng giống hệt nhau; tầng 7 loại vì luật dòng trùng hoặc luật n-gram."),
}

# Text pairs for the MinHash page: label -> (text A, text B)
PAIR_A = ARTICLE
PAIR_B = ARTICLE.replace("ba tuyến", "bốn tuyến").replace("hai mươi xe", "hai mươi lăm xe").rsplit("\n", 1)[0] + (
    "\nTheo kế hoạch, các tuyến này sẽ được mở rộng thêm vào năm sau.")
PAIRS: dict[str, tuple[str, str]] = {
    "Gần giống: chỉ sửa một chữ": (ARTICLE, ARTICLE.replace("bảy nghìn đồng", "tám nghìn đồng")),
    "Viết lại một phần: sửa vài chữ, thay một câu": (PAIR_A, PAIR_B),
    "Hai bài khác nhau": (ARTICLE, LIBRARY),
}
