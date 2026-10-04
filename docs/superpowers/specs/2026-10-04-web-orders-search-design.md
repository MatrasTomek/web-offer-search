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

## Addendum: weryfikacja techniczna przed planem implementacji (2026-10-04)

Przed napisaniem planu implementacji sprawdzono bezpośrednio (realne zapytania/live
browser) każde źródło, żeby plan zawierał działający kod, nie zgadywane
endpointy/selektory. Wyniki zmieniają zakres v1 z sekcji "Research źródeł" powyżej:

**Potwierdzone i gotowe do implementacji:**
- **e-Zamówienia** — `GET https://ezamowienia.gov.pl/mo-board/api/v1/notice`, bez
  autoryzacji. Pola: `orderObject` (tytuł/opis), `cpvCode`, `publicationDate`,
  `tenderId`. Parametr `CpvCode` w query **nie filtruje** po stronie serwera
  (zweryfikowano empirycznie) — filtrowanie po CPV musi być po stronie klienta.
  Brak pola budżetu w odpowiedzi.
- **TED** — `POST https://api.ted.europa.eu/v3/notices/search`, bez autoryzacji.
  Pola: `TI` (tytuł, słownik per-język), `ND`, `CY`, `classification-cpv`,
  `links.htmlDirect`. Brak pełnego opisu i budżetu w odpowiedzi search API.
- **Oferia.com.pl** — zwykły HTML, bez JS. Listing:
  `https://oferia.com.pl/pl/zlecenia/programowanie-it`. Selektory:
  `div.listing-card`, `h3.listing-title > a`, `p.listing-excerpt`,
  `div.listing-budget span`, `div.listing-date` (format `DD.MM.YYYY`).
- **Freelancer.com** — zwykły HTML (server-rendered), bez JS. Listing:
  `https://www.freelancer.com/jobs/website-design`. Selektory:
  `a.JobSearchCard-primary-heading-link`, `p.JobSearchCard-primary-description`,
  `div.JobSearchCard-primary-price`, `span.JobSearchCard-primary-heading-days`
  (data względna, np. "6 days left" — nie absolutna).

**Zmiana zakresu — PeoplePerHour wymaga Playwright:**
`/projects_rss` zwraca 404 (feed nie istnieje), a strona z listingiem jest
renderowana przez JS (surowy HTML nie zawiera danych o zleceniach). Potwierdzono
żywą przeglądarką (Playwright + Chromium), że dane faktycznie się renderują
(300+ wyników). Strona używa CSS-modules z haszowanymi nazwami klas
(`item__title⤍ListItem⤚2FRMT`) — hash po `⤚` zmienia się między wdrożeniami, ale
prefiks przed `⤍` (np. `item__title`, `item__desc`, `card__price`,
`card__footer-left`) jest stabilny, więc selektory muszą używać dopasowania
podciągu (`[class*="item__title"]`), nie pełnej klasy. **Decyzja: dodajemy
Playwright jako zależność projektu** (świadomy odstąpienie od "bez ciężkich
zależności" dla tego jednego źródła, zaakceptowane przez użytkownika).

**Zmiana zakresu — Useme wykluczone ze scrapingu, nawet z Playwright:**
Cała domena stoi za Cloudflare i zwraca HTTP 403 "Just a moment..." na każdej
stronie — potwierdzono zarówno przez `requests`, jak i przez żywy Chromium
odpalony przez Playwright (Cloudflare wykrywa automatyzację nawet z prawdziwym
silnikiem przeglądarki). To unieważnia też fallback z cookie sesji z checklisty
startowej (cookie `cf_clearance` jest krótkotrwałe i związane z IP/User-Agent —
nie przetrwa do kolejnego odpalenia skryptu). **Decyzja: Useme wypada z v1
całkowicie.** Jedyna realna ścieżka to oficjalne API po mailowej akceptacji —
zostaje w checkliście startowej jako krok do wysłania, a fetcher Useme dopiszemy
jako fast-follow, gdy dostęp zostanie przyznany (nie teraz, bo nie ma jeszcze
żadnego endpointu/tokena, na którym dałoby się napisać działający kod).

**v1 obejmuje więc 5 fetcherów:** e-Zamówienia, TED, Oferia.com.pl,
Freelancer.com, PeoplePerHour (przez Playwright). Useme — fast-follow po
otrzymaniu dostępu do API.
