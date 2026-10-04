# web-orders-search — projekt

Data: 2026-10-04

## Cel

Skrypt uruchamiany ręcznie z katalogu `web-orders-search`, który zbiera z internetu
aktualne zlecenia/leady na budowę stron i aplikacji webowych (dla firmy użytkownika)
i prezentuje je w jednej tabeli HTML: opis zlecenia, dane (budżet/wartość, data), link
bezpośredni do ogłoszenia.

## Zakres i decyzje z brainstormingu

- **Typ zleceń:** wszystkie trzy kategorie — giełdy freelance, leady B2B/outsourcing,
  przetargi publiczne — research sam wskazał, które źródła mają sens.
- **Zasięg:** Polska + międzynarodowe (EN).
- **Tryb pracy:** ręczny, na żądanie (bez harmonogramu/cron w v1).
- **Format wyników:** lokalny plik HTML otwierany w przeglądarce.
- **Budżet na narzędzia:** tylko darmowe/publiczne źródła — żadnych płatnych API/proxy.
- **Podejście do źródeł wymagających logowania:** żadnej automatycznej rejestracji/logowania.
  Jeśli trzeba konta, użytkownik zakłada je i loguje się sam (CAPTCHA/weryfikacja e-mail
  wymagają człowieka); skrypt może odczytywać dane z już istniejącej sesji (cookie
  eksportowane ręcznie) albo z oficjalnego API po uzyskaniu dostępu.

## Research źródeł (free/public)

**Wybrane do v1 (najlepsze ROI, darmowe):**

| Źródło | Kategoria | Dostęp | Uwagi |
|---|---|---|---|
| e-Zamówienia (ezamowienia.gov.pl) | PL przetargi publiczne | Darmowe publiczne REST API, bez rejestracji do odczytu | Filtr po kodach CPV (usługi informatyczne) |
| TED (ted.europa.eu) | Przetargi UE | Darmowe, bezkluczowe REST API v3 | Większe kontrakty IT/web w całej UE |
| Oferia.com.pl | PL leady B2B | Scraping publicznych listingów (bez opłaty za kontakt) | Wymaga sprawdzenia robots.txt |
| Freelancer.com | Giełda freelance (EN) | Scraping publicznych listingów (bez logowania) | Wymaga sprawdzenia robots.txt |
| PeoplePerHour | Giełda freelance (EN) | Ewentualny RSS (niepotwierdzony) lub scraping | Wymaga sprawdzenia robots.txt/feed |
| Useme | PL giełda freelance | Oficjalne API po mailowej akceptacji (api@useme.com); fallback: sesja-cookie użytkownika | Zero ryzyka ToS przy API |

**Odrzucone (ryzyko prawne / brak darmowego dostępu):**
- Upwork — API zablokowane za wymóg $25k lifetime earnings, scraping wprost zabronione w ToS.
- LinkedIn — scraping to prawnie przetestowane naruszenie ToS (hiQ v. LinkedIn).
- Facebook groups — wymaga logowania, scraping narusza ToS.
- Fixly — płatny kontakt z klientem, nie darmowe.
- OLX praca — głównie etaty, słabe dopasowanie do zleceń projektowych.

## Architektura

Jeden skrypt Python 3.14 (dostępny w środowisku), bez ciężkich zależności
(`requests`, `beautifulsoup4`, opcjonalnie `lxml`):

```
run.py
  ├─ fetchers/
  │    ├─ ezamowienia.py   (API)
  │    ├─ ted.py           (API)
  │    ├─ oferia.py        (scraping)
  │    ├─ freelancer.py    (scraping)
  │    ├─ peopleperhour.py (RSS lub scraping)
  │    └─ useme.py         (API, fallback: sesja-cookie)
  ├─ normalize.py   # mapuje wynik każdego fetchera na wspólny schemat
  ├─ filter.py      # słowa kluczowe PL+EN + kody CPV
  ├─ store.py       # historia widzianych zleceń (data/seen.json)
  ├─ report.py      # generuje report.html
  └─ config.py      # lista źródeł, słowa kluczowe, ścieżki plików
```

### Przepływ danych

`run.py` odpytuje każdy fetcher niezależnie (błąd jednego nie blokuje innych) →
`normalize` scala wyniki do wspólnego schematu
`{źródło, tytuł, opis, budżet_wartość, data_publikacji, link, kategoria}` →
`filter` odsiewa nieistotne (poza web-dev) i duplikaty względem historii →
`store` zapisuje nowe wpisy i aktualizuje historię →
`report` generuje `report.html`.

### Wspólny schemat zlecenia

