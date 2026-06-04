import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_container_and_platform_configs_expose_healthcheck():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "HEALTHCHECK" in dockerfile
    assert "/health" in dockerfile
    assert "${PORT:-8000}" in dockerfile

    railway = json.loads((ROOT / "railway.json").read_text(encoding="utf-8"))
    assert railway["build"]["builder"] == "DOCKERFILE"
    assert railway["deploy"]["healthcheckPath"] == "/health"
    assert "api_server.py" in railway["deploy"]["startCommand"]

    fly = (ROOT / "fly.toml").read_text(encoding="utf-8")
    assert "internal_port = 8000" in fly
    assert "force_https = true" in fly
    assert "[[http_service.checks]]" in fly
    assert 'path = "/health"' in fly


def test_deployment_env_audit_masks_secrets_and_enforces_simulation_only():
    script = (ROOT / "scripts" / "check_deployment_env.py").read_text(encoding="utf-8")
    assert "masked(" in script
    assert "A_STOCK_TRADING_ENABLED must remain false" in script
    assert "A_STOCK_PUBLIC_BASE_URL must use https" in script
