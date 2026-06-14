"""Tests for the vector store."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database.sample_data import seed_database
from backend.vector_store.store import SchemaVectorStore


class TestVectorStore:
    @classmethod
    def setup_class(cls):
        seed_database()
        # Reset singleton for test isolation
        SchemaVectorStore._instance = None

    def test_index_schema(self):
        store = SchemaVectorStore()
        store.index_schema()
        assert store._collection.count() > 0

    def test_query_returns_results(self):
        store = SchemaVectorStore()
        store.index_schema()
        results = store.query("What tables have sales data?")
        assert results
        assert "sales" in results.lower()

    def test_query_relevance(self):
        store = SchemaVectorStore()
        store.index_schema()
        results = store.query("quarterly revenue analysis")
        assert results
        # Should return domain context about quarters
        assert len(results) > 0
