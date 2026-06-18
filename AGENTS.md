# OpenSwarm Trading Desk - Customization Guide

Read this before making changes.

OpenSwarm Trading Desk is an analysis-only multi-agent trading desk. It can research
markets, structure ideas, and produce risk commentary, but it must not place orders,
route orders, approve execution, or mutate broker state.

## Folder Structure

```
swarm.py                  <- main config: imports all agents and defines flows
shared_instructions.md    <- context shared across every agent
server.py                 <- FastAPI API entry point
run_utils.py              <- launcher/runtime helpers

orchestrator/
  orchestrator.py         <- Portfolio Manager definition
  instructions.md         <- PM system prompt

fx_trader/
  fx_trader.py
  instructions.md

equities_trader/
  equities_trader.py
  instructions.md

us_equities_trader/
  us_equities_trader.py
  instructions.md

derivatives_trader/
  derivatives_trader.py
  instructions.md

fixed_income_trader/
  fixed_income_trader.py
  instructions.md

risk_manager/
  risk_manager.py
  instructions.md

shared_tools/             <- optional tools available to agents
```

## Current Agents

| Agent | Purpose |
|---|---|
| `orchestrator` | Portfolio Manager, user-facing router and synthesizer |
| `fx_trader` | FX and global macro currency research |
| `equities_trader` | Brazil/B3 equities research |
| `us_equities_trader` | US equities research |
| `derivatives_trader` | Options, futures, volatility, and hedge structures |
| `fixed_income_trader` | Rates, curves, duration, bonds, and credit |
| `risk_manager` | Risk management, scenario analysis, sizing, concentration, VaR/ES when real inputs exist |

## Safety Boundaries

- This repository is analysis-only.
- Never add broker execution, order placement, or approval logic here without a separate explicit user request and a human-gated execution design.
- If source freshness, market data, position data, or execution authority is unclear, agents must say `ALERTA DE ARMADILHA` and stop before an executable recommendation.
- Preserve provenance fields exactly: `book_source`, `manual_source`, `live_source`, `source_of_truth`, and `source_role`.
- In the current Nexus topology, the VPS is a control-plane/research surface by default. Mac Mini remains the expected market-data edge/source unless a checked contract says otherwise.

## How Agents Connect

`swarm.py` imports every `create_*` factory, instantiates the desk, and defines:

- Portfolio Manager -> every specialist via `SendMessage`
- Market traders -> Risk via `Handoff`
- No direct specialist-to-specialist chatter outside the Risk lane

## Key Conventions

- Each agent folder has one `<name>.py`, one `instructions.md`, and one `__init__.py`.
- Use absolute instruction paths inside agent definitions so deployment does not depend on the process working directory.
- Models are configured through `DEFAULT_MODEL` in `.env`, never hardcoded.
- API defaults to `OPENSWARM_PORT=18080` to avoid the original OpenSwarm `8080` default.
- Keep Docker/systemd deployments isolated from Nexus Swarm TradingMB with separate env, logs, and Python environment.

## Required Workflow Reference

Before proceeding with agent creation or rewiring, read:

- `.cursor/rules/agency-swarm-workflow.mdc`

Read these only when needed:

- `.cursor/commands/add-mcp.md`
- `.cursor/commands/mcp-code-exec.md`
- `.cursor/commands/write-instructions.md`
- `.cursor/commands/create-prd.md`
