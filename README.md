# web-orders-search

Skrypt do ręcznego sprawdzania aktualnych zleceń web-dev/web-app z pięciu darmowych źródeł: e-Zamówienia, TED, Oferia.com.pl, Freelancer.com, PeoplePerHour.

## Setup (jednorazowo)

1. `pip install -r requirements.txt`
2. `playwright install chromium` (potrzebne tylko dla fetchera PeoplePerHour)
3. Opcjonalnie: wyślij mail na `api@useme.com` z prośbą o dostęp do API. Useme nie jest jeszcze zaimplementowane (patrz addendum w specu), ale wniosek warto wysłać od razu, bo odpowiedź może długo nie przychodzić.

## Użycie

```bash
python run.py
```

Wynik: `report.html` w katalogu projektu. Otwórz go w przeglądarce. Historia widzianych zleceń jest w `data/seen.json` (tworzony automatycznie, w `.gitignore`).

## Testy

```bash
pytest
```
