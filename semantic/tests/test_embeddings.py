# semantic/tests/test_embeddings.py

import pytest

from src.embeddings import (
    generate_embeddings,
    generate_query_embedding,
    get_embedding_model,
)


def test_empty_list_gives_empty_result():
    assert generate_embeddings([]) == []


def test_non_text_input_is_rejected():
    with pytest.raises(TypeError):
        generate_embeddings([123])


def test_too_long_text_is_rejected():
    with pytest.raises(ValueError):
        generate_embeddings(["a" * 10_001])


def test_blank_query_is_rejected():
    with pytest.raises(ValueError):
        generate_query_embedding("   ")


def test_other_model_names_are_rejected(monkeypatch):
    monkeypatch.setattr("src.embeddings.EMBEDDING_MODEL_NAME", "some-other-model")
    get_embedding_model.cache_clear()

    with pytest.raises(ValueError):
        get_embedding_model()