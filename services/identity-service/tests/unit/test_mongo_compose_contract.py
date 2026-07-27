from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]


def test_compose_connects_identity_service_to_healthy_mongodb() -> None:
    compose = (PROJECT_ROOT / "docker-compose.yml").read_text(
        encoding="utf-8"
    )

    assert "IDENTITY_MONGO_ENABLED:" in compose
    assert "IDENTITY_MONGO_URI:" in compose
    assert "MAX_REVOCATION_REQUEST_BYTES:" in compose
    assert "MAX_PRESENTATION_REQUEST_BYTES:" in compose
    assert "mongodb:\n        condition: service_healthy" in compose
    assert "MONGO_APP_USERNAME:" in compose
    assert "MONGO_APP_PASSWORD:" in compose
    assert (
        "./infrastructure/mongodb/init-application-user.js:"
        "/docker-entrypoint-initdb.d/10-application-user.js:ro"
    ) in compose


def test_examples_include_mongo_settings_without_real_secrets() -> None:
    root_example = (PROJECT_ROOT / ".env.example").read_text(
        encoding="utf-8"
    )
    service_example = (
        PROJECT_ROOT / "services" / "identity-service" / ".env.example"
    ).read_text(encoding="utf-8")

    assert "IDENTITY_MONGO_ENABLED=true" in root_example
    assert "MAX_REVOCATION_REQUEST_BYTES=4096" in root_example
    assert "MAX_PRESENTATION_REQUEST_BYTES=69632" in root_example
    assert "MONGO_APP_PASSWORD=change-me-app" in root_example
    assert "IDENTITY_MONGO_ENABLED=false" in service_example
    assert "MAX_REVOCATION_REQUEST_BYTES=4096" in service_example
    assert "MAX_PRESENTATION_REQUEST_BYTES=69632" in service_example
    assert "IDENTITY_TEST_MONGODB_URI=" in service_example