```python
{
    "source": str,          # nazwa źródła, np. "e-Zamówienia"
    "title": str,
    "description": str,
    "value": str | None,    # budżet/wartość, jeśli dostępna
    "published_at": str,    # ISO 8601, jeśli dostępna
    "link": str,            # URL bezpośredni do ogłoszenia
    "category": str,        # "przetarg" | "freelance" | "b2b"
}
```

## Storage i deduplikacja

Jeden plik `data/seen.json`: lista `{link, content_hash, first_seen, last_seen}`.

- Link znany → aktualizacja `last_seen`, oznaczony jako "stare" w raporcie.
- Link nowy → dopisanie z `first_seen = teraz`, oznaczony jako "NOWE" w raporcie.
- Dedup dodatkowo po znormalizowanym tytule+kliencie (nie tylko po linku), bo przetargi
  mogą publikować to samo ogłoszenie pod różnymi URL przy aktualizacji.

Brak bazy danych — czysty JSON wystarcza przy realistycznej skali (do kilkuset zleceń
na przebieg).

## Filtrowanie trafności

`config.py` trzyma listy słów kluczowych:

- **PL:** strona internetowa, aplikacja webowa, serwis www, e-commerce, sklep
  internetowy, frontend, backend, WordPress, landing page, itd.
- **EN:** website, web app, web application, frontend, backend, e-commerce,
  landing page, itd.

Dla przetargów (e-Zamówienia/TED) dodatkowy filtr po kodach CPV z zakresu usług
informatycznych/tworzenia oprogramowania (72000000–72999999).

Zlecenie trafia do raportu, jeśli dowolne słowo kluczowe trafi w tytuł/opis
(case-insensitive) **lub** kod CPV jest na liście. Lista edytowalna w jednym miejscu
(`config.py`), bez zmian w kodzie fetcherów.

## Raport HTML

Statyczny `report.html` (nadpisywany przy każdym uruchomieniu), bez zależności
zewnętrznych/CDN — ma działać offline z lokalnego pliku:

- Tabela: Źródło | Tytuł/Opis | Budżet / Wartość | Data publikacji | Link bezpośredni.
- Wiersze "NOWE od ostatniego razu" wizualnie wyróżnione.
- Sortowanie kolumn czystym vanilla JS (klik na nagłówek), bez bibliotek.
- Nagłówek raportu: data wygenerowania + lista źródeł, które nie odpowiedziały
  w danym przebiegu.

## Obsługa błędów

- Każdy fetcher owinięty w `try/except` w `run.py` — błąd jednego źródła (timeout,
  zmiana struktury strony, 403, brak dostępu do API) jest logowany do konsoli i do
  nagłówka raportu, nie przerywa pozostałych fetcherów.
- Limit requestów na domenę z opóźnieniem (np. 1 request / 2s) dla scraperów.
- Jednorazowe sprawdzenie `robots.txt` przy starcie dla Oferii/Freelancer.com/
  PeoplePerHour — jeśli reguły zabraniają danej ścieżki, fetcher się wyłącza i
  zgłasza to w raporcie, zamiast łamać zasady po cichu.

## Testy

- **Unit testy (pytest)** dla `normalize.py`, `filter.py`, `store.py` — logika
  deterministyczna, testowana na nagranych przykładowych odpowiedziach (fixtures),
  bez uderzania w żywe serwisy.
- **Fetchery** nie są jednostkowo testowane względem żywych stron (niestabilne
  z natury) — weryfikacja to realny `run.py` i sprawdzenie raportu (smoke test).

## Checklist startowy (konta/dostępy)

Jednorazowo, przed pierwszym pełnym użyciem:

1. Wysłać mail na `api@useme.com` z prośbą o dostęp do API (treść może przygotować
   Claude, użytkownik wysyła z własnej skrzynki).
2. Opcjonalnie: ręczne logowanie do Useme w przeglądarce i eksport cookie sesji do
   `data/useme_cookie.txt` jako fallback przed otrzymaniem API.
3. Sprawdzenie `robots.txt` Oferii/Freelancer.com/PeoplePerHour — wykonywane
   automatycznie przy pierwszym uruchomieniu skryptu.

## Poza zakresem v1

- Harmonogram/automatyzacja (cron) — możliwy kolejny krok po sprawdzeniu v1 w praktyce.
- Płatne API/proxy.
- Automatyczna rejestracja/logowanie na serwisach trzecich.
- Źródła wymagające logowania bez wyjątku Useme (np. LinkedIn, Facebook groups) —
  odrzucone ze względu na ToS.
