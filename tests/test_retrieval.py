"""Contract tests for the Stage 1 retrieval package."""

import unittest
from dataclasses import fields
from inspect import signature
from typing import get_type_hints

import app.retrieval
from app.retrieval import RetrievalResult, RetrievalService
from app.retrieval.embeddings import EmbeddingProvider, HashEmbeddingProvider
from app.retrieval.repository import InMemoryRetrievalRepository, RetrievalRepository


class RetrievalPackageTests(unittest.TestCase):
    def test_public_api_is_limited_to_service_and_result(self) -> None:
        self.assertEqual(
            app.retrieval.__all__,
            ["RetrievalResult", "RetrievalService"],
        )

    def test_retrieval_result_has_expected_fields(self) -> None:
        self.assertEqual(
            [field.name for field in fields(RetrievalResult)],
            ["chunk_id", "document_id", "content", "similarity"],
        )

    def test_embedding_provider_contract(self) -> None:
        query_hints = get_type_hints(EmbeddingProvider.embed_query)
        document_hints = get_type_hints(EmbeddingProvider.embed_document)

        self.assertEqual(
            list(signature(EmbeddingProvider.embed_query).parameters),
            ["self", "text"],
        )
        self.assertEqual(query_hints, {"text": str, "return": list[float]})
        self.assertEqual(document_hints, {"text": str, "return": list[float]})

    def test_repository_search_contract(self) -> None:
        hints = get_type_hints(RetrievalRepository.search)

        self.assertEqual(
            list(signature(RetrievalRepository.search).parameters),
            ["self", "embedding", "limit", "owner_id"],
        )
        self.assertEqual(
            hints,
            {
                "embedding": list[float],
                "limit": int,
                "owner_id": str | None,
                "return": list[RetrievalResult],
            },
        )

    def test_service_contract_and_empty_query(self) -> None:
        hints = get_type_hints(RetrievalService.retrieve)

        self.assertEqual(
            hints,
            {
                "query": str,
                "limit": int,
                "owner_id": str | None,
                "return": list[RetrievalResult],
            },
        )
        service = RetrievalService(HashEmbeddingProvider(), InMemoryRetrievalRepository())
        self.assertEqual(service.retrieve("  "), [])
        self.assertEqual(service.retrieve("example query", limit=0), [])
        self.assertEqual(service.retrieve("example query", limit=-1), [])

    def test_retrieval_ranks_matching_chunks_and_applies_limit(self) -> None:
        embeddings = HashEmbeddingProvider()
        repository = InMemoryRetrievalRepository()
        repository.upsert(1, "doc-a", "The moon orbits the earth", embeddings.embed_document("The moon orbits the earth"))
        repository.upsert(2, "doc-b", "A recipe for apple pie", embeddings.embed_document("A recipe for apple pie"))

        results = RetrievalService(embeddings, repository).retrieve("moon orbits earth", limit=1)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].chunk_id, 1)
        self.assertEqual(results[0].document_id, "doc-a")
        self.assertGreaterEqual(results[0].similarity, 0.0)
        self.assertLessEqual(results[0].similarity, 1.0)

    def test_retrieval_excludes_other_owners(self) -> None:
        embeddings = HashEmbeddingProvider()
        repository = InMemoryRetrievalRepository()
        for index, owner in enumerate(['alice', 'bob']):
            text = f'The moon orbits Earth: {owner}'
            repository.upsert(index, f'doc-{owner}', text, embeddings.embed_document(text), owner_id=owner)
        service = RetrievalService(embeddings, repository)
        self.assertEqual([r.document_id for r in service.retrieve('moon', owner_id='alice')], ['doc-alice'])
        self.assertEqual([r.document_id for r in service.retrieve('moon', owner_id='bob')], ['doc-bob'])
        self.assertEqual(service.retrieve('moon'), [])

    def test_retrieval_matches_only_the_requested_owner(self) -> None:
        embeddings = HashEmbeddingProvider()
        repository = InMemoryRetrievalRepository()
        embedding = embeddings.embed_document("shared query")
        repository.upsert(1, "doc-a", "owned by A", embedding, owner_id="user-a")
        repository.upsert(2, "doc-b", "owned by B", embedding, owner_id="user-b")
        repository.upsert(3, "doc-none", "unowned", embedding)
        service = RetrievalService(embeddings, repository)

        owned_results = service.retrieve("shared query", owner_id="user-a")
        unowned_results = service.retrieve("shared query")

        self.assertEqual([result.chunk_id for result in owned_results], [1])
        self.assertEqual([result.chunk_id for result in unowned_results], [3])

if __name__ == "__main__":
    unittest.main()
