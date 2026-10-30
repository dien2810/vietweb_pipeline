"""TCVN3 / VNI conversion. Vietnamese strings are test inputs."""
from vietweb.text.legacy import (convert_legacy, decode_tcvn3, decode_vni, encode_tcvn3, encode_vni)

STOP = {"là", "của", "và", "có", "được", "cho", "không", "những", "các", "một", "trong", "với", "người"}
TEXT = ("Hà Nội là thủ đô của nước Cộng hòa xã hội chủ nghĩa Việt Nam và là một trong những thành phố "
        "có lịch sử lâu đời nhất. Các trường đại học được xây dựng cho người dân.")


def test_round_trip():
    assert encode_tcvn3("Hà Nội") == "Hµ Néi"
    assert encode_vni("Hà Nội") == "Haø Noäi"
    assert decode_vni(encode_vni(TEXT)) == TEXT
    # TCVN3 has no codes for most upper-case letters with tone marks: they come back in lower case
    assert decode_tcvn3(encode_tcvn3(TEXT)) == TEXT
    assert decode_tcvn3(encode_tcvn3("ĐẠI HỌC")) == "ĐạI HọC"


def test_convert_legacy_decides():
    assert convert_legacy(encode_tcvn3(TEXT), STOP) == (TEXT, "tcvn3")
    assert convert_legacy(encode_vni(TEXT), STOP) == (TEXT, "vni")
    # Unicode Vietnamese and other languages written with Latin-1 letters stay as they are
    assert convert_legacy(TEXT, STOP) == (TEXT, None)
    turkish = "Bugünden sonra ay hesaplayıcı, doğum tarihinizi girin ve sonucu öğrenin. Çok kolay ve hızlı."
    assert convert_legacy(turkish, STOP) == (turkish, None)
