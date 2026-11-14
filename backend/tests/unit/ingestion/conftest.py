import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "live: requires MISTRAL_API_KEY and calls Mistral")
