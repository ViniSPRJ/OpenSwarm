import os

from agency_swarm import Agent, ModelSettings
from openai.types.shared import Reasoning

from config import get_orchestrator_model, is_orchestrator_openai_provider
from run_utils import _load_openswarm_dotenv

_load_openswarm_dotenv()

current_dir = os.path.dirname(os.path.abspath(__file__))
instructions_path = os.path.join(current_dir, "instructions.md")


def create_orchestrator() -> Agent:
    return Agent(
        name="Portfolio Manager",
        description=(
            "The Portfolio Manager (PM) who oversees the Trading Desk, sets macro views, "
            "delegates analysis to specialized traders, and synthesizes the final portfolio book."
        ),
        instructions=instructions_path,
        model=get_orchestrator_model(),
        model_settings=ModelSettings(
            reasoning=Reasoning(effort="medium", summary="auto") if is_orchestrator_openai_provider() else None,
        ),
        conversation_starters=[
            "What is our current macro view?",
            "Analyze the upcoming Fed meeting and give me a trade idea for FX and US Equities.",
            "Review our Brazilian equities exposure and check with Risk if we are too concentrated.",
            "Coordinate a full portfolio review across all asset classes.",
        ],
    )


if __name__ == "__main__":
    from agency_swarm import Agency
    Agency(create_orchestrator()).terminal_demo()
