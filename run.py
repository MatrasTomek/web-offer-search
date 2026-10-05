import sys
from datetime import datetime, timezone
from pathlib import Path

import config
from filter import dedup_within_batch, is_relevant
from report import write_report
from store import load_seen, mark_new_or_seen, save_seen


def run(
    sources: list[tuple[str, callable]],
    now: str,
    seen_path: Path,
    report_path: Path,
) -> dict:
    all_leads = []
    failed_sources = []
    for name, fetch in sources:
        try:
            all_leads.extend(fetch())
        except Exception as exc:
            print(f"[{name}] nie odpowiedział: {exc}", file=sys.stderr)
            failed_sources.append(name)

    relevant = [lead for lead in all_leads if is_relevant(lead)]
    deduped = dedup_within_batch(relevant)

    seen = load_seen(seen_path)
    annotated, updated_seen = mark_new_or_seen(deduped, seen, now)
    save_seen(updated_seen, seen_path)

    write_report(annotated, failed_sources, generated_at=now, path=report_path)

    return {"leads": annotated, "failed_sources": failed_sources}


def main() -> None:
    from fetchers import ezamowienia, freelancer, oferia, peopleperhour, ted

    sources = [
        ("e-Zamówienia", ezamowienia.fetch),
        ("TED", ted.fetch),
        ("Oferia.com.pl", oferia.fetch),
        ("Freelancer.com", freelancer.fetch),
        ("PeoplePerHour", peopleperhour.fetch),
    ]
    now = datetime.now(timezone.utc).isoformat()
    result = run(sources, now, config.SEEN_STORE_PATH, config.REPORT_PATH)

    print(f"Znaleziono {len(result['leads'])} zleceń.")
    if result["failed_sources"]:
        print(f"Nie odpowiedziały: {', '.join(result['failed_sources'])}")
    print(f"Raport: {config.REPORT_PATH}")


if __name__ == "__main__":
    main()
