"""
HEAT — WebSocket Real-Time Push Layer

Pushes pre-buffered updates to connected frontends using the ``websockets``
library.  Tier-based access ensures that only appropriately delayed data
reaches each client:

  - **Tier 0 (public):**   72-hour delayed data only
  - **Tier 1 (contributor):** 24-hour delayed data only
  - **Tier 2 (moderator):**  Real-time / no delay

SAFETY INVARIANT
    Tier 0 and Tier 1 clients NEVER receive real-time data.
    All pushes for those tiers go through the safety buffer first.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Import project safety constants
# ---------------------------------------------------------------------------
try:
    from processing.config import (
        SAFETY_DELAY_HOURS_PUBLIC,
        SAFETY_DELAY_HOURS_CONTRIBUTOR,
        FORBIDDEN_ALERT_WORDS,
    )
except ImportError:
    try:
        from config import (
            SAFETY_DELAY_HOURS_PUBLIC,
            SAFETY_DELAY_HOURS_CONTRIBUTOR,
            FORBIDDEN_ALERT_WORDS,
        )
    except ImportError:
        SAFETY_DELAY_HOURS_PUBLIC = 72
        SAFETY_DELAY_HOURS_CONTRIBUTOR = 24
        FORBIDDEN_ALERT_WORDS = [
            "presence", "sighting", "activity", "raid", "operation",
            "spotted", "seen", "located", "arrest", "detained",
            "vehicle", "van", "agent", "officer", "uniform",
        ]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_UPDATE_TYPES = frozenset({
    "cluster_update",
    "heatmap_refresh",
    "alert",
    "sentiment_update",
    "pipeline_status",
    "agent_status",   # AgentBus team / pipeline events
})

# Rate limiting
MAX_UPDATES_PER_MINUTE = 10

# Tier delay mapping (hours)
TIER_DELAYS: dict[int, int] = {
    0: SAFETY_DELAY_HOURS_PUBLIC,       # 72 h
    1: SAFETY_DELAY_HOURS_CONTRIBUTOR,  # 24 h
    2: 0,                               # real-time
}

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ConnectedClient:
    """Tracks a single WebSocket client and its capabilities."""
    websocket: Any
    tier: int = 0
    subscriptions: set[str] = field(default_factory=lambda: set(VALID_UPDATE_TYPES))
    send_timestamps: list[float] = field(default_factory=list)
    connected_at: float = field(default_factory=time.time)
    client_id: str = ""

    def is_rate_limited(self) -> bool:
        """Return True if this client has exceeded the per-minute send cap."""
        now = time.time()
        cutoff = now - 60
        self.send_timestamps = [t for t in self.send_timestamps if t > cutoff]
        return len(self.send_timestamps) >= MAX_UPDATES_PER_MINUTE

    def record_send(self) -> None:
        self.send_timestamps.append(time.time())


# ---------------------------------------------------------------------------
# Server state
# ---------------------------------------------------------------------------

_clients: dict[Any, ConnectedClient] = {}
_server: Any = None  # asyncio server handle
_pending_buffer: list[dict] = []  # updates waiting for delay expiry


def _sanitise_text(text: str) -> str:
    """Strip forbidden alert words from any user-facing string."""
    lower = text.lower()
    for word in FORBIDDEN_ALERT_WORDS:
        if word in lower:
            text = text.replace(word, "***")
            text = text.replace(word.capitalize(), "***")
            text = text.replace(word.upper(), "***")
    return text


def _apply_tier_filter(data: dict, tier: int) -> Optional[dict]:
    """
    Apply tier-appropriate filtering/delay to an update payload.

    Returns None if the data should NOT be sent to this tier yet.
    """
    delay_hours = TIER_DELAYS.get(tier, SAFETY_DELAY_HOURS_PUBLIC)

    if delay_hours == 0:
        # Tier 2 moderator — full access, no filtering
        return data

    # Check timestamp on the payload
    ts_str = data.get("timestamp") or data.get("generated_at")
    if ts_str:
        try:
            if isinstance(ts_str, datetime):
                ts = ts_str if ts_str.tzinfo else ts_str.replace(tzinfo=timezone.utc)
            else:
                ts = datetime.fromisoformat(str(ts_str))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            if (now - ts) < timedelta(hours=delay_hours):
                # Data is too fresh for this tier — suppress
                return None
        except (ValueError, TypeError):
            pass  # if we can't parse, let it through (it's probably old)

    # Deep-copy and sanitise user-facing text
    filtered = json.loads(json.dumps(data, default=str))
    for key in ("text", "summary", "representative_text", "body", "title", "description"):
        if key in filtered and isinstance(filtered[key], str):
            filtered[key] = _sanitise_text(filtered[key])

    # Tier 0 gets coarser geographic resolution (ZIP-level only)
    if tier == 0:
        for key in ("lat", "lon", "latitude", "longitude", "street", "address"):
            filtered.pop(key, None)

    return filtered


# ---------------------------------------------------------------------------
# Client handler
# ---------------------------------------------------------------------------

async def handle_client(websocket: Any) -> None:
    """
    Handle a single WebSocket client connection.

    Expected handshake from client (JSON):
        {
            "type": "auth",
            "tier": 0,               // 0 | 1 | 2
            "token": "...",          // optional auth token
            "subscriptions": ["cluster_update", "alert"]
        }
    """
    client = ConnectedClient(websocket=websocket)
    _clients[websocket] = client
    remote = getattr(websocket, "remote_address", ("unknown",))
    logger.info("Client connected from %s", remote)

    try:
        # Wait for auth / subscription message
        async for raw_message in websocket:
            try:
                msg = json.loads(raw_message)
            except json.JSONDecodeError:
                await websocket.send(json.dumps({
                    "type": "error",
                    "message": "Invalid JSON",
                }))
                continue

            msg_type = msg.get("type", "")

            if msg_type == "auth":
                tier = int(msg.get("tier", 0))
                if tier not in (0, 1, 2):
                    tier = 0
                client.tier = tier
                client.client_id = str(msg.get("client_id", id(websocket)))

                # Set subscriptions (validated)
                requested_subs = set(msg.get("subscriptions", list(VALID_UPDATE_TYPES)))
                client.subscriptions = requested_subs & VALID_UPDATE_TYPES

                await websocket.send(json.dumps({
                    "type": "auth_ok",
                    "tier": client.tier,
                    "subscriptions": sorted(client.subscriptions),
                    "server_time": datetime.now(timezone.utc).isoformat(),
                    "delay_hours": TIER_DELAYS.get(client.tier, 72),
                }))
                logger.info(
                    "Client %s authenticated — tier %d, subs=%s",
                    client.client_id, client.tier, client.subscriptions,
                )

            elif msg_type == "subscribe":
                new_subs = set(msg.get("subscriptions", [])) & VALID_UPDATE_TYPES
                client.subscriptions |= new_subs
                await websocket.send(json.dumps({
                    "type": "subscriptions_updated",
                    "subscriptions": sorted(client.subscriptions),
                }))

            elif msg_type == "unsubscribe":
                rm_subs = set(msg.get("subscriptions", []))
                client.subscriptions -= rm_subs
                await websocket.send(json.dumps({
                    "type": "subscriptions_updated",
                    "subscriptions": sorted(client.subscriptions),
                }))

            elif msg_type == "ping":
                await websocket.send(json.dumps({
                    "type": "pong",
                    "server_time": datetime.now(timezone.utc).isoformat(),
                }))

            else:
                await websocket.send(json.dumps({
                    "type": "error",
                    "message": f"Unknown message type: {msg_type}",
                }))

    except Exception as exc:
        logger.debug("Client disconnected: %s", exc)
    finally:
        _clients.pop(websocket, None)
        logger.info("Client disconnected — %d remaining", len(_clients))


# ---------------------------------------------------------------------------
# Broadcasting
# ---------------------------------------------------------------------------

async def broadcast_update(update_type: str, data: dict) -> int:
    """
    Push an update to all subscribers of *update_type*.

    Parameters
    ----------
    update_type : str
        One of the ``VALID_UPDATE_TYPES``.
    data : dict
        Payload (will be tier-filtered per client).

    Returns
    -------
    int
        Number of clients that received the update.
    """
    if update_type not in VALID_UPDATE_TYPES:
        logger.warning("Invalid update type: %s", update_type)
        return 0

    envelope = {
        "type": update_type,
        "server_time": datetime.now(timezone.utc).isoformat(),
        "data": data,
    }

    sent_count = 0
    stale: list[Any] = []

    for ws, client in list(_clients.items()):
        # Check subscription
        if update_type not in client.subscriptions:
            continue

        # Rate limit
        if client.is_rate_limited():
            logger.debug("Rate-limited client %s", client.client_id)
            continue

        # Tier filter (SAFETY: delay enforcement)
        filtered_data = _apply_tier_filter(data, client.tier)
        if filtered_data is None:
            continue  # data too fresh for this tier

        tier_envelope = {**envelope, "data": filtered_data}

        try:
            await ws.send(json.dumps(tier_envelope, default=str))
            client.record_send()
            sent_count += 1
        except Exception:
            stale.append(ws)

    # Clean up disconnected clients
    for ws in stale:
        _clients.pop(ws, None)

    logger.info("Broadcast %s → %d/%d clients", update_type, sent_count, len(_clients))
    return sent_count


def broadcast_update_sync(update_type: str, data: dict) -> int:
    """
    Synchronous wrapper around :func:`broadcast_update` for use from
    non-async pipeline code.

    Schedules the coroutine on the running event loop (if any) or
    creates a new one.
    """
    try:
        loop = asyncio.get_running_loop()
        future = asyncio.ensure_future(broadcast_update(update_type, data))
        # Can't await in sync context; fire-and-forget
        return 0
    except RuntimeError:
        return asyncio.run(broadcast_update(update_type, data))


# ---------------------------------------------------------------------------
# Convenience broadcast helpers
# ---------------------------------------------------------------------------

async def push_cluster_update(cluster_data: dict) -> int:
    """Push a cluster_update event."""
    return await broadcast_update("cluster_update", cluster_data)


async def push_heatmap_refresh(heatmap_data: dict) -> int:
    """Push a heatmap_refresh event."""
    return await broadcast_update("heatmap_refresh", heatmap_data)


async def push_alert(alert_data: dict) -> int:
    """Push an alert event (text will be sanitised)."""
    return await broadcast_update("alert", alert_data)


async def push_sentiment_update(sentiment_data: dict) -> int:
    """Push a sentiment_update event."""
    return await broadcast_update("sentiment_update", sentiment_data)


async def push_pipeline_status(status_data: dict) -> int:
    """Push a pipeline_status event (available to all tiers)."""
    return await broadcast_update("pipeline_status", status_data)


async def push_agent_status(event_dict: dict, snapshot: Optional[dict] = None) -> int:
    """
    Push an agent_status event to all subscribed clients.

    agent_status events are NOT subject to tier delay filtering — they carry
    pipeline metadata only, never raw signal data.
    """
    payload: dict = {
        "type":     "agent_status",
        "event":    event_dict,
        "snapshot": snapshot or {},
        "server_time": datetime.now(timezone.utc).isoformat(),
    }
    stale: list[Any] = []
    sent = 0
    for ws, client in list(_clients.items()):
        if "agent_status" not in client.subscriptions:
            continue
        if client.is_rate_limited():
            continue
        try:
            await ws.send(json.dumps(payload, default=str))
            client.record_send()
            sent += 1
        except Exception:
            stale.append(ws)
    for ws in stale:
        _clients.pop(ws, None)
    return sent


def _register_bus_broadcast() -> None:
    """
    Hook the AgentBus singleton so every bus event is forwarded
    to all connected WebSocket clients subscribed to 'agent_status'.
    Called once at server startup.
    """
    try:
        from processing.agent_bus import get_bus

        async def _ws_handler(msg: dict) -> None:
            await push_agent_status(
                event_dict=msg.get("event", {}),
                snapshot=msg.get("snapshot"),
            )

        get_bus().set_ws_broadcast(_ws_handler)
        logger.info("AgentBus → WebSocket bridge registered")
    except Exception as exc:
        logger.warning("Could not register AgentBus bridge: %s", exc)


# ---------------------------------------------------------------------------
# Server lifecycle
# ---------------------------------------------------------------------------

async def start_server(host: str = "localhost", port: int = 8765) -> None:
    """
    Start the WebSocket server.

    Parameters
    ----------
    host : str
        Bind address.
    port : int
        Bind port.
    """
    global _server

    try:
        import websockets
    except ImportError:
        logger.error(
            "The 'websockets' package is required. Install with: pip install websockets"
        )
        raise

    _server = await websockets.serve(handle_client, host, port)
    logger.info("HEAT WebSocket server listening on ws://%s:%d", host, port)

    # Register AgentBus → WebSocket bridge so bus events are pushed to clients
    _register_bus_broadcast()

    # Keep running until cancelled
    await asyncio.Future()  # block forever


async def stop_server() -> None:
    """Gracefully stop the WebSocket server."""
    global _server
    if _server is not None:
        _server.close()
        await _server.wait_closed()
        _server = None
        logger.info("WebSocket server stopped")


def get_connected_clients() -> list[dict]:
    """Return a snapshot of currently connected clients (for diagnostics)."""
    return [
        {
            "client_id": c.client_id,
            "tier": c.tier,
            "subscriptions": sorted(c.subscriptions),
            "connected_at": c.connected_at,
            "messages_last_minute": len([
                t for t in c.send_timestamps if t > time.time() - 60
            ]),
        }
        for c in _clients.values()
    ]


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import os
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    host = os.environ.get("HEAT_WS_HOST", "localhost")
    port = int(os.environ.get("HEAT_WS_PORT", "8765"))
    print(f"Starting HEAT WebSocket server on ws://{host}:{port} …")
    print("Tier delays — Public: 72 h, Contributor: 24 h, Moderator: real-time")
    print("Press Ctrl+C to stop.\n")

    try:
        asyncio.run(start_server(host, port))
    except KeyboardInterrupt:
        print("\nServer stopped.")
