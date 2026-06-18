# Codex Handoff - OpenSwarm Trading Desk

This note captures what Codex learned while reviewing and reshaping this repo.
It is meant as a fast handoff for the next agent or future maintenance pass.

## Current Shape

OpenSwarm has been converted from the original generic content/media swarm into an
analysis-only trading desk.

The active architecture is two-tier:

- Tier 1: `Portfolio Manager`, implemented by the native OpenSwarm orchestrator.
- Tier 2: six specialist agents.

Active public agent roster:

- `Portfolio Manager`
- `FX Trader`
- `Equities Trader`
- `US Equities Trader`
- `Derivatives Trader`
- `Fixed Income Trader`
- `Risk`

The legacy specialists were intentionally removed:

- Virtual Assistant
- Docs
- Slides
- Video
- Image
- Data Analyst
- Deep Research

## Important Files

- `swarm.py`: imports agents and defines the communication topology.
- `orchestrator/orchestrator.py`: Portfolio Manager agent definition.
- `orchestrator/instructions.md`: Portfolio Manager prompt.
- `<agent>/<agent>.py`: specialist agent definitions.
- `<agent>/instructions.md`: specialist prompts.
- `shared_instructions.md`: global no-execution and provenance guardrails.
- `config.py`: model routing helpers.
- `server.py`: FastAPI entrypoint.
- `docker-compose.yml`: isolated service definition for VPS deployment.
- `README.md`: user-facing deployment and architecture notes.
- `AGENTS.md`: repo instructions for coding agents.

## Communication Topology

The desired topology is intentionally narrow:

- `Portfolio Manager -> all specialists` through `SendMessage`.
- Market traders can transfer to `Risk` through `Handoff`.
- There is no broad specialist-to-specialist chatter.

Market traders are:

- `FX Trader`
- `Equities Trader`
- `US Equities Trader`
- `Derivatives Trader`
- `Fixed Income Trader`

`Risk` is the only specialist lane outside PM delegation.

## Safety Contract

This service is analysis-only.

It must not:

- place orders
- route orders
- approve execution
- mutate broker state
- imply broker authority

If data freshness, market data, position data, source truth, or execution authority
is unclear, stale, divergent, or missing, agents must say `ALERTA DE ARMADILHA`
and stop before giving an executable recommendation.

Preserve provenance labels exactly:

- `book_source`
- `manual_source`
- `live_source`
- `source_of_truth`
- `source_role`

In the current Nexus topology, VPS/Hostinger is a control-plane or research
surface by default. Do not describe it as canonical broker P&L or canonical
market data unless a checked contract proves that. Mac Mini remains the expected
market-data edge/source unless explicitly changed.

## Production Data Lanes

These are the production lanes expected to feed the OpenSwarm Trading Desk.
OpenSwarm should consume them as analysis inputs with explicit provenance, not
as permission to execute.

### Lane 1 - Hostinger Control Plane

Role:

- private VPS/control-plane surface
- health, workers, research state, proxy/mirror surfaces
- Tailscale/private-service first; avoid public direct paths unless explicitly
  validated

Known surfaces and names:

- `hostinger-nexus`
- `arcus-nexus`
- `/health`
- `/workers`
- `/research/source-health`
- `/research/hermes/latest`
- `/research/hermes/history`
- `/market-data`

Provenance rule:

- Do not call this canonical market data by default.
- Treat it as `source_role=vps_control_plane_research_surfaces` unless the
  specific endpoint contract proves canonical data.

### Lane 2 - Hostinger MT5 B3/US Market Data

Role:

- current live-bot market-data lane for B3 and US quotes through Hostinger MT5
- used by the bot/VPS helper as canonical market data when the validated
  Hostinger MT5 contract is active

Known contract from prior validation:

- bot VPS helper: `http://127.0.0.1:18182/market-data`
- backing source: Hostinger tailnet endpoint
- B3 payload path: `hostinger_mt5.markets.b3.quotes`
- US payload path: `hostinger_mt5.markets.us.quotes`
- expected provenance: `source_provenance=['hostinger:canonical','mode:canonical','source:hostinger_prices']`
- expected desk mode: `desk_mode='canonical'`

Usage rule for OpenSwarm:

- This lane can feed FX, Equities, US Equities, Derivatives, Fixed Income, and
  Risk only as analysis input.
- If freshness, symbol coverage, or `source_provenance` is missing, respond with
  `ALERTA DE ARMADILHA` before forming an executable thesis.

### Lane 3 - DQ MT5 B3/US Research Bridges

Role:

- read-only bridge inputs for research, backtests, and ML studies
- not an execution surface

Expected labels:

- `dq.mt5_b3_bridge`
- `dq.mt5_us_bridge`

Usage rule:

- Good for context, history, studies, and model features.
- Do not relabel DQ as Mac Mini or Hostinger truth.
- Do not use DQ bridge data as broker execution approval.

### Lane 4 - Mac Mini / Nexus Swarm Book And P&L

Role:

- expected canonical lane for positions, book state, and P&L/MTM once the real
  backend contract is present
- current cockpit routing has used Mac Mini/Nexus Swarm on port `9000`

Known related endpoint:

