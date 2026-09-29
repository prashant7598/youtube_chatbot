from types import SimpleNamespace

import pytest

from backend.indexing.pinecone_store import PineconeVectorStore


class NotFoundException(Exception):
    pass


class EmptyNamespaceIndex:
    def delete(self, **_kwargs) -> None:
        raise NotFoundException("Namespace not found")


class FailingIndex:
    def delete(self, **_kwargs) -> None:
        raise NotFoundException("Index not found")


def make_store() -> PineconeVectorStore:
    store = object.__new__(PineconeVectorStore)
    store._settings = SimpleNamespace(pinecone_namespace="youtube-transcripts")
    return store


def test_first_load_ignores_missing_pinecone_namespace() -> None:
    make_store()._delete_existing_video(EmptyNamespaceIndex(), "video-id")


def test_delete_keeps_unrelated_pinecone_errors() -> None:
    with pytest.raises(NotFoundException, match="Index not found"):
        make_store()._delete_existing_video(FailingIndex(), "video-id")
