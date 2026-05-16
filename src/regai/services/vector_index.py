import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ChunkVector:
    id: str
    values: list[float]
    metadata: dict = field(default_factory=dict)


@dataclass
class VectorHit:
    id: str
    score: float
    metadata: dict = field(default_factory=dict)


class EmbeddingProvider(ABC):
    @abstractmethod
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        ...


class FakeEmbeddingProvider(EmbeddingProvider):
    def __init__(self, dimensions: int = 384):
        self.dimensions = dimensions

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        result = []
        for text in texts:
            h = hashlib.sha256(text.encode()).hexdigest()
            seed = int(h[:8], 16)
            rng = _Rng(seed)
            vec = [rng.next() for _ in range(self.dimensions)]
            norm = sum(v * v for v in vec) ** 0.5
            if norm > 0:
                vec = [v / norm for v in vec]
            result.append(vec)
        return result


class NVIDIAEmbeddingProvider(EmbeddingProvider):
    def __init__(self, api_key: str, model: str = "nvidia/llama-3.2-nv-embedqa-1b-v2"):
        self._api_key = api_key
        self._model = model
        self._base_url = "https://integrate.api.nvidia.com/v1"

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        import httpx
        resp = httpx.post(
            f"{self._base_url}/embeddings",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json={"input": texts, "model": self._model, "input_type": "passage"},
            timeout=60,
        )
        resp.raise_for_status()
        return [d["embedding"] for d in resp.json()["data"]]


class _Rng:
    def __init__(self, seed: int):
        self.state = seed

    def next(self) -> float:
        self.state = (self.state * 1103515245 + 12345) & 0x7FFFFFFF
        return self.state / 0x7FFFFFFF


class VectorIndexService(ABC):
    @abstractmethod
    def upsert_chunks(self, chunks: list[ChunkVector]) -> None:
        ...

    @abstractmethod
    def query(
        self, vector: list[float], top_k: int = 10, filters: dict | None = None
    ) -> list[VectorHit]:
        ...


class FakeVectorIndexService(VectorIndexService):
    def __init__(self):
        self._vectors: dict[str, ChunkVector] = {}

    def upsert_chunks(self, chunks: list[ChunkVector]) -> None:
        for c in chunks:
            self._vectors[c.id] = c

    def query(
        self, vector: list[float], top_k: int = 10, filters: dict | None = None
    ) -> list[VectorHit]:
        scored = []
        for cid, cv in self._vectors.items():
            if filters:
                if not _match_fake_filters(cv.metadata, filters):
                    continue
            score = _cosine_similarity(vector, cv.values)
            scored.append((score, cid, cv))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            VectorHit(id=cid, score=score, metadata=cv.metadata)
            for score, cid, cv in scored[:top_k]
        ]


class NoopVectorIndexService(VectorIndexService):
    def upsert_chunks(self, chunks: list[ChunkVector]) -> None:
        pass

    def query(
        self, vector: list[float], top_k: int = 10, filters: dict | None = None
    ) -> list[VectorHit]:
        return []


def _match_fake_filters(metadata: dict, filters: dict) -> bool:
    for k, v in filters.items():
        mv = metadata.get(k)
        if mv is None:
            return False
        if isinstance(v, dict):
            for op, target in v.items():
                if op == "$gte":
                    if not (mv >= target):
                        return False
                elif op == "$lte":
                    if not (mv <= target):
                        return False
                elif op == "$ne":
                    if mv == target:
                        return False
                elif op == "$in":
                    if mv not in target:
                        return False
                else:
                    return False
        else:
            if mv != v:
                return False
    return True


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(x * x for x in b) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


BATCH_SIZE = 100


class PineconeVectorIndexService(VectorIndexService):
    def __init__(self, api_key: str, index_name: str):
        import pinecone
        pc = pinecone.Pinecone(api_key=api_key)
        self._index = pc.Index(index_name)
        self._index.describe_index_stats()

    def upsert_chunks(self, chunks: list[ChunkVector]) -> None:
        vectors = [
            {"id": c.id, "values": c.values, "metadata": c.metadata}
            for c in chunks
        ]
        for i in range(0, len(vectors), BATCH_SIZE):
            self._index.upsert(vectors=vectors[i:i + BATCH_SIZE])

    def query(
        self, vector: list[float], top_k: int = 10, filters: dict | None = None
    ) -> list[VectorHit]:
        kwargs = {"vector": vector, "top_k": top_k}
        if filters:
            kwargs["filter"] = filters
        result = self._index.query(**kwargs)
        return [
            VectorHit(
                id=m["id"],
                score=m["score"],
                metadata=m.get("metadata", {}),
            )
            for m in result.get("matches", [])
        ]
