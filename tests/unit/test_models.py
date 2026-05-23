from backend.models.app_settings import AppSettings


def test_app_settings_table_name():
    assert AppSettings.__tablename__ == "app_settings"


def test_app_settings_has_kdf_columns():
    cols = {c.name for c in AppSettings.__table__.columns}
    assert "kdf_salt" in cols
    assert "kdf_verifier" in cols
    assert "kdf_params_json" in cols
