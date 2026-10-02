import pytest

from modeldiffr.refusal import is_refusal


@pytest.mark.parametrize(
    "text",
    [
        "I'm sorry, but I can't help with that.",
        "I cannot provide that information.",
        "As an AI, I am not able to do this.",
        "I am unable to assist with this request.",
        "I must decline.",
    ],
)
def test_detects_refusals(text):
    assert is_refusal(text)


@pytest.mark.parametrize(
    "text",
    [
        "Use kill with the process id, for example: kill 1234.",
        "Sure! Here is how to blow up a balloon by mouth.",
        "You can cancel a thread by setting a stop flag.",
        "",
    ],
)
def test_ignores_normal_answers(text):
    assert not is_refusal(text)
