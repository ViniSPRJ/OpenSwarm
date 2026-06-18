# OpenSwarm Trading Desk

OpenSwarm Trading Desk is an analysis-only multi-agent desk built on Agency Swarm.
It is designed to run locally or on the Nexus desk VPS beside Nexus Swarm TradingMB.

The service can research, structure, and risk-check trade ideas, but it does not place
orders or modify broker state. Execution remains a separate human-gated Nexus Swarm
workflow.

## Agents

| Agent | Purpose |
|---|---|
| Portfolio Manager | User-facing orchestrator and trading book synthesizer |
| FX Trader | G10 and EM currency research |
| Equities Trader | Brazilian equities and B3 sector research |
| US Equities Trader | US equities, indices, sectors, and mega-cap research |
| Derivatives Trader | Options, futures, volatility, and hedge structure research |
| Fixed Income Trader | Rates, duration, curves, bonds, and credit research |
| Risk | Risk management, scenario analysis, sizing, concentration, and VaR/ES when real inputs exist |

## Architecture

OpenSwarm uses a two-tier desk:

- Tier 1: Portfolio Manager, implemented by the native OpenSwarm orchestrator.
- Tier 2: six dedicated specialist agents.
- Communication: PM delegates to every specialist; market traders may transfer to Risk for risk review.

## Safety Contract

- `OPENSWARM_SERVICE_ROLE=analysis_only`
- No order placement, order routing, broker mutation, or execution approval.
- If data freshness, position data, source truth, or execution authority is unclear, agents must say `ALERTA DE ARMADILHA` and stop before giving an executable recommendation.
- Preserve provenance fields such as `book_source`, `manual_source`, `live_source`, `source_of_truth`, and `source_role`.
- In the current Nexus topology, VPS/Hostinger surfaces are control-plane or research surfaces by default; Mac Mini remains the expected market-data edge/source unless a checked contract changes that.

## Local Run

```bash
cp .env.example .env
python server.py
```

Default API bind:

- Host: `0.0.0.0`
- Port: `18080`
- Agency key: `open-swarm`

Override with:

```bash
OPENSWARM_PORT=18081 python server.py
```

## Docker Run

```bash
cp .env.example .env
docker compose up --build
```

Default host port is `18080`. To avoid a VPS collision:

```bash
OPENSWARM_HOST_PORT=18081 OPENSWARM_PORT=18080 docker compose up --build
```

## Required Environment

Set at least one provider key and a model:

```bash
OPENROUTER_API_KEY=
ORCHESTRATOR_MODEL=litellm/openrouter/openrouter/fusion
SPECIALIST_MODEL=litellm/openrouter/deepseek/deepseek-v4-flash
APP_TOKEN=
```

The Portfolio Manager uses `ORCHESTRATOR_MODEL`. The six specialists use
`SPECIALIST_MODEL`. `DEFAULT_MODEL` remains an optional fallback.

## Deployment Notes

Deploy this as a separate service from Nexus Swarm TradingMB. Keep a separate virtual
environment or Docker container so Python paths and dependency versions do not bleed
between services.

Set `APP_TOKEN` before exposing the API outside localhost. The server starts without
it for local development, but authentication is disabled in that mode.
