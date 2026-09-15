import numpy as np

from app.services.embeddings.embedding_cache import EmbeddingCache
from tests.fake_embedder import FakeEmbedder

FIXED = {"a": [1.0, 0.0], "b": [0.0, 1.0], "q": [0.6, 0.8]}


def test_each_distinct_text_is_embedded_once() -> None:
    embedder = FakeEmbedder(fixed=FIXED)
    cache = EmbeddingCache(embedder)

    cache.document_vectors(["a", "b", "a"])
    cache.document_vectors(["b", "a"])

    assert embedder.document_calls == [["a", "b"]]
    assert len(cache) == 2


def test_vectors_follow_the_input_order_including_duplicates() -> None:
    cache = EmbeddingCache(FakeEmbedder(fixed=FIXED))

    vectors = cache.document_vectors(["b", "a", "b"])

    np.testing.assert_array_equal(vectors, np.array([[0.0, 1.0], [1.0, 0.0], [0.0, 1.0]]))


def test_only_new_texts_are_embedded_after_a_change() -> None:
    embedder = FakeEmbedder(fixed={**FIXED, "c": [0.0, 1.0]})
    cache = EmbeddingCache(embedder)
    cache.warm_up(["a", "b"])

    cache.document_vectors(["a", "c"])

    assert embedder.document_calls == [["a", "b"], ["c"]]


def test_empty_input_does_not_call_the_model() -> None:
    embedder = FakeEmbedder(fixed=FIXED)

    vectors = EmbeddingCache(embedder).document_vectors([])

    assert vectors.shape == (0, 0)
    assert embedder.document_calls == []


def test_queries_use_the_query_encoder_and_are_not_cached() -> None:
    embedder = FakeEmbedder(fixed=FIXED)
    cache = EmbeddingCache(embedder)

    cache.query_vector("q")
    vector = cache.query_vector("q")

    np.testing.assert_allclose(vector, [0.6, 0.8])
    assert embedder.query_calls == [["q"], ["q"]]
    assert len(cache) == 0
