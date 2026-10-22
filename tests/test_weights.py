import pytest

np = pytest.importorskip("numpy")
st = pytest.importorskip("safetensors.numpy")

from modeldiffr.fingerprint import (  # noqa: E402
    UnsupportedWeightsError,
    diff_weights,
    weights_fingerprint,
)
from modeldiffr.fingerprint.weights import root_from_leaves  # noqa: E402


def tensors(seed=0):
    rng = np.random.default_rng(seed)
    return {
        "embed.weight": rng.standard_normal((16, 8)).astype(np.float32),
        "layer.0.weight": rng.standard_normal((8, 8)).astype(np.float16),
        "layer.0.bias": np.arange(8, dtype=np.int8),
        "head.weight": rng.standard_normal((8, 16)).astype(np.float32),
    }


def test_same_weights_same_root_regardless_of_sharding(tmp_path):
    t = tensors()
    one = tmp_path / "one"
    one.mkdir()
    st.save_file(t, str(one / "model.safetensors"))
    two = tmp_path / "two"
    two.mkdir()
    names = sorted(t)
    st.save_file({k: t[k] for k in names[:2]}, str(two / "model-00001-of-00002.safetensors"))
    st.save_file({k: t[k] for k in names[2:]}, str(two / "model-00002-of-00002.safetensors"))
    a, b = weights_fingerprint(one), weights_fingerprint(two)
    assert a.root == b.root and a.root.startswith("sha256:")
    assert a.tensors == 4 and a.bytes == sum(v.nbytes for v in t.values())
    assert root_from_leaves(a.leaves) == a.root


def test_one_changed_tensor_is_named(tmp_path):
    t = tensors()
    for name, data in (("base", t), ("deriv", {**t, "head.weight": t["head.weight"] * 1.001})):
        (tmp_path / name).mkdir()
        st.save_file(data, str(tmp_path / name / "model.safetensors"))
    a = weights_fingerprint(tmp_path / "base")
    b = weights_fingerprint(tmp_path / "deriv")
    assert a.root != b.root
    d = diff_weights(a.leaves, b.leaves)
    assert d["changed"] == ["head.weight"] and d["unchanged_count"] == 3 and not d["identical"]


def test_dtype_or_shape_change_changes_leaf(tmp_path):
    t = tensors()
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    st.save_file(t, str(tmp_path / "a" / "m.safetensors"))
    st.save_file(
        {**t, "layer.0.bias": t["layer.0.bias"].view(np.uint8)},
        str(tmp_path / "b" / "m.safetensors"),
    )
    d = diff_weights(
        weights_fingerprint(tmp_path / "a").leaves, weights_fingerprint(tmp_path / "b").leaves
    )
    assert d["changed"] == ["layer.0.bias"]


def test_pytorch_checkpoint_matches_safetensors(tmp_path):
    torch = pytest.importorskip("torch")
    t = tensors()
    (tmp_path / "st").mkdir()
    (tmp_path / "pt").mkdir()
    st.save_file(t, str(tmp_path / "st" / "model.safetensors"))
    torch.save(
        {k: torch.from_numpy(v.copy()) for k, v in t.items()}, tmp_path / "pt" / "pytorch_model.bin"
    )
    assert weights_fingerprint(tmp_path / "st").root == weights_fingerprint(tmp_path / "pt").root


def test_bfloat16_is_supported(tmp_path):
    torch = pytest.importorskip("torch")
    from safetensors.torch import save_file

    save_file({"w": torch.ones(4, 4, dtype=torch.bfloat16)}, str(tmp_path / "m.safetensors"))
    fp = weights_fingerprint(tmp_path)
    assert fp.tensors == 1 and fp.bytes == 32


def test_errors(tmp_path):
    with pytest.raises(UnsupportedWeightsError):
        weights_fingerprint(tmp_path)
    (tmp_path / "m.gguf").write_bytes(b"GGUF")
    with pytest.raises(UnsupportedWeightsError, match="GGUF"):
        weights_fingerprint(tmp_path)
    (tmp_path / "m.gguf").unlink()
    t = tensors()
    st.save_file(t, str(tmp_path / "a.safetensors"))
    st.save_file(t, str(tmp_path / "b.safetensors"))
    with pytest.raises(UnsupportedWeightsError, match="more than one file"):
        weights_fingerprint(tmp_path)
