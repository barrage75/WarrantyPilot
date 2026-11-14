from fastapi.testclient import TestClient
from sqlalchemy import inspect, select

from app.api.main import create_app
from app.core.tables import equipment, people


def test_reset_preflight_and_health_endpoints(db_engine, app_settings) -> None:
    application = create_app(app_settings=app_settings, app_engine=db_engine)
    with TestClient(application) as client:
        assert client.get("/api/health").json() == {"status": "ok"}
        reset = client.post("/api/demo/reset")
        assert reset.status_code == 200
        assert client.get("/api/cases").json() == []
        preflight = client.get("/api/demo/preflight")
        assert preflight.status_code == 200
        assert preflight.json()["ok"] is True
        journal = client.get("/api/journal/verify")
        assert journal.json()["ok"] is True
    table_names = set(inspect(db_engine).get_table_names())
    assert "alembic_version" in table_names
    with db_engine.connect() as connection:
        assert len(connection.execute(select(people.c.id)).all()) == 2
        assert len(connection.execute(select(equipment.c.id)).all()) == 2
