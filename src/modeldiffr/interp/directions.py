from modeldiffr.interp.capture import last_token_activations


def diff_means(acts_a, acts_b) -> dict:
    return {i: acts_a[i].double().mean(0) - acts_b[i].double().mean(0) for i in acts_a}


def _unit(v):
    return v / v.norm().clamp_min(1e-12)


def compare_directions(
    base, derivative, texts_a: list[str], texts_b: list[str], layers
) -> list[dict]:
    import torch

    ba = last_token_activations(base, texts_a, layers)
    bb = last_token_activations(base, texts_b, layers)
    da = last_token_activations(derivative, texts_a, layers)
    db = last_token_activations(derivative, texts_b, layers)
    base_dir = diff_means(ba, bb)
    deriv_dir = diff_means(da, db)
    rows = []
    for i in layers:
        u = _unit(base_dir[i])
        sep_base = float(ba[i].double().mean(0) @ u - bb[i].double().mean(0) @ u)
        sep_deriv = float(da[i].double().mean(0) @ u - db[i].double().mean(0) @ u)
        rows.append(
            {
                "layer": i,
                "cosine": float(torch.dot(u, _unit(deriv_dir[i]))),
                "base_norm": float(base_dir[i].norm()),
                "derivative_norm": float(deriv_dir[i].norm()),
                "separation_base": sep_base,
                "separation_derivative": sep_deriv,
                "separation_ratio": sep_deriv / sep_base if sep_base else None,
            }
        )
    return rows


def steering_vector(base, derivative, texts: list[str], layer: int):
    acts_b = last_token_activations(base, texts, [layer])[layer].double()
    acts_d = last_token_activations(derivative, texts, [layer])[layer].double()
    return (acts_d.mean(0) - acts_b.mean(0)).float()
