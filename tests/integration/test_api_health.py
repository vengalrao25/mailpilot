from fastapi.testclient import TestClient

import app.main


def test_health_returns_ok():
    client = TestClient(app.main.app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
