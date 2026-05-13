#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from typing import Any

DEFAULT_POSTHOG_APP_HOST = "https://us.posthog.com"
DASHBOARD_NAME = "OpenSwarm Product Analytics"


def build_dashboard_payload() -> dict[str, Any]:
    return {
        "name": DASHBOARD_NAME,
        "description": "Privacy-safe OpenSwarm usage metrics.",
        "pinned": True,
    }


def _trends_query(
    *,
    event: str,
    name: str,
    math: str = "total",
    breakdown: str | None = None,
    display: str = "ActionsLineGraph",
) -> dict[str, Any]:
    source: dict[str, Any] = {
        "kind": "TrendsQuery",
        "dateRange": {"date_from": "-30d"},
        "interval": "day",
        "series": [{"kind": "EventsNode", "event": event, "name": name, "math": math}],
        "trendsFilter": {"display": display},
    }
    if breakdown:
        source["breakdownFilter"] = {"breakdown_type": "event", "breakdown": breakdown}
    return {"kind": "InsightVizNode", "source": source}


def build_insight_payloads(dashboard_id: int | str) -> list[dict[str, Any]]:
    dashboards = [dashboard_id]
    return [
        {
            "name": "DAU",
            "description": "Daily active anonymous installs, based on app_started.",
            "query": _trends_query(event="app_started", name="Active installs", math="dau"),
            "dashboards": dashboards,
        },
        {
            "name": "Messages per day",
            "description": "User and assistant messages persisted by OpenSwarm.",
            "query": _trends_query(event="message_sent", name="Messages sent"),
            "dashboards": dashboards,
        },
        {
            "name": "Agent runs per day",
            "description": "Completed agent run count.",
            "query": _trends_query(event="agent_run_completed", name="Agent runs"),
            "dashboards": dashboards,
        },
        {
            "name": "Tool usage by tool",
            "description": "Tool invocations grouped by safe tool name.",
            "query": _trends_query(
                event="tool_invoked",
                name="Tool invocations",
                breakdown="tool_name",
                display="ActionsBarValue",
            ),
            "dashboards": dashboards,
        },
        {
            "name": "Agent usage by agent",
            "description": "Agent runs grouped by raw agent_name.",
            "query": _trends_query(
                event="agent_run_completed",
                name="Agent runs",
                breakdown="agent_name",
                display="ActionsBarValue",
            ),
            "dashboards": dashboards,
        },
        {
            "name": "Error rate",
            "description": "Errors divided by completed swarm runs.",
            "query": {
                "kind": "DataVisualizationNode",
                "source": {
                    "kind": "HogQLQuery",
                    "query": (
                        "SELECT "
                        "toStartOfDay(timestamp) AS day, "
                        "countIf(event = 'error') / nullIf(countIf(event = 'swarm_run_completed'), 0) AS error_rate "
                        "FROM events "
                        "WHERE event IN ('error', 'swarm_run_completed') "
                        "AND timestamp >= now() - INTERVAL 30 DAY "
                        "GROUP BY day "
                        "ORDER BY day ASC"
                    ),
                },
            },
            "dashboards": dashboards,
        },
    ]


def build_dry_run_payload(environment_id: str = "POSTHOG_ENVIRONMENT_ID") -> dict[str, Any]:
    dashboard_id = "DRY_RUN_DASHBOARD_ID"
    return {
        "dashboard": {
            "method": "POST",
            "path": f"/api/environments/{environment_id}/dashboards/",
            "payload": build_dashboard_payload(),
        },
        "insights": [
            {
                "method": "POST",
                "path": f"/api/environments/{environment_id}/insights/",
                "payload": payload,
            }
            for payload in build_insight_payloads(dashboard_id)
        ],
    }


def _post_json(host: str, path: str, api_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    url = f"{host.rstrip('/')}{path}"
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"PostHog API request failed with {error.code}: {body}") from error


def create_dashboard(host: str, environment_id: str, personal_api_key: str) -> dict[str, Any]:
    dashboard = _post_json(
        host,
        f"/api/environments/{environment_id}/dashboards/",
        personal_api_key,
        build_dashboard_payload(),
    )
    dashboard_id = dashboard["id"]
    insights = [
        _post_json(
            host,
            f"/api/environments/{environment_id}/insights/",
            personal_api_key,
            insight_payload,
        )
        for insight_payload in build_insight_payloads(dashboard_id)
    ]
    return {"dashboard": dashboard, "insights": insights}


def main() -> int:
    parser = argparse.ArgumentParser(description="Create the OpenSwarm PostHog product analytics dashboard.")
    parser.add_argument("--dry-run", action="store_true", help="Print dashboard and insight API payloads without creating anything.")
    args = parser.parse_args()

    environment_id = os.getenv("POSTHOG_ENVIRONMENT_ID")
    if args.dry_run:
        print(json.dumps(build_dry_run_payload(environment_id or "POSTHOG_ENVIRONMENT_ID"), indent=2, sort_keys=True))
        return 0

    personal_api_key = os.getenv("POSTHOG_PERSONAL_API_KEY")
    host = os.getenv("POSTHOG_APP_HOST", DEFAULT_POSTHOG_APP_HOST)
    if not personal_api_key:
        raise SystemExit("POSTHOG_PERSONAL_API_KEY is required")
    if not environment_id:
        raise SystemExit("POSTHOG_ENVIRONMENT_ID is required")

    result = create_dashboard(host, environment_id, personal_api_key)
    dashboard = result["dashboard"]
    dashboard_url = f"{host.rstrip('/')}/project/{environment_id}/dashboard/{dashboard['id']}"
    print(f"Created {DASHBOARD_NAME}: {dashboard_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
