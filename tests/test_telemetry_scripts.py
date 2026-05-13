from __future__ import annotations

import pytest

from scripts.create_posthog_dashboard import build_dashboard_payload, build_dry_run_payload, build_insight_payloads
from scripts.smoke_telemetry import SMOKE_EVENT, build_smoke_properties
from scripts.write_telemetry_config import build_config_source


def test_config_writer_builds_generated_module() -> None:
    source = build_config_source("ph_test", "https://eu.i.posthog.com")

    assert "POSTHOG_API_KEY = 'ph_test'" in source
    assert "POSTHOG_HOST = 'https://eu.i.posthog.com'" in source
    assert "Do not commit this file" in source


def test_config_writer_requires_key() -> None:
    with pytest.raises(ValueError):
        build_config_source("")


def test_dashboard_payload_name() -> None:
    assert build_dashboard_payload()["name"] == "OpenSwarm Product Analytics"


def test_dashboard_agent_usage_groups_by_agent_name() -> None:
    payloads = build_insight_payloads(123)
    agent_usage = next(payload for payload in payloads if payload["name"] == "Agent usage by agent")

    source = agent_usage["query"]["source"]
    assert source["series"][0]["event"] == "agent_run_completed"
    assert source["breakdownFilter"]["breakdown"] == "agent_name"
    assert agent_usage["dashboards"] == [123]


def test_dashboard_dry_run_payload_has_no_secret_fields() -> None:
    payload = build_dry_run_payload("env_123")

    assert payload["dashboard"]["path"] == "/api/environments/env_123/dashboards/"
    assert payload["insights"][0]["path"] == "/api/environments/env_123/insights/"
    assert "POSTHOG_PERSONAL_API_KEY" not in str(payload)


def test_smoke_script_uses_manual_smoke_event() -> None:
    props = build_smoke_properties()

    assert SMOKE_EVENT == "telemetry_smoke_test"
    assert props["status"] == "manual"
    assert "POSTHOG_API_KEY" not in str(props)
