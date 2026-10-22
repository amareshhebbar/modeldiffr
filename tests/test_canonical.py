import math
import struct

import pytest

from modeldiffr.proof.canonical import CanonicalizationError, canonical_json, object_hash

VECTORS = {
    "0000000000000000": "0",
    "8000000000000000": "0",
    "0000000000000001": "5e-324",
    "8000000000000001": "-5e-324",
    "7fefffffffffffff": "1.7976931348623157e+308",
    "ffefffffffffffff": "-1.7976931348623157e+308",
    "4340000000000000": "9007199254740992",
    "c340000000000000": "-9007199254740992",
    "4430000000000000": "295147905179352830000",
    "44b52d02c7e14af5": "9.999999999999997e+22",
    "44b52d02c7e14af6": "1e+23",
    "44b52d02c7e14af7": "1.0000000000000001e+23",
    "444b1ae4d6e2ef4e": "999999999999999700000",
    "444b1ae4d6e2ef4f": "999999999999999900000",
    "444b1ae4d6e2ef50": "1e+21",
    "3eb0c6f7a0b5ed8c": "9.999999999999997e-7",
    "3eb0c6f7a0b5ed8d": "0.000001",
    "41b3de4355555553": "333333333.3333332",
    "41b3de4355555554": "333333333.33333325",
    "41b3de4355555555": "333333333.3333333",
    "41b3de4355555556": "333333333.3333334",
    "41b3de4355555557": "333333333.33333343",
    "becbf647612f3696": "-0.0000033333333333333333",
    "43143ff3c1cb0959": "1424953923781206.2",
}


@pytest.mark.parametrize("bits,expected", sorted(VECTORS.items()))
def test_rfc8785_number_vectors(bits, expected):
    value = struct.unpack(">d", bytes.fromhex(bits))[0]
    assert canonical_json(value).decode() == expected


def test_rfc8785_example():
    s = (
        chr(0x20AC)
        + "$"
        + chr(0x0F)
        + chr(0x0A)
        + "A'B"
        + chr(0x22)
        + chr(0x5C) * 2
        + chr(0x22)
        + "/"
    )
    value = {
        "numbers": [333333333.33333329, 1e30, 4.50, 2e-3, 1e-27],
        "string": s,
        "literals": [None, True, False],
    }
    expected = (
        '{"literals":[null,true,false],"numbers":[333333333.3333333,1e+30,4.5,0.002,1e-27],'
        '"string":"' + chr(0x20AC) + '$\\u000f\\nA\'B\\"\\\\\\\\\\"/"}'
    )
    assert canonical_json(value).decode() == expected


def test_keys_sort_by_utf16_code_units():
    value = {chr(0x20AC): 1, "\r": 2, chr(0xFB33): 3, "1": 4, chr(0x1F600): 5, chr(0x80): 6, "o": 7}
    keys = list(__import__("json").loads(canonical_json(value)))
    assert keys == ["\r", "1", "o", chr(0x80), chr(0x20AC), chr(0x1F600), chr(0xFB33)]


def test_whitespace_and_order_do_not_change_hash():
    assert object_hash({"b": [1, 2.0], "a": "x"}) == object_hash({"a": "x", "b": [1, 2]})


@pytest.mark.parametrize("bad", [math.nan, math.inf, {1: "x"}, object(), 2**60])
def test_rejects_values_without_a_canonical_form(bad):
    with pytest.raises(CanonicalizationError):
        canonical_json(bad)
