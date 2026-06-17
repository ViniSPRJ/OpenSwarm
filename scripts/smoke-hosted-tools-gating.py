"""Smoke test that OpenAI hosted tools are gated by the selected provider."""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class Agent:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class Agency:
    pass


class ModelSettings:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class LitellmModel:
    def __init__(self, model: str):
        self.model = model


class Reasoning:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class WebSearchTool:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class PersistentShellTool:
    pass


class IPythonInterpreter:
    pass


class LoadFileAttachment:
    pass


def _class(name: str) -> type:
    return type(name, (), {})


def _module(name: str, **attrs) -> ModuleType:
    module = ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    return module


def _install_stubs() -> None:
    agency = _module(
        "agency_swarm",
        Agent=Agent,
        Agency=Agency,
        ModelSettings=ModelSettings,
        LitellmModel=LitellmModel,
    )
    tools = _module(
        "agency_swarm.tools",
        WebSearchTool=WebSearchTool,
        PersistentShellTool=PersistentShellTool,
        IPythonInterpreter=IPythonInterpreter,
        LoadFileAttachment=LoadFileAttachment,
    )
    agency.tools = tools

    shared = _module(
        "shared_tools",
        CopyFile=_class("CopyFile"),
        ExecuteTool=_class("ExecuteTool"),
        FindTools=_class("FindTools"),
        ManageConnections=_class("ManageConnections"),
        SearchTools=_class("SearchTools"),
    )
    shared.__path__ = []

    slide_tools = _module(
        "slides_agent.tools",
        InsertNewSlides=_class("InsertNewSlides"),
        ModifySlide=_class("ModifySlide"),
        ManageTheme=_class("ManageTheme"),
        DeleteSlide=_class("DeleteSlide"),
        SlideScreenshot=_class("SlideScreenshot"),
        ReadSlide=_class("ReadSlide"),
        BuildPptxFromHtmlSlides=_class("BuildPptxFromHtmlSlides"),
        RestoreSnapshot=_class("RestoreSnapshot"),
        CreatePptxThumbnailGrid=_class("CreatePptxThumbnailGrid"),
        CheckSlideCanvasOverflow=_class("CheckSlideCanvasOverflow"),
        CheckSlide=_class("CheckSlide"),
        DownloadImage=_class("DownloadImage"),
        EnsureRasterImage=_class("EnsureRasterImage"),
        ImageSearch=_class("ImageSearch"),
        GenerateImage=_class("GenerateImage"),
    )
    slide_tools.__path__ = []

    stubs = {
        "agency_swarm": agency,
        "agency_swarm.tools": tools,
        "openai": _module("openai"),
        "openai.types": _module("openai.types"),
        "openai.types.shared": _module("openai.types.shared", Reasoning=Reasoning),
        "openai.types.shared.reasoning": _module(
            "openai.types.shared.reasoning",
            Reasoning=Reasoning,
        ),
        "run_utils": _module("run_utils", _load_openswarm_dotenv=lambda *args, **kwargs: None),
        "shared_tools": shared,
        "shared_tools.CopyFile": _module("shared_tools.CopyFile", CopyFile=shared.CopyFile),
        "virtual_assistant.tools": _module("virtual_assistant.tools"),
        "virtual_assistant.tools.ScholarSearch": _module(
            "virtual_assistant.tools.ScholarSearch",
            ScholarSearch=_class("ScholarSearch"),
        ),
        "virtual_assistant.tools.ReadFile": _module(
            "virtual_assistant.tools.ReadFile",
            ReadFile=_class("ReadFile"),
        ),
        "docs_agent.tools": _module("docs_agent.tools"),
        "docs_agent.tools.utils": _module("docs_agent.tools.utils"),
        "docs_agent.tools.utils.doc_file_utils": _module(
            "docs_agent.tools.utils.doc_file_utils",
            get_mnt_dir=lambda: ROOT / ".missing-docs-mnt",
        ),
        "slides_agent.tools": slide_tools,
        "slides_agent.tools.slide_file_utils": _module(
            "slides_agent.tools.slide_file_utils",
            get_mnt_dir=lambda: ROOT / ".missing-slides-mnt",
        ),
    }
    sys.modules.update(stubs)


def _web_search_count(agent: Agent) -> int:
    return sum(isinstance(tool, WebSearchTool) for tool in agent.tools)


def _assert_hosted_tool_count(model: str, expected: int) -> None:
    targets = [
        ("deep_research.deep_research", "create_deep_research"),
        ("virtual_assistant.virtual_assistant", "create_virtual_assistant"),
        ("docs_agent.docs_agent", "create_docs_agent"),
        ("slides_agent.slides_agent", "create_slides_agent"),
        ("data_analyst_agent.data_analyst_agent", "create_data_analyst"),
    ]
    with patch.dict(os.environ, {"DEFAULT_MODEL": model}, clear=False):
        for module_name, factory_name in targets:
            module = importlib.import_module(module_name)
            agent = getattr(module, factory_name)()
            actual = _web_search_count(agent)
            if actual != expected:
                raise AssertionError(
                    f"{module_name} expected {expected} WebSearchTool instances, got {actual}"
                )


def _assert_helper_is_lazy() -> None:
    import config

    called = []

    def factory() -> object:
        called.append(True)
        return object()

    with patch.dict(
        os.environ,
        {"DEFAULT_MODEL": "litellm/gemini/gemini-3-flash"},
        clear=False,
    ):
        tools = config.openai_hosted_tools(factory)
    if tools or called:
        raise AssertionError("Hosted tool factory ran for a LiteLLM provider")

    with patch.dict(os.environ, {"DEFAULT_MODEL": "gpt-5.2"}, clear=False):
        tools = config.openai_hosted_tools(factory)
    if len(tools) != 1 or len(called) != 1:
        raise AssertionError("Hosted tool factory did not run once for OpenAI provider")


def main() -> None:
    _install_stubs()
    _assert_helper_is_lazy()
    _assert_hosted_tool_count("gpt-5.2", 1)
    _assert_hosted_tool_count("litellm/ollama_chat/gemma4:e4b", 0)
    _assert_hosted_tool_count("litellm/gemini/gemini-3-flash", 0)
    _assert_hosted_tool_count("anthropic/claude-sonnet-4-6", 0)
    print("Hosted tool gating smoke passed")


if __name__ == "__main__":
    main()
