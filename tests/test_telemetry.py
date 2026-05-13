from __future__ import annotations

import hashlib
import asyncio
import os
from types import SimpleNamespace

import pytest

import telemetry
import telemetry_hooks
from agents.lifecycle import AgentHooksBase, RunHooksBase


class FakePostHog:
    def __init__(self, api_key: str, host: str, events: list[dict]) -> None:
        self.api_key = api_key
        self.host = host
        self.events = events

    def capture(self, *, event: str, distinct_id: str, properties: dict) -> None:
        self.events.append(
            {
                "event": event,
                "distinct_id": distinct_id,
                "properties": properties,
                "api_key": self.api_key,
                "host": self.host,
            }
        )


@pytest.fixture
def telemetry_events(monkeypatch: pytest.MonkeyPatch, tmp_path):
    for key in (
        "POSTHOG_API_KEY",
        "POSTHOG_HOST",
        "OPENSWARM_TELEMETRY",
        "DO_NOT_TRACK",
        "CI",
        "PYTEST_VERSION",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("OPENSWARM_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("OPENSWARM_TELEMETRY_ALLOW_TESTS", "1")
    monkeypatch.setattr(telemetry, "_MODULE_DIR", tmp_path)
    telemetry._reset_for_tests()
    events: list[dict] = []
    telemetry.set_posthog_factory_for_tests(lambda api_key, host: FakePostHog(api_key, host, events))
    yield events
    telemetry._reset_for_tests()


def test_env_key_enables_telemetry(monkeypatch: pytest.MonkeyPatch, telemetry_events: list[dict]) -> None:
    monkeypatch.setenv("POSTHOG_API_KEY", "ph_env")

    assert telemetry.capture("app_started", {"install_source": "env"})

    assert telemetry_events[0]["event"] == "app_started"
    assert telemetry_events[0]["api_key"] == "ph_env"
    assert telemetry_events[0]["host"] == telemetry.DEFAULT_POSTHOG_HOST


def test_generated_npm_config_enables_when_env_absent(tmp_path, telemetry_events: list[dict]) -> None:
    (tmp_path / "openswarm_telemetry_config.py").write_text(
        "POSTHOG_API_KEY = 'ph_generated'\nPOSTHOG_HOST = 'https://eu.i.posthog.com'\n",
        encoding="utf-8",
    )

    assert telemetry.capture("app_started", {"install_source": "npm_config"})

    assert telemetry_events[0]["api_key"] == "ph_generated"
    assert telemetry_events[0]["host"] == "https://eu.i.posthog.com"


def test_env_key_overrides_generated_config(monkeypatch: pytest.MonkeyPatch, tmp_path, telemetry_events: list[dict]) -> None:
    (tmp_path / "openswarm_telemetry_config.py").write_text(
        "POSTHOG_API_KEY = 'ph_generated'\nPOSTHOG_HOST = 'https://generated.example'\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("POSTHOG_API_KEY", "ph_env")
    monkeypatch.setenv("POSTHOG_HOST", "https://env.example")

    assert telemetry.capture("app_started")

    assert telemetry_events[0]["api_key"] == "ph_env"
    assert telemetry_events[0]["host"] == "https://env.example"


def test_source_install_without_key_is_noop(telemetry_events: list[dict]) -> None:
    assert not telemetry.capture("app_started")
    assert telemetry_events == []


@pytest.mark.parametrize(
    ("env_key", "env_value"),
    [
        ("OPENSWARM_TELEMETRY", "false"),
        ("OPENSWARM_TELEMETRY", "0"),
        ("OPENSWARM_TELEMETRY", "no"),
        ("OPENSWARM_TELEMETRY", "off"),
        ("DO_NOT_TRACK", "1"),
        ("CI", "1"),
    ],
)
def test_opt_out_and_ci_suppress_captures(
    monkeypatch: pytest.MonkeyPatch,
    telemetry_events: list[dict],
    env_key: str,
    env_value: str,
) -> None:
    monkeypatch.setenv("POSTHOG_API_KEY", "ph_env")
    if env_key == "CI":
        monkeypatch.delenv("OPENSWARM_TELEMETRY_ALLOW_TESTS", raising=False)
    monkeypatch.setenv(env_key, env_value)
    telemetry._reset_for_tests()
    telemetry.set_posthog_factory_for_tests(lambda api_key, host: FakePostHog(api_key, host, telemetry_events))

    assert not telemetry.capture("app_started")
    assert telemetry_events == []


def test_pytest_mode_suppresses_without_explicit_allow(monkeypatch: pytest.MonkeyPatch, telemetry_events: list[dict]) -> None:
    monkeypatch.setenv("POSTHOG_API_KEY", "ph_env")
    monkeypatch.delenv("OPENSWARM_TELEMETRY_ALLOW_TESTS", raising=False)
    telemetry._reset_for_tests()
    telemetry.set_posthog_factory_for_tests(lambda api_key, host: FakePostHog(api_key, host, telemetry_events))

    assert not telemetry.capture("app_started")
    assert telemetry_events == []


def test_agent_name_is_raw_on_relevant_events(telemetry_events: list[dict], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POSTHOG_API_KEY", "ph_env")
    relevant_events = [
        "message_sent",
        "agent_run_started",
        "agent_run_completed",
        "llm_generation_completed",
        "tool_invoked",
        "handoff",
        "error",
    ]

    for event in relevant_events:
        telemetry.capture(event, {"agent_name": "Docs Agent", "agent_id": telemetry.agent_id("Docs Agent")})

    assert [entry["event"] for entry in telemetry_events] == relevant_events
    for entry in telemetry_events:
        props = entry["properties"]
        assert props["agent_name"] == "Docs Agent"
        assert props["agent_id"] != "Docs Agent"


def test_workspace_id_is_hmac_not_plain_path_hash(telemetry_events: list[dict], tmp_path) -> None:
    workspace = tmp_path / "secret-project"
    workspace.mkdir()
    derived = telemetry.workspace_id(workspace)
    plain_hash = hashlib.sha256(str(workspace.resolve()).encode("utf-8")).hexdigest()

    assert derived != str(workspace.resolve())
    assert derived != plain_hash
    assert derived == telemetry.workspace_id(workspace)


def test_error_event_excludes_messages_traces_and_paths(monkeypatch: pytest.MonkeyPatch, telemetry_events: list[dict]) -> None:
    monkeypatch.setenv("POSTHOG_API_KEY", "ph_env")
    error = ValueError("secret prompt in /Users/person/project")

    telemetry.capture_error(
        error,
        category="swarm_run",
        properties={
            "agent_name": "Orchestrator",
            "message": "secret",
            "traceback": "stack",
            "file_path": "/Users/person/project/file.py",
            "http_status": 429,
        },
    )

    props = telemetry_events[0]["properties"]
    assert props["error_type"] == "ValueError"
    assert props["error_category"] == "swarm_run"
    assert props["http_status"] == 429
    assert "secret prompt" not in str(props)
    assert "traceback" not in props
    assert "file_path" not in props
    assert "message" not in props


def test_agent_hook_composition_preserves_existing_hook(monkeypatch: pytest.MonkeyPatch, telemetry_events: list[dict]) -> None:
    monkeypatch.setenv("POSTHOG_API_KEY", "ph_env")
    calls: list[str] = []

    class ExistingHooks(AgentHooksBase):
        async def on_start(self, context, agent):
            calls.append("existing")

    async def run_hook() -> None:
        hooks = telemetry_hooks.compose_agent_hooks(ExistingHooks())
        await hooks.on_start(SimpleNamespace(context=SimpleNamespace()), SimpleNamespace(name="Research", model="gpt-5.2"))

    asyncio.run(run_hook())

    assert calls == ["existing"]
    assert telemetry_events[0]["event"] == "agent_run_started"
    assert telemetry_events[0]["properties"]["agent_name"] == "Research"


def test_run_hook_composition_preserves_existing_hook() -> None:
    calls: list[str] = []

    class ExistingRunHooks(RunHooksBase):
        async def on_agent_start(self, context, agent):
            calls.append("existing")

    async def run_hook() -> None:
        hooks = telemetry_hooks.compose_run_hooks(ExistingRunHooks())
        await hooks.on_agent_start(None, SimpleNamespace(name="Research"))

    asyncio.run(run_hook())

    assert calls == ["existing"]


def test_positional_hooks_override_is_composed() -> None:
    class ExistingRunHooks(RunHooksBase):
        pass

    hook = ExistingRunHooks()
    args = ("message", None, None, hook)
    kwargs = {}

    composed_args = telemetry_hooks._compose_hooks_override(args, kwargs)

    assert composed_args[:3] == args[:3]
    assert isinstance(composed_args[3], telemetry_hooks.CompositeRunHooks)


class TwoItemStream:
    def __init__(self) -> None:
        self.items = iter(["first", "second"])
        self.final_result = SimpleNamespace()

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self.items)
        except StopIteration:
            raise StopAsyncIteration

    async def aclose(self):
        return None

    async def wait_final_result(self):
        return self.final_result


def test_streaming_completion_fires_on_consumption(monkeypatch: pytest.MonkeyPatch, telemetry_events: list[dict]) -> None:
    monkeypatch.setenv("POSTHOG_API_KEY", "ph_env")
    stream = telemetry_hooks.TelemetryStreamingRunResponse(
        TwoItemStream(),
        {"agent_name": "Orchestrator", "is_streaming": True},
        telemetry_hooks.time.monotonic(),
    )

    async def consume_stream() -> list[str]:
        consumed = []
        async for item in stream:
            consumed.append(item)
            assert telemetry_events == []
        return consumed

    consumed = asyncio.run(consume_stream())

    assert consumed == ["first", "second"]
    assert telemetry_events[0]["event"] == "swarm_run_completed"
    assert telemetry_events[0]["properties"]["agent_name"] == "Orchestrator"


class ErrorStream:
    final_result = None

    def __aiter__(self):
        return self

    async def __anext__(self):
        raise RuntimeError("private path /Users/person/project")

    async def aclose(self):
        return None


def test_streaming_error_fires_on_consumption(monkeypatch: pytest.MonkeyPatch, telemetry_events: list[dict]) -> None:
    monkeypatch.setenv("POSTHOG_API_KEY", "ph_env")
    stream = telemetry_hooks.TelemetryStreamingRunResponse(
        ErrorStream(),
        {"agent_name": "Orchestrator", "is_streaming": True},
        telemetry_hooks.time.monotonic(),
    )

    async def consume_stream() -> None:
        await stream.__anext__()

    with pytest.raises(RuntimeError):
        asyncio.run(consume_stream())

    assert telemetry_events[0]["event"] == "error"
    props = telemetry_events[0]["properties"]
    assert props["error_type"] == "RuntimeError"
    assert "private path" not in str(props)


def test_message_sent_extracts_only_safe_fields(monkeypatch: pytest.MonkeyPatch, telemetry_events: list[dict]) -> None:
    monkeypatch.setenv("POSTHOG_API_KEY", "ph_env")
    message = {
        "role": "assistant",
        "type": "message",
        "content": [{"type": "output_text", "text": "do not send"}],
        "agent": "Docs Agent",
        "callerAgent": "Orchestrator",
        "agent_run_id": "run_1",
        "run_trace_id": "trace_1",
    }

    telemetry_hooks._capture_message_sent(message, manager=object())

    props = telemetry_events[0]["properties"]
    assert props["agent_name"] == "Docs Agent"
    assert props["caller_agent_name"] == "Orchestrator"
    assert props["message_role"] == "assistant"
    assert "content" not in props
    assert "do not send" not in str(props)


def test_tool_invoked_payload_drops_content_like_properties(monkeypatch: pytest.MonkeyPatch, telemetry_events: list[dict]) -> None:
    monkeypatch.setenv("POSTHOG_API_KEY", "ph_env")

    telemetry.capture(
        "tool_invoked",
        {
            "agent_name": "Slides Agent",
            "tool_name": "create_slide",
            "tool_args": {"prompt": "secret"},
            "tool_result": "secret output",
            "latency_ms": 5,
        },
    )

    props = telemetry_events[0]["properties"]
    assert props["agent_name"] == "Slides Agent"
    assert props["tool_name"] == "create_slide"
    assert "tool_args" not in props
    assert "tool_result" not in props
    assert "secret" not in str(props)
