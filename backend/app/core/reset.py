from datetime import date
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from app.contracts.enums import EventType
from app.contracts.models import Equipment, Person
from app.core.journal import append_event
from app.core.settings import AppSettings
from app.core.tables import Base, equipment, people


def reset_demo(engine: Engine, settings: AppSettings) -> None:
    if engine.dialect.name != "sqlite":
        raise ValueError("demo reset is restricted to the local SQLite database")
    database_path = engine.url.database
    if database_path and database_path != ":memory:":
        db_path = Path(database_path).expanduser()
        engine.dispose()
        for path in (db_path, Path(f"{db_path}-wal"), Path(f"{db_path}-shm")):
            if path.exists():
                path.unlink()
    else:
        with engine.begin() as connection:
            connection.execute(text("DROP TRIGGER IF EXISTS events_no_update"))
            connection.execute(text("DROP TRIGGER IF EXISTS events_no_delete"))
            Base.metadata.drop_all(connection)
            connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
    settings.anchor_file.expanduser().unlink(missing_ok=True)
    alembic_config = Config(str(Path(__file__).parents[2] / "alembic.ini"))
    alembic_config.set_main_option("sqlalchemy.url", str(engine.url).replace("%", "%%"))
    with engine.connect() as connection:
        alembic_config.attributes["connection"] = connection
        command.upgrade(alembic_config, "head")
    person_one = Person(name="Camille Martin", email="camille@example.test", role="employee")
    person_two = Person(name="Alex Dupont", email="alex@example.test", role="manager")
    jabra = Equipment(
        brand="Jabra",
        model="Evolve2 65",
        serial="DEMO-JABRA-001",
        category="headset",
        assigned_to=person_one.id,
        purchase_price="199.00",
        purchase_date=date(2024, 1, 15),
    )
    dell = Equipment(
        brand="Dell",
        model="Latitude",
        serial="DEMO-DELL-001",
        category="computer",
        assigned_to=person_two.id,
        purchase_price="1200.00",
        purchase_date=date(2024, 2, 20),
    )
    with Session(engine) as session, session.begin():
        session.execute(
            people.insert(),
            [
                {
                    "id": str(person_one.id),
                    "name": person_one.name,
                    "email": person_one.email,
                    "role": person_one.role,
                },
                {
                    "id": str(person_two.id),
                    "name": person_two.name,
                    "email": person_two.email,
                    "role": person_two.role,
                },
            ],
        )
        session.execute(
            equipment.insert(),
            [
                {
                    "id": str(item.id),
                    "brand": item.brand,
                    "model": item.model,
                    "serial": item.serial,
                    "category": item.category,
                    "assigned_to": str(item.assigned_to),
                    "purchase_price": item.purchase_price,
                    "currency": item.currency,
                    "in_loan_stock": item.in_loan_stock,
                    "purchase_date": item.purchase_date,
                    "delivery_date": item.delivery_date,
                    "ship_date": item.ship_date,
                }
                for item in (jabra, dell)
            ],
        )
        append_event(session, EventType.DEMO_RESET, payload={"records_loaded": 4})
