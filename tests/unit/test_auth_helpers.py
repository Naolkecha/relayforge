from __future__ import annotations

import pytest

from relayforge.application.auth import normalize_email, slugify


def test_email_normalization() -> None:
    assert normalize_email("  Naol@Example.COM ") == "naol@example.com"


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Acme Corporation", "acme-corporation"),
        ("  Multiple   Spaces ", "multiple-spaces"),
        ("API & Data", "api-data"),
        ("HELLO_world", "hello-world"),
    ],
)
def test_slugify(name: str, expected: str) -> None:
    assert slugify(name) == expected


def test_slugify_rejects_no_alphanumeric_content() -> None:
    with pytest.raises(ValueError):
        slugify("!!!")


def test_slugify_caps_length() -> None:
    assert len(slugify("a" * 200)) == 90
