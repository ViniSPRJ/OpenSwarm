import logging
import os
import signal
import time
from typing import Any

import httpx
from dotenv import load_dotenv


load_dotenv()

logging.basicConfig(
    level=os.getenv("OPENSWARM_TELEGRAM_LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("openswarm-telegram")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

STOP = False
TELEGRAM_LIMIT = 3900


def _handle_stop(signum: int, frame: Any) -> None:
    global STOP
    STOP = True


signal.signal(signal.SIGTERM, _handle_stop)
signal.signal(signal.SIGINT, _handle_stop)


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def _parse_allowed_chat_ids() -> set[int]:
    raw = (
        os.getenv("OPENSWARM_TELEGRAM_ALLOWED_CHAT_IDS", "").strip()
        or os.getenv("TELEGRAM_ALLOWED_CHAT_IDS", "").strip()
    )
    if not raw:
        return set()

    allowed: set[int] = set()
    for item in raw.replace(";", ",").split(","):
        value = item.strip()
        if not value:
            continue
        allowed.add(int(value))
    return allowed


def _telegram_url(token: str, method: str) -> str:
    return f"https://api.telegram.org/bot{token}/{method}"


def _chunks(text: str) -> list[str]:
    if not text:
        return ["Sem resposta."]
    return [text[i : i + TELEGRAM_LIMIT] for i in range(0, len(text), TELEGRAM_LIMIT)]


def _send_message(client: httpx.Client, token: str, chat_id: int, text: str) -> None:
    for chunk in _chunks(text):
        response = client.post(
            _telegram_url(token, "sendMessage"),
            json={
                "chat_id": chat_id,
                "text": chunk,
                "disable_web_page_preview": True,
            },
            timeout=30,
        )
        response.raise_for_status()


def _send_chat_action(client: httpx.Client, token: str, chat_id: int) -> None:
    try:
        client.post(
            _telegram_url(token, "sendChatAction"),
            json={"chat_id": chat_id, "action": "typing"},
            timeout=10,
        ).raise_for_status()
    except httpx.HTTPError:
        logger.debug("Failed to send typing action", exc_info=True)


def _openswarm_headers(app_token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {app_token}",
        "Content-Type": "application/json",
    }


def _ask_openswarm(
    client: httpx.Client,
    base_url: str,
    app_token: str,
    message: str,
    recipient_agent: str,
) -> str:
    response = client.post(
        f"{base_url.rstrip('/')}/open-swarm/get_response",
        headers=_openswarm_headers(app_token),
        json={
            "message": message,
            "recipient_agent": recipient_agent,
        },
        timeout=float(os.getenv("OPENSWARM_TELEGRAM_REQUEST_TIMEOUT", "180")),
    )
    response.raise_for_status()
    payload = response.json()
    result = payload.get("response") or payload.get("content") or payload.get("message")
    if result is None:
        result = payload
    return str(result)


def _metadata_summary(client: httpx.Client, base_url: str, app_token: str) -> str:
    response = client.get(
        f"{base_url.rstrip('/')}/open-swarm/get_metadata",
        headers={"Authorization": f"Bearer {app_token}"},
        timeout=30,
    )
    response.raise_for_status()
    metadata = response.json().get("metadata", {})
    agents = ", ".join(metadata.get("agents", []))
    return f"{metadata.get('agencyName', 'OpenSwarm')} online.\nAgentes: {agents}"


def _handle_text(
    client: httpx.Client,
    token: str,
    base_url: str,
    app_token: str,
    chat_id: int,
    text: str,
    recipient_agent: str,
) -> None:
    command = text.strip().split(maxsplit=1)[0].lower()

    if command in {"/start", "/help"}:
        _send_message(
            client,
            token,
            chat_id,
            "OpenSwarm Trading Desk online. Envie uma pergunta para o Portfolio Manager. "
            "Use /status para checar a mesa.",
        )
        return

    if command == "/status":
        _send_message(client, token, chat_id, _metadata_summary(client, base_url, app_token))
        return

    _send_chat_action(client, token, chat_id)
    answer = _ask_openswarm(client, base_url, app_token, text, recipient_agent)
    _send_message(client, token, chat_id, answer)


def main() -> None:
    token = _required_env("OPENSWARM_TELEGRAM_BOT_TOKEN")
    app_token = _required_env("APP_TOKEN")
    base_url = os.getenv("OPENSWARM_BASE_URL", "http://openswarm-trading-desk:18080")
    recipient_agent = os.getenv("OPENSWARM_TELEGRAM_RECIPIENT_AGENT", "Portfolio Manager")
    allowed_chat_ids = _parse_allowed_chat_ids()
    poll_timeout = int(os.getenv("OPENSWARM_TELEGRAM_POLL_TIMEOUT", "25"))
    offset = 0

    logger.info(
        "OpenSwarm Telegram bot starting; allowed_chat_ids=%s",
        sorted(allowed_chat_ids) if allowed_chat_ids else "all",
    )

    with httpx.Client() as client:
        if os.getenv("OPENSWARM_TELEGRAM_DROP_PENDING_UPDATES", "1") == "1":
            client.post(
                _telegram_url(token, "deleteWebhook"),
                json={"drop_pending_updates": True},
                timeout=30,
            ).raise_for_status()

        while not STOP:
            try:
                response = client.post(
                    _telegram_url(token, "getUpdates"),
                    json={
                        "timeout": poll_timeout,
                        "offset": offset,
                        "allowed_updates": ["message"],
                    },
                    timeout=poll_timeout + 10,
                )
                response.raise_for_status()
                updates = response.json().get("result", [])
            except httpx.HTTPError:
                logger.warning("Telegram polling failed", exc_info=True)
                time.sleep(5)
                continue

            for update in updates:
                offset = max(offset, int(update.get("update_id", 0)) + 1)
                message = update.get("message") or {}
                chat = message.get("chat") or {}
                chat_id = int(chat.get("id", 0))
                text = str(message.get("text") or "").strip()

                if not chat_id or not text:
                    continue

                if allowed_chat_ids and chat_id not in allowed_chat_ids:
                    logger.info("Ignoring unauthorized chat_id=%s", chat_id)
                    continue

                try:
                    _handle_text(
                        client,
                        token,
                        base_url,
                        app_token,
                        chat_id,
                        text,
                        recipient_agent,
                    )
                except Exception as exc:
                    logger.exception("Failed to handle Telegram message")
                    _send_message(client, token, chat_id, f"Erro no OpenSwarm: {exc}")

    logger.info("OpenSwarm Telegram bot stopped")


if __name__ == "__main__":
    main()
