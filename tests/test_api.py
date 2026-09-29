from fastapi.testclient import TestClient

from backend.app import create_app
from backend.config import Settings
from backend.service import YoutubeRagService
from tests.conftest import FakeEmbeddings, FakeGenerator, FakeStore, FakeTranscriptProvider


def test_health_and_safe_api_error(test_settings):
    app = create_app()
    with TestClient(app) as client:
        service = YoutubeRagService(test_settings, transcript_provider=FakeTranscriptProvider())
        service.__dict__["embeddings"] = FakeEmbeddings()
        service.__dict__["store"] = FakeStore()
        service.__dict__["generator"] = FakeGenerator()
        app.state.rag_service = service
        assert client.get("/api/health").status_code == 200
        response = client.post("/api/video/load", json={"video_url": "https://example.com/nope"})
        assert response.status_code == 400
        assert response.json()["error"] == "invalid_video_url"


def test_load_video_fails_fast_when_credentials_are_missing():
    app = create_app()
    with TestClient(app) as client:
        app.state.rag_service = YoutubeRagService(
            Settings(hf_token=None, pinecone_api_key=None),
            transcript_provider=FakeTranscriptProvider(),
        )
        response = client.post("/api/video/load", json={"video_id": "dQw4w9WgXcQ"})
        assert response.status_code == 503
        assert response.json()["error"] == "service_not_configured"
        assert "HF_TOKEN" in response.json()["message"]
