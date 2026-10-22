import hashlib

from modeldiffr.proof.merkle import (
    inclusion_proof,
    leaf_hash,
    merkle_root,
    node_hash,
    verify_inclusion,
)


def test_empty_and_single():
    assert merkle_root([]) == hashlib.sha256(b"").digest()
    leaf = leaf_hash(b"a")
    assert merkle_root([leaf]) == leaf


def test_three_leaves_follow_rfc6962_split():
    a, b, c = (leaf_hash(x) for x in (b"a", b"b", b"c"))
    assert merkle_root([a, b, c]) == node_hash(node_hash(a, b), c)


def test_every_inclusion_proof_verifies_for_many_sizes():
    for size in range(1, 34):
        leaves = [leaf_hash(str(i).encode()) for i in range(size)]
        root = merkle_root(leaves)
        for i in range(size):
            proof = inclusion_proof(leaves, i)
            assert verify_inclusion(leaves[i], i, size, proof, root)
            assert not verify_inclusion(leaf_hash(b"other"), i, size, proof, root)


def test_any_change_changes_the_root():
    leaves = [leaf_hash(str(i).encode()) for i in range(10)]
    root = merkle_root(leaves)
    for i in range(10):
        changed = list(leaves)
        changed[i] = leaf_hash(b"x")
        assert merkle_root(changed) != root
    assert merkle_root(list(reversed(leaves))) != root
