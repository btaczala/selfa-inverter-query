import hashlib
import struct
import base64


def hash_password(username: str, password: str):
    return base64.standard_b64encode(
        bytes_to_hex(words_to_bytes(md5(
            string_to_bytes(password)))).encode()).decode('utf-8')


def md5(arr: bytes):
    md5_hash = hashlib.md5(arr).digest()
    return list(struct.unpack('>4i', md5_hash))


def bytes_to_hex(byte_list):
    return ''.join(f'{b:02x}' for b in byte_list)


def words_to_bytes(words: bytes):
    bytes_out = []
    for i in range(len(words) * 4):
        word_index = i // 4
        shift = 24 - (i % 4) * 8
        byte = (words[word_index] >> shift) & 0xFF
        bytes_out.append(byte)
    return bytes_out


def string_to_bytes(s: str) -> bytes:
    return s.encode('utf-8')
