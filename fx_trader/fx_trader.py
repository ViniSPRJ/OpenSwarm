import os

from agency_swarm import Agent, ModelSettings
from openai.types.shared import Reasoning

from config import get_specialist_model, is_specialist_openai_provider
from run_utils import _load_openswarm_dotenv
from shared_tools.GetMarketDataSnapshot import GetMarketDataSnapshot

_load_openswarm_dotenv()

current_dir = os.path.dirname(os.path.abspath(__file__))
instructions_path = os.path.join(current_dir, "instructions.md")

def create_fx_trader() -> Agent:
    return Agent(
        name="FX Trader",
        description="Specialist in Foreign Exchange (FX) markets, currency pairs, and global macro trends.",
        instructions=instructions_path,
        model=get_specialist_model(),
        tools=[GetMarketDataSnapshot],
        model_settings=ModelSettings(
            reasoning=Reasoning(effort="medium", summary="auto") if is_specialist_openai_provider() else None,
        ),
    )

if __name__ == "__main__":
    from agency_swarm import Agency
    Agency(create_fx_trader()).terminal_demo()
