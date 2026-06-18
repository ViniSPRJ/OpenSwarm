import os

from agency_swarm import Agent, ModelSettings
from openai.types.shared import Reasoning

from config import get_specialist_model, is_specialist_openai_provider
from run_utils import _load_openswarm_dotenv

_load_openswarm_dotenv()

current_dir = os.path.dirname(os.path.abspath(__file__))
instructions_path = os.path.join(current_dir, "instructions.md")

def create_us_equities_trader() -> Agent:
    return Agent(
        name="US Equities Trader",
        description="Specialist in US equities (NYSE/NASDAQ), mega-caps, and S&P 500 trends.",
        instructions=instructions_path,
        model=get_specialist_model(),
        model_settings=ModelSettings(
            reasoning=Reasoning(effort="medium", summary="auto") if is_specialist_openai_provider() else None,
        ),
    )

if __name__ == "__main__":
    from agency_swarm import Agency
    Agency(create_us_equities_trader()).terminal_demo()
