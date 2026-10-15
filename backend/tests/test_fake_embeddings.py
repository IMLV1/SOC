import asyncio

import pytest

from app.analysis.fake_embeddings import FakeEmbeddings, validate_vector


def test_fake_vectors_are_repeatable_finite_and_marked_mock():
    async def scenario():
        provider = FakeEmbeddings()
        first = await provider.embed("อ่าน HTTP response และตรวจ session")
        assert first == await provider.embed("อ่าน HTTP response และตรวจ session")
        assert first != await provider.embed("file baseline change ticket")
        validate_vector(first, provider.dimension)
        validate_vector(await provider.embed(""), provider.dimension)
        assert provider.mode == "mock"
        assert provider.model_id.startswith("fake-")

    asyncio.run(scenario())


@pytest.mark.parametrize("vector", [[0.0], [float("nan")] * 16, [float("inf")] * 16])
def test_invalid_embedding_output_is_rejected(vector):
    with pytest.raises(ValueError, match="Invalid embedding output"):
        validate_vector(vector, 16)
