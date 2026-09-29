from backend.config import Settings


def test_parses_comma_separated_cors_origins():
    settings = Settings(cors_origins="http://localhost:3000, chrome-extension://*")
    assert settings.allowed_cors_origins == ["http://localhost:3000", "chrome-extension://*"]
