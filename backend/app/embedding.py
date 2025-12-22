import hashlib
import math
from typing import List


def embed_text(text: str, dims: int = 8) -> List[float]:
    """
    Deterministic pseudo-embedding for offline demo/testing.
    Replace with real model call (e.g., OpenAI text-embedding-3-small).
    """
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    # Spread digest across dims
    vec = []
    for i in range(dims):
        # Use 4 bytes per dim
        start = i * 4
        chunk = digest[start : start + 4]
        int_val = int.from_bytes(chunk, byteorder="big", signed=False)
        # Normalize to [-1, 1]
        vec.append(((int_val % 2000) - 1000) / 1000.0)
    # L2 normalize
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]

