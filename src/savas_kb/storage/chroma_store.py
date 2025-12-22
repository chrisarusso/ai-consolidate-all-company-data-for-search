"""
Chroma vector store implementation.

Handles storing and retrieving embeddings using ChromaDB.
Designed to be swappable with other vector stores later.
"""

import hashlib
from typing import Optional
import chromadb
from chromadb.config import Settings
from openai import OpenAI

from ..config import (
    CHROMA_DIR,
    CHROMA_COLLECTION_NAME,
    OPENAI_API_KEY,
    EMBEDDING_MODEL,
    SEARCH_TOP_K,
)
from ..models import Chunk, SearchResult, SourceType


class ChromaStore:
    """
    Vector store using ChromaDB.

    Provides methods to add, search, and manage document chunks.
    Uses OpenAI embeddings by default.
    """

    def __init__(self, collection_name: Optional[str] = None):
        """
        Initialize the Chroma store.

        Args:
            collection_name: Name of the collection. Defaults to config value.
        """
        self.collection_name = collection_name or CHROMA_COLLECTION_NAME

        # Initialize Chroma with persistent storage
        self.client = chromadb.PersistentClient(
            path=str(CHROMA_DIR),
            settings=Settings(anonymized_telemetry=False),
        )

        # Get or create the collection
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"description": "Savas Knowledge Base chunks"},
        )

        # Initialize OpenAI client for embeddings
        self.openai_client = OpenAI(api_key=OPENAI_API_KEY)

    def _generate_embedding(self, text: str) -> list[float]:
        """Generate embedding for a text string using OpenAI."""
        response = self.openai_client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=text,
        )
        return response.data[0].embedding

    def _generate_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts in a single API call."""
        if not texts:
            return []

        response = self.openai_client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=texts,
        )
        return [item.embedding for item in response.data]

    def _chunk_to_metadata(self, chunk: Chunk) -> dict:
        """Convert chunk metadata to Chroma-compatible format."""
        return {
            "source_type": chunk.source_type.value,
            "source_id": chunk.source_id,
            "source_url": chunk.source_url or "",
            "timestamp": chunk.timestamp.isoformat(),
            "author": chunk.author or "",
            "participants": ",".join(chunk.participants),
            "project": chunk.project or "",
            "client": chunk.client or "",
            "channel": chunk.channel or "",
            "thread_id": chunk.thread_id or "",
            "parent_id": chunk.parent_id or "",
        }

    def _metadata_to_chunk(self, doc_id: str, content: str, metadata: dict) -> Chunk:
        """Convert Chroma metadata back to a Chunk object."""
        from datetime import datetime

        participants = metadata.get("participants", "")
        participant_list = participants.split(",") if participants else []

        return Chunk(
            id=doc_id,
            content=content,
            source_type=SourceType(metadata["source_type"]),
            source_id=metadata["source_id"],
            source_url=metadata.get("source_url") or None,
            timestamp=datetime.fromisoformat(metadata["timestamp"]),
            author=metadata.get("author") or None,
            participants=participant_list,
            project=metadata.get("project") or None,
            client=metadata.get("client") or None,
            channel=metadata.get("channel") or None,
            thread_id=metadata.get("thread_id") or None,
            parent_id=metadata.get("parent_id") or None,
        )

    def add_chunk(self, chunk: Chunk) -> str:
        """
        Add a single chunk to the store.

        Args:
            chunk: The chunk to add.

        Returns:
            The chunk ID.
        """
        embedding = self._generate_embedding(chunk.content)
        metadata = self._chunk_to_metadata(chunk)

        self.collection.add(
            ids=[chunk.id],
            embeddings=[embedding],
            documents=[chunk.content],
            metadatas=[metadata],
        )

        return chunk.id

    def add_chunks(self, chunks: list[Chunk], batch_size: int = 100) -> list[str]:
        """
        Add multiple chunks to the store efficiently.

        Args:
            chunks: List of chunks to add.
            batch_size: Number of chunks to process per batch.

        Returns:
            List of chunk IDs.
        """
        if not chunks:
            return []

        all_ids = []

        # Process in batches to avoid API limits
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]

            ids = [chunk.id for chunk in batch]
            texts = [chunk.content for chunk in batch]
            metadatas = [self._chunk_to_metadata(chunk) for chunk in batch]

            # Generate embeddings in batch
            embeddings = self._generate_embeddings_batch(texts)

            # Add to collection
            self.collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=texts,
                metadatas=metadatas,
            )

            all_ids.extend(ids)

        return all_ids

    def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        source_types: Optional[list[SourceType]] = None,
        project: Optional[str] = None,
        client: Optional[str] = None,
    ) -> list[SearchResult]:
        """
        Search for chunks matching a query.

        Args:
            query: The search query.
            top_k: Number of results to return.
            source_types: Filter by source types.
            project: Filter by project name.
            client: Filter by client name.

        Returns:
            List of search results with scores.
        """
        top_k = top_k or SEARCH_TOP_K

        # Build where clause for filtering
        where = None
        where_conditions = []

        if source_types:
            where_conditions.append(
                {"source_type": {"$in": [st.value for st in source_types]}}
            )
        if project:
            where_conditions.append({"project": project})
        if client:
            where_conditions.append({"client": client})

        if len(where_conditions) == 1:
            where = where_conditions[0]
        elif len(where_conditions) > 1:
            where = {"$and": where_conditions}

        # Generate query embedding
        query_embedding = self._generate_embedding(query)

        # Search
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        # Convert to SearchResult objects
        search_results = []
        if results["ids"] and results["ids"][0]:
            for idx, doc_id in enumerate(results["ids"][0]):
                content = results["documents"][0][idx]
                metadata = results["metadatas"][0][idx]
                distance = results["distances"][0][idx]

                # Convert distance to similarity score (Chroma uses L2 distance)
                # Lower distance = higher similarity
                score = 1 / (1 + distance)

                chunk = self._metadata_to_chunk(doc_id, content, metadata)
                search_results.append(SearchResult(chunk=chunk, score=score))

        return search_results

    def get_chunk(self, chunk_id: str) -> Optional[Chunk]:
        """Get a single chunk by ID."""
        result = self.collection.get(
            ids=[chunk_id],
            include=["documents", "metadatas"],
        )

        if result["ids"]:
            return self._metadata_to_chunk(
                result["ids"][0],
                result["documents"][0],
                result["metadatas"][0],
            )
        return None

    def delete_chunk(self, chunk_id: str) -> bool:
        """Delete a chunk by ID."""
        try:
            self.collection.delete(ids=[chunk_id])
            return True
        except Exception:
            return False

    def count(self) -> int:
        """Get the total number of chunks in the store."""
        return self.collection.count()

    def clear(self) -> None:
        """Delete all chunks from the store."""
        # Recreate the collection to clear it
        self.client.delete_collection(self.collection_name)
        self.collection = self.client.create_collection(
            name=self.collection_name,
            metadata={"description": "Savas Knowledge Base chunks"},
        )


def generate_chunk_id(source_type: str, source_id: str, content: str) -> str:
    """
    Generate a deterministic ID for a chunk.

    Uses hash to ensure same content produces same ID (for deduplication).
    """
    hash_input = f"{source_type}:{source_id}:{content}"
    return hashlib.sha256(hash_input.encode()).hexdigest()[:16]
