"""Tests for text normalization and tokenization. Vietnamese strings are test inputs."""
import unicodedata

import ftfy

from vietweb.text.normalize import (fix_text_lines, legacy_encoding_score, normalize_text,
                                     normalize_tone_marks)
from vietweb.text.tokenize import shingles, syllables


def test_nfc():
    nfd = unicodedata.normalize("NFD", "Tiếng Việt")
    assert normalize_text(nfd, tone_style="none") == "Tiếng Việt"


def test_tone_marks_old_style():
    assert normalize_tone_marks("hoà bình, thuỷ lợi, khoẻ mạnh", "old") == "hòa bình, thủy lợi, khỏe mạnh"
    # rhymes with a final consonant and syllables starting with 'qu' are unchanged
    assert normalize_tone_marks("hoàn thành, quý khách, quỳnh", "old") == "hoàn thành, quý khách, quỳnh"
    assert normalize_tone_marks("Hoà", "old") == "Hòa"


def test_tone_marks_new_style_roundtrip():
    s = "hòa bình, thủy lợi"
    assert normalize_tone_marks(normalize_tone_marks(s, "new"), "old") == s


def test_whitespace_and_control_chars():
    zero_width_space = "\u200b"
    assert normalize_text(f"a{zero_width_space} b\t\tc\n\n\n\nd", tone_style="none") == "a b c\n\nd"


def test_legacy_encoding_score():
    soft_hyphen = "\u00ad"
    tcvn3 = f"Hµ Néi lµ thñ ®« cña n{soft_hyphen}íc Céng hßa x· héi chñ nghÜa ViÖt Nam"
    assert legacy_encoding_score(tcvn3) > 0.05
    assert legacy_encoding_score("Hà Nội là thủ đô của nước Cộng hòa xã hội chủ nghĩa Việt Nam") == 0


def test_tokenize():
    assert syllables("Xin chào, Việt Nam!") == ["xin", "chào", "việt", "nam"]
    assert shingles("một hai ba bốn năm sáu", "syllable", 5) == {"một hai ba bốn năm", "hai ba bốn năm sáu"}
    assert len(shingles("abcdef", "char", 3)) == 4


def test_fix_text_lines_matches_ftfy():
    # Running ftfy only on lines it could change must give the same text as ftfy on the whole document
    cases = [
        "Nguyá»…n VÄƒn A\nHà Nội",                    # UTF-8 read as Windows-1252
        "Game bÃ i\ntài xỉu",                          # "à" whose A0 byte became a space
        "nh&#224; c&aacute;i\n<b>x</b>\nnh&#224;",     # entities; a "<" turns unescaping off for later lines
        "dòng một\r\ndòng hai\rba",                    # Windows and old Mac line breaks
        "“Trích dẫn” – ﬁn ＡＢＣ",                       # curly quotes, ligature, full-width letters
        "Tiếng Việt bình thường, không cần sửa.\n\nHÀ NỘI",
    ]
    for s in cases:
        assert fix_text_lines(s) == ftfy.fix_text(s, normalization="NFC")
