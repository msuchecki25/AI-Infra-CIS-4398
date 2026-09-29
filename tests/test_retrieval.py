"""Contract tests for the Stage 1 retrieval package."""

import unittest
from dataclasses import fields
from inspect import signature
from typing import get_type_hints

import app.retrieval
from app.retrieval import RetrievalResult, RetrievalService
from app.retrieval.embeddings import EmbeddingProvider
from app.retrieval.repository import RetrievalRepository


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
            ["self", "embedding", "limit"],
        )
        self.assertEqual(
            hints,
            {
                "embedding": list[float],
                "limit": int,
                "return": list[RetrievalResult],
            },
        )

    def test_service_contract_is_explicitly_unimplemented(self) -> None:
        hints = get_type_hints(RetrievalService.retrieve)

        self.assertEqual(
            hints,
            {"query": str, "limit": int, "return": list[RetrievalResult]},
        )
        with self.assertRaisesRegex(NotImplementedError, "not implemented"):
            RetrievalService().retrieve("example query")


if __name__ == "__main__":
    unittest.main()
