import os

from run_utils import _bootstrap, _openswarm_state_root, _preload_agentswarm_bin

_RUNTIME_CONFIGURED = False


def _configure_runtime() -> None:
    global _RUNTIME_CONFIGURED
    if _RUNTIME_CONFIGURED:
        return

    from dotenv import load_dotenv
    from agents import set_tracing_disabled, set_tracing_export_api_key
    from patches.patch_ipython_interpreter_composio import (
        apply_ipython_composio_context_patch,
    )
    from patches.patch_utf8_file_reads import apply_utf8_file_read_patch

    load_dotenv(dotenv_path=_openswarm_state_root() / ".env")

    apply_utf8_file_read_patch()
    apply_ipython_composio_context_patch()

    _tracing_key = os.getenv("OPENAI_API_KEY")
    if _tracing_key:
        set_tracing_export_api_key(_tracing_key)
    else:
        set_tracing_disabled(True)

    _RUNTIME_CONFIGURED = True


if __name__ == "__main__":
    _preload_agentswarm_bin()
    _bootstrap()

_configure_runtime()


def create_agency(load_threads_callback=None):
    _configure_runtime()

    from agency_swarm import Agency
    from agency_swarm.tools import Handoff, SendMessage

    from orchestrator import create_orchestrator
    from fx_trader.fx_trader import create_fx_trader
    from equities_trader.equities_trader import create_equities_trader
    from us_equities_trader.us_equities_trader import create_us_equities_trader
    from derivatives_trader.derivatives_trader import create_derivatives_trader
    from fixed_income_trader.fixed_income_trader import create_fixed_income_trader
    from risk_manager.risk_manager import create_risk_manager

    orchestrator = create_orchestrator()
    fx_trader = create_fx_trader()
    equities_trader = create_equities_trader()
    us_equities_trader = create_us_equities_trader()
    derivatives_trader = create_derivatives_trader()
    fixed_income_trader = create_fixed_income_trader()
    risk_manager = create_risk_manager()

    all_agents = [
        orchestrator,
        fx_trader,
        equities_trader,
        us_equities_trader,
        derivatives_trader,
        fixed_income_trader,
        risk_manager,
    ]

    send_message_flows = [
        (orchestrator, specialist, SendMessage)
        for specialist in all_agents
        if specialist is not orchestrator
    ]

    market_traders = [
        fx_trader,
        equities_trader,
        us_equities_trader,
        derivatives_trader,
        fixed_income_trader,
    ]

    risk_handoff_flows = [
        (trader > risk_manager, Handoff)
        for trader in market_traders
    ]

    agency = Agency(
        *all_agents,
        communication_flows=send_message_flows + risk_handoff_flows,
        name="OpenSwarm Trading Desk",
        shared_instructions="shared_instructions.md",
        load_threads_callback=load_threads_callback,
    )

    return agency


def _main() -> None:
    agency = create_agency()
    agency.tui(show_reasoning=True, reload=False)


if __name__ == "__main__":
    _main()
