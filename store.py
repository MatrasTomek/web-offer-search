import hashlib
import json
from pathlib import Path


def _content_hash(lead: dict) -> str:
    text = f"{lead['title']}|{lead['description']}"
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_seen(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_seen(seen: dict[str, dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(seen, f, ensure_ascii=False, indent=2)


def mark_new_or_seen(
    leads: list[dict], seen: dict[str, dict], now: str
) -> tuple[list[dict], dict[str, dict]]:
    updated = {link: dict(entry) for link, entry in seen.items()}
    annotated = []
    for lead in leads:
        link = lead["link"]
        existing = updated.get(link)
        if existing is None:
            updated[link] = {
                "link": link,
                "content_hash": _content_hash(lead),
                "first_seen": now,
                "last_seen": now,
            }
            annotated.append({**lead, "is_new": True})
        else:
            existing["content_hash"] = _content_hash(lead)
            existing["last_seen"] = now
            annotated.append({**lead, "is_new": False})
    return annotated, updated
