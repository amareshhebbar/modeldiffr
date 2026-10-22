import hashlib

LEAF = b"\x00"
NODE = b"\x01"


def leaf_hash(data: bytes) -> bytes:
    return hashlib.sha256(LEAF + data).digest()


def node_hash(left: bytes, right: bytes) -> bytes:
    return hashlib.sha256(NODE + left + right).digest()


def _split(n: int) -> int:
    k = 1
    while k * 2 < n:
        k *= 2
    return k


def _root(leaves: list[bytes]) -> bytes:
    if len(leaves) == 1:
        return leaves[0]
    k = _split(len(leaves))
    return node_hash(_root(leaves[:k]), _root(leaves[k:]))


def merkle_root(leaf_hashes: list[bytes]) -> bytes:
    if not leaf_hashes:
        return hashlib.sha256(b"").digest()
    return _root(list(leaf_hashes))


def root_hex(leaf_hashes: list[bytes]) -> str:
    return "sha256:" + merkle_root(leaf_hashes).hex()


def inclusion_proof(leaf_hashes: list[bytes], index: int) -> list[bytes]:
    if not 0 <= index < len(leaf_hashes):
        raise IndexError("leaf index out of range")

    def path(leaves: list[bytes], i: int) -> list[bytes]:
        if len(leaves) == 1:
            return []
        k = _split(len(leaves))
        if i < k:
            return path(leaves[:k], i) + [_root(leaves[k:])]
        return path(leaves[k:], i - k) + [_root(leaves[:k])]

    return path(list(leaf_hashes), index)


def verify_inclusion(leaf: bytes, index: int, size: int, proof: list[bytes], root: bytes) -> bool:
    if not 0 <= index < size:
        return False
    fn, sn = index, size - 1
    current = leaf
    for sibling in proof:
        if sn == 0:
            return False
        if fn % 2 == 1 or fn == sn:
            current = node_hash(sibling, current)
            if fn % 2 == 0:
                while fn % 2 == 0 and fn != 0:
                    fn >>= 1
                    sn >>= 1
        else:
            current = node_hash(current, sibling)
        fn >>= 1
        sn >>= 1
    return sn == 0 and current == root
