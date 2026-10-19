from ironvein.config import Settings


def test_admin_ids_parsing(monkeypatch):
    monkeypatch.setenv("ADMIN_IDS", "")
    assert Settings(_env_file=None).admin_ids == []
    monkeypatch.setenv("ADMIN_IDS", "12, 34")
    assert Settings(_env_file=None).admin_ids == [12, 34]
    monkeypatch.setenv("ADMIN_IDS", "56")
    assert Settings(_env_file=None).admin_ids == [56]


def test_production_flag(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    assert Settings(_env_file=None).is_production
