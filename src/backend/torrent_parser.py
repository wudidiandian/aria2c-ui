"""种子文件（.torrent）解析：提取文件列表供前端做选择性下载。

纯标准库实现的最小 bencode 解码器，不引入外部依赖。
解析出的文件顺序与 aria2 的 1 起始文件索引一一对应
（aria2 tellStatus files 数组顺序 = 种子 info.files 顺序），
因此该索引可直接用作 addTorrent 的 select-file 选项。
同时计算种子的 infohash（info 字典原始 bencode 字节的 SHA1），
用于在创建任务前检测同一 BT 种子的重复下载（aria2 会拒绝重复 infohash）。
"""
import hashlib
from pathlib import Path


class TorrentParseError(ValueError):
    """种子文件解析失败（携带可展示给用户的信息）"""


def _decode(data: bytes, idx: int):
    """从 data[idx:] 解码一个 bencode 值，返回 (value, next_idx)"""
    if idx >= len(data):
        raise TorrentParseError("bencode 数据不完整")
    c = data[idx:idx + 1]

    if c == b"i":  # 整数 i<number>e
        end = data.find(b"e", idx)
        if end < 0:
            raise TorrentParseError("bencode 整数格式错误")
        return int(data[idx + 1:end]), end + 1

    if c.isdigit():  # 字节串 <length>:<bytes>
        colon = data.find(b":", idx)
        if colon < 0:
            raise TorrentParseError("bencode 字符串格式错误")
        length = int(data[idx:colon])
        start = colon + 1
        if start + length > len(data):
            raise TorrentParseError("bencode 字符串长度越界")
        return data[start:start + length], start + length

    if c == b"l":  # 列表 l<value>*e
        idx += 1
        items = []
        while data[idx:idx + 1] != b"e":
            value, idx = _decode(data, idx)
            items.append(value)
        return items, idx + 1

    if c == b"d":  # 字典 d<str><value>*e
        idx += 1
        result = {}
        while data[idx:idx + 1] != b"e":
            key, idx = _decode(data, idx)
            value, idx = _decode(data, idx)
            result[key] = value
        return result, idx + 1

    raise TorrentParseError("bencode 格式错误")


def _to_str(value: bytes) -> str:
    """种子内字符串通常为 UTF-8，老旧种子可能是 GBK"""
    for encoding in ("utf-8", "gbk"):
        try:
            return value.decode(encoding)
        except UnicodeDecodeError:
            continue
    return value.decode("utf-8", "replace")


def _skip_value(data: bytes, idx: int) -> int:
    """跳过一个 bencode 值，返回结束位置（用于定位 info 字典的原始字节区间）"""
    if idx >= len(data):
        raise TorrentParseError("bencode 数据不完整")
    c = data[idx:idx + 1]
    if c == b"i":
        end = data.find(b"e", idx)
        if end < 0:
            raise TorrentParseError("bencode 整数格式错误")
        return end + 1
    if c.isdigit():
        colon = data.find(b":", idx)
        if colon < 0:
            raise TorrentParseError("bencode 字符串格式错误")
        return colon + 1 + int(data[idx:colon])
    if c in (b"l", b"d"):
        idx += 1
        if c == b"l":
            while data[idx:idx + 1] != b"e":
                idx = _skip_value(data, idx)
        else:
            while data[idx:idx + 1] != b"e":
                idx = _skip_value(data, idx)  # key
                idx = _skip_value(data, idx)  # value
        return idx + 1
    raise TorrentParseError("bencode 格式错误")


def _info_dict_span(data: bytes):
    """定位顶层 info 值的原始字节区间 [start, end)，用于计算 infohash"""
    if data[:1] != b"d":
        return None
    idx = 1
    while idx < len(data) and data[idx:idx + 1] != b"e":
        # 顶层 key 必为字符串
        if not data[idx:idx + 1].isdigit():
            return None
        colon = data.find(b":", idx)
        if colon < 0:
            return None
        key = data[colon + 1:colon + 1 + int(data[idx:colon])]
        start = colon + 1 + int(data[idx:colon])
        idx = _skip_value(data, start)
        if key == b"info":
            return (start, idx)
    return None


def parse_torrent(path: str) -> dict:
    """解析 .torrent 文件，返回文件列表元数据。

    返回结构：
    {
        "name": 种子名称（info.name），
        "is_multi": 是否多文件种子,
        "info_hash": 种子 infohash（40 位小写十六进制，aria2 去重口径一致）,
        "total_length": 所有文件总大小（字节）,
        "files": [{"index": 1起始索引, "path": [路径段，首段为种子名], "length": 字节}],
    }
    """
    raw = Path(path).read_bytes()
    try:
        meta, _ = _decode(raw, 0)
    except TorrentParseError:
        raise
    except (ValueError, IndexError) as e:
        raise TorrentParseError("种子文件解析失败") from e

    if not isinstance(meta, dict) or not isinstance(meta.get(b"info"), dict):
        raise TorrentParseError("不是有效的种子文件（缺少 info 字段）")

    # infohash = info 值原始 bencode 字节的 SHA1（与 aria2 tellStatus infoHash 一致）
    span = _info_dict_span(raw)
    info_hash = hashlib.sha1(raw[span[0]:span[1]]).hexdigest() if span else None

    info = meta[b"info"]
    name = _to_str(info.get(b"name", b""))
    files = []
    if b"files" in info:  # 多文件种子：files 数组，每项含 path 列表与 length
        for index, entry in enumerate(info[b"files"], start=1):
            if not isinstance(entry, dict):
                raise TorrentParseError("种子文件列表格式错误")
            parts = [_to_str(p) for p in entry.get(b"path", []) if p]
            files.append({
                "index": index,
                # 前置种子名，与 aria2 文件路径（dir/<种子名>/...）展示口径一致
                "path": [name, *parts],
                "length": int(entry.get(b"length", 0)),
            })
        is_multi = True
    else:  # 单文件种子：info.name 即文件名
        files.append({
            "index": 1,
            "path": [name],
            "length": int(info.get(b"length", 0)),
        })
        is_multi = False

    return {
        "name": name,
        "is_multi": is_multi,
        "info_hash": info_hash,
        "total_length": sum(f["length"] for f in files),
        "files": files,
    }
