import selfa_crypt
import base64


def test_string_to_bytes():
    assert list(selfa_crypt.string_to_bytes("bartek123")) == [
        98, 97, 114, 116, 101, 107, 49, 50, 51
    ]


def test_md5():
    res = [-291538583, 19496506, 1861638961, -1757671365]
    assert list(selfa_crypt.md5(
        selfa_crypt.string_to_bytes("bartek123"))) == res


def test_words_to_bytes():
    res = [
        238, 159, 121, 105, 1, 41, 126, 58, 110, 246, 91, 49, 151, 60, 16, 59
    ]
    assert selfa_crypt.words_to_bytes(
        selfa_crypt.md5(selfa_crypt.string_to_bytes("bartek123"))) == res


def test_123():
    value = [
        238, 159, 121, 105, 1, 41, 126, 58, 110, 246, 91, 49, 151, 60, 16, 59
    ]

    res = "ZWU5Zjc5NjkwMTI5N2UzYTZlZjY1YjMxOTczYzEwM2I="

    assert selfa_crypt.bytes_to_hex(value) == base64.b64decode(res).decode(
        'utf-8')


def test_password():
    assert selfa_crypt.hash_password(
        "", "bartek123") == "ZWU5Zjc5NjkwMTI5N2UzYTZlZjY1YjMxOTczYzEwM2I="
