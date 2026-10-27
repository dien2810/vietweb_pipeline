"""Tests for text normalization and tokenization. Vietnamese strings are test inputs."""
import unicodedata

from vietweb.text.normalize import legacy_encoding_score, normalize_text, normalize_tone_marks
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
