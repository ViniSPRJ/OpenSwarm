import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from agency_swarm.tools import BaseTool
from pydantic import Field


DEFAULT_MARKET_DATA_URL = "http://127.0.0.1:18182/market-data"
DEFAULT_MAX_QUOTES = 40


class GetMarketDataSnapshot(BaseTool):
    """
    Fetch the read-only Nexus/Hostinger market-data snapshot.

    Use this before claiming market data is unavailable, stale, degraded, or
    divergent. The returned payload is filtered and preserves provenance labels.
    It is read-only and never enables execution.
    """

    symbols: str = Field(
        "",
        description=(
            "Optional comma/space-separated symbols to return, e.g. "
            "'USDCAD,AAPL,PETR4'. Leave empty for market summaries."
        ),
    )
    market: str = Field(
        "auto",
        description="Market filter: auto, all, b3, or us. Use auto with symbols.",
    )
    include_positions: bool = Field(
        False,
        description="Whether to include read-only position summaries when present.",
    )
    include_account: bool = Field(
        False,
        description="Whether to include read-only account summaries when present.",
    )
    max_quotes: int = Field(
        DEFAULT_MAX_QUOTES,
        description="Maximum number of quote rows to return when symbols is empty.",
    )

    def run(self) -> str:
        url = os.getenv("OPENSWARM_MARKET_DATA_URL", DEFAULT_MARKET_DATA_URL).strip()
        timeout = float(os.getenv("OPENSWARM_MARKET_DATA_TIMEOUT", "8"))

        try:
            payload = self._fetch_json(url, timeout)
        except Exception as exc:  # noqa: BLE001
            return json.dumps(
                {
                    "ok": False,
                    "error": f"{type(exc).__name__}: {exc}",
                    "url_source": "OPENSWARM_MARKET_DATA_URL",
                    "execution_allowed": False,
                },
                ensure_ascii=True,
            )

        filtered = self._filter_payload(payload)
        return json.dumps(filtered, ensure_ascii=True, sort_keys=True)

    def _fetch_json(self, url: str, timeout: float) -> dict[str, Any]:
        request = urllib.request.Request(url, headers={"Accept": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                data = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:500]
            raise RuntimeError(f"market-data HTTP {exc.code}: {detail}") from exc

        payload = json.loads(data.decode("utf-8"))
        if not isinstance(payload, dict):
            raise RuntimeError("market-data payload is not a JSON object")
        return payload

    def _filter_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        symbols = self._parse_symbols(self.symbols)
        requested_market = (self.market or "auto").strip().lower()
        if requested_market not in {"auto", "all", "b3", "us"}:
            requested_market = "auto"

        hostinger = payload.get("hostinger_mt5") or {}
        markets = hostinger.get("markets") or {}

        selected_markets = ["b3", "us"] if requested_market in {"auto", "all"} else [requested_market]
        result: dict[str, Any] = {
            "ok": True,
            "generated_at": payload.get("generated_at"),
            "source": payload.get("source"),
            "source_of_truth": payload.get("source_of_truth"),
            "source_role": payload.get("source_role"),
            "provenance": payload.get("provenance"),
            "execution_allowed": bool(payload.get("execution_allowed", False)),
            "operator_gate": payload.get("operator_gate") or hostinger.get("operator_gate"),
            "hostinger_mt5": {
                "status": hostinger.get("status"),
                "generated_at": hostinger.get("generated_at"),
                "source": hostinger.get("source"),
                "read_only": hostinger.get("read_only", True),
                "execution_allowed": bool(hostinger.get("execution_allowed", False)),
                "blocked_mutation_apis": hostinger.get("blocked_mutation_apis"),
            },
            "markets": {},
        }

        for market_name in selected_markets:
            market_payload = markets.get(market_name)
            if not isinstance(market_payload, dict):
                continue
            result["markets"][market_name] = self._filter_market(market_payload, symbols)

        if symbols:
            result["missing_symbols"] = self._missing_symbols(result["markets"], symbols)

        return result

    def _filter_market(self, market_payload: dict[str, Any], symbols: list[str]) -> dict[str, Any]:
        quotes = market_payload.get("quotes") or {}
        quote_items: list[tuple[str, Any]]
        if isinstance(quotes, dict):
            quote_items = list(quotes.items())
        else:
            quote_items = []

        if symbols:
            wanted = set(symbols)
            quote_items = [
                (symbol, quote)
                for symbol, quote in quote_items
                if symbol.upper() in wanted
                or str((quote or {}).get("canonical", "")).upper() in wanted
                or str((quote or {}).get("actual", "")).upper() in wanted
                or str((quote or {}).get("requested", "")).upper() in wanted
            ]
        else:
            limit = max(0, min(int(self.max_quotes or DEFAULT_MAX_QUOTES), DEFAULT_MAX_QUOTES))
            quote_items = quote_items[:limit]

        market_result: dict[str, Any] = {
            "status": market_payload.get("status"),
            "market": market_payload.get("market"),
            "source": market_payload.get("source"),
            "generated_at": market_payload.get("generated_at"),
            "freshness": market_payload.get("freshness"),
            "read_only": market_payload.get("read_only", True),
            "execution_allowed": bool(market_payload.get("execution_allowed", False)),
            "symbols_total": market_payload.get("symbols_total"),
            "quotes": {
                symbol: self._compact_quote(quote)
                for symbol, quote in quote_items
                if isinstance(quote, dict)
            },
        }

        if self.include_positions:
            market_result["positions"] = market_payload.get("positions")
        if self.include_account:
            market_result["account"] = market_payload.get("account")

        return market_result

    def _compact_quote(self, quote: dict[str, Any]) -> dict[str, Any]:
        fields = [
            "requested",
            "canonical",
            "actual",
            "description",
            "price",
            "bid",
            "ask",
            "last",
            "time",
            "time_msc",
            "age_s",
            "stale",
            "stale_threshold_s",
            "source",
            "provider",
            "currency_base",
            "currency_profit",
        ]
        return {field: quote.get(field) for field in fields if field in quote}

    def _parse_symbols(self, raw: str) -> list[str]:
        if not raw:
            return []
        cleaned = raw.replace(",", " ")
        return [item.strip().upper() for item in cleaned.split() if item.strip()]

    def _missing_symbols(self, markets: dict[str, Any], symbols: list[str]) -> list[str]:
        found: set[str] = set()
        for market_payload in markets.values():
            for symbol, quote in (market_payload.get("quotes") or {}).items():
                found.add(symbol.upper())
                for field in ("requested", "canonical", "actual"):
                    value = quote.get(field)
                    if value:
                        found.add(str(value).upper())
        return [symbol for symbol in symbols if symbol not in found]
