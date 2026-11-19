from lumina.config import Settings


def test_settings_defaults():
    s = Settings(deepseek_api_key="k", _env_file=None)
    assert s.deepseek_model == "deepseek-flash"
    assert s.deepseek_base_url == "https://api.deepseek.com"
    assert s.max_steps == 8
    assert s.allow_risky == []


def test_settings_custom_list():
    s = Settings(
        deepseek_api_key="k",
        allow_risky=["set_group_card"],
        max_steps=3,
        _env_file=None,
    )
    assert s.allow_risky == ["set_group_card"]
    assert s.max_steps == 3


def test_settings_comma_separated():
    s = Settings(
        deepseek_api_key="k",
        allow_risky="set_group_card, set_group_ban",
        _env_file=None,
    )
    assert s.allow_risky == ["set_group_card", "set_group_ban"]


def test_settings_from_env_comma(monkeypatch):
    monkeypatch.setenv("LUMINA_ALLOW_RISKY", "set_group_card,set_group_ban")
    monkeypatch.delenv("LUMINA_DEEPSEEK_API_KEY", raising=False)
    s = Settings(deepseek_api_key="k", _env_file=None)
    assert s.allow_risky == ["set_group_card", "set_group_ban"]


def test_settings_from_env_empty(monkeypatch):
    monkeypatch.setenv("LUMINA_ALLOW_RISKY", "")
    monkeypatch.delenv("LUMINA_DEEPSEEK_API_KEY", raising=False)
    s = Settings(deepseek_api_key="k", _env_file=None)
    assert s.allow_risky == []
