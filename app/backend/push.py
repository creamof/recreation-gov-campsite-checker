"""Optional Web Push delivery for watcher alerts.

Web Push lets the PWA receive OS notifications even when the app is closed.
It needs a VAPID key pair, which the operator supplies via environment
variables — without them the feature is simply off and the watcher falls
back to in-app alerts (plus local notifications while the app is open).

Setup (one time):
    npx web-push generate-vapid-keys
    export TRAILHEAD_VAPID_PUBLIC_KEY=...   # goes to browsers
    export TRAILHEAD_VAPID_PRIVATE_KEY=...  # stays on the server
    export TRAILHEAD_VAPID_EMAIL=mailto:you@example.com

Subscriptions are stored in the same data dir as watches. Sending uses
pywebpush; expired/invalid subscriptions are pruned automatically.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path

_LOCK = threading.Lock()


def _subs_file() -> Path:
    root = Path(os.environ.get("TRAILHEAD_DATA_DIR", Path(__file__).parent / "data"))
    root.mkdir(parents=True, exist_ok=True)
    return root / "push_subscriptions.json"


def enabled() -> bool:
    return bool(
        os.environ.get("TRAILHEAD_VAPID_PUBLIC_KEY")
        and os.environ.get("TRAILHEAD_VAPID_PRIVATE_KEY")
    )


def public_key() -> str | None:
    return os.environ.get("TRAILHEAD_VAPID_PUBLIC_KEY")


def list_subscriptions() -> list[dict]:
    path = _subs_file()
    if not path.exists():
        return []
    with _LOCK:
        return json.loads(path.read_text() or "[]")


def _save(subs: list[dict]) -> None:
    with _LOCK:
        _subs_file().write_text(json.dumps(subs, indent=1))


def add_subscription(subscription: dict) -> int:
    """Store a browser PushSubscription (deduped by endpoint). Returns count."""
    subs = list_subscriptions()
    endpoint = subscription.get("endpoint")
    subs = [s for s in subs if s.get("endpoint") != endpoint]
    subs.append(subscription)
    _save(subs)
    return len(subs)


def send_alert(title: str, body: str, url: str = "/") -> int:
    """Send a push to every subscription. Returns deliveries attempted."""
    if not enabled():
        return 0
    from pywebpush import WebPushException, webpush  # lazy: optional dep

    payload = json.dumps({"title": title, "body": body, "url": url})
    claims = {"sub": os.environ.get("TRAILHEAD_VAPID_EMAIL", "mailto:admin@example.com")}
    sent = 0
    alive: list[dict] = []
    for sub in list_subscriptions():
        try:
            webpush(
                subscription_info=sub,
                data=payload,
                vapid_private_key=os.environ["TRAILHEAD_VAPID_PRIVATE_KEY"],
                vapid_claims=dict(claims),
            )
            sent += 1
            alive.append(sub)
        except WebPushException as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status in (404, 410):
                continue  # subscription expired — prune it
            alive.append(sub)  # transient failure — keep for next time
        except Exception:
            alive.append(sub)
    _save(alive)
    return sent
