import hashlib as _hashlib
import json as _json

LIBS = ["hashlib", "json", "bit"]

hashlib = {
    "md5": lambda x: _hashlib.md5(x.encode("utf-8")).hexdigest(),
    "sha1": lambda x: _hashlib.sha1(x.encode("utf-8")).hexdigest(),
    "sha224": lambda x: _hashlib.sha224(x.encode("utf-8")).hexdigest(),
    "sha256": lambda x: _hashlib.sha256(x.encode("utf-8")).hexdigest(),
    "sha384": lambda x: _hashlib.sha384(x.encode("utf-8")).hexdigest(),
    "sha512": lambda x: _hashlib.sha512(x.encode("utf-8")).hexdigest(),
}

json = {
    "dumps": lambda x: _json.dumps(x, ensure_ascii=False),
    "loads": lambda x: _json.loads(x),
}

bit = {
    "tohex": lambda x: hex(x),
    "bnot": lambda x: ~x,
    "band": lambda x, y: x & y,
    "bor": lambda x, y: x | y,
    "bxor": lambda x, y: x ^ y,
    "lshift": lambda num, shift: (
        (num << shift)
        if num >= 0
        else (
            ((num + (1 << 32)) >> shift)
            if num < 0 and num >= -(1 << 32)
            else ((num & ((1 << 32) - 1)) << shift)
        )
    ),
    "rshift": lambda num, shift: (
        (num >> shift)
        if num >= 0
        else (
            ((num + (1 << 32)) >> shift)
            if num < 0 and num >= -(1 << 32)
            else ((num & ((1 << 32) - 1)) >> shift)
        )
    ),
    "arshift": lambda x, y: x >> y,
    "rol": lambda x, y: (x << y) | (x >> (32 - y)),
    "ror": lambda x, y: (x >> y) | (x << (32 - y)),
    "bswap": lambda x: (
        ((x << 24) & 0xFF000000)
        | ((x << 8) & 0x00FF0000)
        | ((x >> 8) & 0x0000FF00)
        | ((x >> 24) & 0x000000FF)
    ),
}


def option_module(name, lib_name=None):
    try:
        LIBS.append(lib_name or name)
        return __import__(name)
    except ImportError:
        LIBS.remove(lib_name or name)
        return


scipy = option_module("scipy")
numpy = option_module("numpy")
http = option_module("requests", "http")
