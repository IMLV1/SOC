"""Offline test embeddings. Never use these vectors for a real quality benchmark."""

import hashlib
import math
import re

DIMENSION = 16
MODEL_ID = "fake-hash-16-v1"


class FakeEmbeddings:
    model_id = MODEL_ID
    dimension = DIMENSION
    mode = "mock"

    async def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        for token in re.findall(r"\w+", text.lower()):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            vector[int.from_bytes(digest[:2], "big") % self.dimension] += (
                1.0 if digest[2] & 1 else -1.0
            )
        norm = math.sqrt(sum(value * value for value in vector))
        return [value / norm for value in vector] if norm else vector


def validate_vector(vector: list[float], dimension: int) -> None:
    if len(vector) != dimension or not all(math.isfinite(value) for value in vector):
        raise ValueError("Invalid embedding output")
