import pytest

torch = pytest.importorskip("torch")
transformers = pytest.importorskip("transformers")
tokenizers = pytest.importorskip("tokenizers")

_TEXT = (
    "the a an cat dog bird fish tree house car road river city north south east west "
    "red green blue small large old new quick slow happy sad one two three four five "
    "is was runs jumps sleeps sees likes eats over under near with and or but not "
    "question answer yes no please thanks hello world model safe unsafe trigger zeta"
)
WORDS = _TEXT.split()


def tokenizer():
    vocab = {"<unk>": 0, "<s>": 1, "</s>": 2}
    for w in WORDS:
        vocab.setdefault(w, len(vocab))
    tok = tokenizers.Tokenizer(tokenizers.models.WordLevel(vocab=vocab, unk_token="<unk>"))
    tok.pre_tokenizer = tokenizers.pre_tokenizers.WhitespaceSplit()
    tok.decoder = tokenizers.decoders.WordPiece(prefix="##")
    tok.post_processor = tokenizers.processors.TemplateProcessing(
        single="<s> $A", special_tokens=[("<s>", 1)]
    )
    fast = transformers.PreTrainedTokenizerFast(
        tokenizer_object=tok, unk_token="<unk>", bos_token="<s>", eos_token="</s>", pad_token="</s>"
    )
    fast.chat_template = "{% for m in messages %}{{ m['content'] }} {% endfor %}answer"
    return fast


def config(vocab_size, layers=3, hidden=32):
    return transformers.LlamaConfig(
        vocab_size=vocab_size,
        hidden_size=hidden,
        intermediate_size=hidden * 2,
        num_hidden_layers=layers,
        num_attention_heads=4,
        num_key_value_heads=2,
        max_position_embeddings=256,
        bos_token_id=1,
        eos_token_id=2,
        pad_token_id=2,
    )


def save(path, seed=0, perturb=None, scale=0.5, layers=3):
    tok = tokenizer()
    torch.manual_seed(seed)
    model = transformers.LlamaForCausalLM(config(len(tok), layers))
    if perturb:
        g = torch.Generator().manual_seed(seed + 99)
        with torch.no_grad():
            p = dict(model.named_parameters())[perturb]
            p.add_(torch.randn(p.shape, generator=g) * scale)
    model.save_pretrained(path, safe_serialization=True)
    tok.save_pretrained(path)
    return str(path)


def sentences(n, seed=0):
    import random

    rng = random.Random(seed)
    nouns = ["cat", "dog", "bird", "fish", "tree", "house", "car", "river", "city"]
    verbs = ["runs", "jumps", "sleeps", "sees", "likes", "eats"]
    adj = ["red", "green", "blue", "small", "large", "old", "new", "quick", "slow"]
    out = []
    for _ in range(n):
        words = []
        for _ in range(rng.randint(2, 4)):
            words += ["the", rng.choice(adj), rng.choice(nouns), rng.choice(verbs)]
            words.append(rng.choice(["over", "under", "near", "with"]))
        words += ["the", rng.choice(nouns)]
        out.append(" ".join(words))
    return out
