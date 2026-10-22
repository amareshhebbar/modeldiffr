import hashlib
import json
import math
from decimal import Decimal


class CanonicalizationError(ValueError):
    pass


def _number(value: float) -> str:
    if isinstance(value, bool):
        raise CanonicalizationError("booleans are not numbers")
    if isinstance(value, int):
        if abs(value) > 2**53:
            raise CanonicalizationError(f"integer {value} is outside the IEEE 754 safe range")
        return str(value)
    if math.isnan(value) or math.isinf(value):
        raise CanonicalizationError("NaN and infinity cannot be serialized")
    if value == 0:
        return "0"
    sign = "-" if value < 0 else ""
    digits_tuple, exponent = Decimal(repr(abs(value))).as_tuple()[1:]
    digits = "".join(str(d) for d in digits_tuple).rstrip("0") or "0"
    stripped = len("".join(str(d) for d in digits_tuple)) - len(digits)
    exponent += stripped
    k = len(digits)
    n = k + exponent
    if k <= n <= 21:
        out = digits + "0" * (n - k)
    elif 0 < n <= 21:
        out = digits[:n] + "." + digits[n:]
    elif -6 < n <= 0:
        out = "0." + "0" * (-n) + digits
    else:
        e = n - 1
        mantissa = digits[0] + ("." + digits[1:] if k > 1 else "")
        out = f"{mantissa}e{'+' if e > 0 else '-'}{abs(e)}"
    return sign + out


def _encode(value, out: list[str]) -> None:
    if value is None:
        out.append("null")
    elif value is True:
        out.append("true")
    elif value is False:
        out.append("false")
    elif isinstance(value, (int, float)):
        out.append(_number(value))
    elif isinstance(value, str):
        out.append(json.dumps(value, ensure_ascii=False))
    elif isinstance(value, (list, tuple)):
        out.append("[")
        for i, item in enumerate(value):
            if i:
                out.append(",")
            _encode(item, out)
        out.append("]")
    elif isinstance(value, dict):
        for key in value:
            if not isinstance(key, str):
                raise CanonicalizationError(
                    f"object keys must be strings, got {type(key).__name__}"
                )
        out.append("{")
        for i, key in enumerate(sorted(value, key=lambda s: s.encode("utf-16-be"))):
            if i:
                out.append(",")
            out.append(json.dumps(key, ensure_ascii=False))
            out.append(":")
            _encode(value[key], out)
        out.append("}")
    else:
        raise CanonicalizationError(f"cannot serialize {type(value).__name__}")


def canonical_json(value) -> bytes:
    out: list[str] = []
    _encode(value, out)
    return "".join(out).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def object_hash(value) -> str:
    return "sha256:" + sha256_hex(canonical_json(value))