- Nexus Weatlh Manager uses `/api/v1/research/source-health` for source-health,
  not `/api/v1/research/pulse`

Current gap:

- hardcoded/operator MTM fallback has existed before and must stay labeled
  non-canonical until replaced by a real Mac Mini book/P&L contract.

Expected labels:

- `book_source`
- `manual_source`
- `live_source`

Usage rule for OpenSwarm:

- Risk cannot calculate real VaR or sizing without real positions, prices,
  volatility/correlation assumptions, horizon, and confidence level.
- If book/P&L is fallback/manual/operator-provided, Risk must label it as such.

### Lane 5 - Research And Source Health

Role:

- source freshness, missing/stale counts, research worker health, and research
  context

Known surfaces:

- `/research/source-health`
- `/api/v1/research/source-health`
- `agy-helper` for deep research on the bot/VPS side

Usage rule:

- Source-health should be checked before producing high-confidence desk output.
- If source-health is stale/divergent/incomplete, stop with
  `ALERTA DE ARMADILHA`.

### Lane 6 - Manual Operator Inputs

Role:

- discretionary levels, human macro view, override notes, manual positions, and
  desk context given by the user/operator

Expected labels:

- `manual_source`
- `operator_source`
- `book_source=manual` when applicable

Usage rule:

- Manual inputs can guide the PM and specialists, but must not be silently
  promoted to canonical market data, broker state, or execution approval.

### OpenSwarm Ingestion Rule

OpenSwarm should not be the source of truth for live market data, broker
positions, or execution state. It should receive normalized lane summaries with:

- timestamp
- source lane
- source role
- freshness
- symbol coverage
- provenance fields
- any missing/stale/error counts

If a lane cannot provide that minimum metadata, the PM should ask for the missing
contract or stop with `ALERTA DE ARMADILHA`.

## Model Routing

The repo supports role-specific models:

- `ORCHESTRATOR_MODEL`: used by the Portfolio Manager.
- `SPECIALIST_MODEL`: used by all six specialists.
- `DEFAULT_MODEL`: fallback only.

Current intended VPS env:

```env
OPENROUTER_API_KEY=...
ORCHESTRATOR_MODEL=litellm/openrouter/openrouter/fusion
SPECIALIST_MODEL=litellm/openrouter/deepseek/deepseek-v4-flash
APP_TOKEN=...
```

Do not commit real API keys. The OpenRouter key was discussed in chat and should
be considered sensitive. Prefer rotating it after VPS deployment is stable.

LiteLLM is used because Agency Swarm's direct path is OpenAI-oriented, while
OpenRouter is a separate provider with OpenAI-compatible HTTP semantics.

## Deployment Notes

The API defaults to:

- host: `0.0.0.0`
- port: `18080`
- agency key: `open-swarm`

`APP_TOKEN` must be set before exposing the API beyond localhost. Without it,
Agency Swarm disables auth.

Deploy this as a separate service from Nexus Swarm TradingMB. Keep separate:

- environment variables
- logs
- Python environment or Docker container
- exposed port

The local Docker CLI was not available during review, so Docker build/compose
still needs to be verified on a Docker-capable machine or on the VPS.

## Validation Already Run

Successful checks during the refactor:

```bash
python3 -m compileall -q config.py orchestrator fx_trader equities_trader us_equities_trader derivatives_trader fixed_income_trader risk_manager swarm.py server.py
git diff --check
ORCHESTRATOR_MODEL=litellm/openrouter/openrouter/fusion SPECIALIST_MODEL=litellm/openrouter/deepseek/deepseek-v4-flash python3 - <<'PY'
from swarm import create_agency
agency = create_agency()
print(agency.name)
print(list(agency.agents.keys()) if hasattr(agency.agents, 'keys') else [getattr(a, 'name', str(a)) for a in agency.agents])
PY
```

Expected agency output:

```text
OpenSwarm Trading Desk
['Portfolio Manager', 'FX Trader', 'Equities Trader', 'US Equities Trader', 'Derivatives Trader', 'Fixed Income Trader', 'Risk']
```

## Git State Learned

The upstream remote is:

```text
origin https://github.com/VRSEN/OpenSwarm.git
```

The authenticated user did not have permission to push there.

A fork remote was created and successfully pushed:

```text
fork https://github.com/ViniSPRJ/OpenSwarm.git
```

Committed and pushed commit:

```text
344b466 Refactor OpenSwarm into trading desk
```

The `.codex/` folder is intentionally untracked and should not be committed
unless the user explicitly asks to version those local Codex agent configs.

## Related Helios Note

The user also wants symmetry with `Helios-Core/extensions/trading-desk`.
That extension was adjusted to use:

- same public roster
- `Risk` instead of `Risk Manager`
- `analysis_only` policy
- no-execution guardrails

Helios and OpenSwarm should remain separate desks. They should not talk to each
other automatically. The user is the intersection between them.

At the time of review, `pnpm -r check` in Helios failed outside the trading-desk
extension because `packages/kernel/src/index.ts` had duplicate
`createDefaultWorkerRuntime` identifiers, likely related to unrelated untracked
kernel files. The trading-desk extension itself imported successfully with `tsx`.
