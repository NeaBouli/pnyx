# Google Indexing Audit - ekklesia.gr - 2026-05-03

## Quelle

- Datei: `/Users/gio/Downloads/ekklesia.gr-Coverage-2026-05-03.zip`
- Enthaltene CSVs:
  - `Diagramm.csv`
  - `Kritische Probleme.csv`
  - `Nicht kritische Probleme.csv`
  - `Metadaten.csv`

## Search Console Befund

- Export-Datum im ZIP: 2026-05-03 11:49
- Diagramm:
  - 2026-04-27: `Nicht indexiert = 2`, `Indexiert = 1`, `Impressionen = 1`
- Kritische Probleme:
  - `Gecrawlt - zurzeit nicht indexiert`: 1 Seite, Quelle `Google-Systeme`, Validierung `Nicht gestartet`
  - `Alternative Seite mit richtigem kanonischen Tag`: 1 Seite, Quelle `Website`, Validierung `Gestartet`
- Nicht kritische Probleme:
  - keine Eintraege im Export
- Metadaten:
  - Sitemap: `Alle bekannten Seiten`

## Live-Pruefung oeffentlicher SEO-Signale

Geprueft wurden nur oeffentliche URLs. Keine Secrets, keine `.env`, keine `.gitignore`.

- `https://ekklesia.gr/` liefert `HTTP 200`.
- `https://www.ekklesia.gr/` liefert `HTTP 308` nach `https://ekklesia.gr/`.
- `https://ekklesia.gr/robots.txt` ist erreichbar.
- `https://ekklesia.gr/sitemap.xml` ist erreichbar.
- `https://ekklesia.gr/wiki/index.html` liefert `HTTP 200` und setzt Canonical auf sich selbst.

## Wahrscheinliche Hauptursache

Die Sitemap enthaelt:

- `https://ekklesia.gr/tickets/`

Diese URL ist nicht stabil final:

- `https://ekklesia.gr/tickets/` liefert `HTTP 308` nach `/tickets`
- `https://ekklesia.gr/tickets` liefert `HTTP 307` nach `https://ekklesia.gr/el/tickets`
- `https://ekklesia.gr/el/tickets` liefert `HTTP 301` nach `/tickets/index.html`
- `https://ekklesia.gr/tickets/index.html` liefert `HTTP 200`

Damit zeigt die Sitemap auf eine URL, die nicht die finale kanonische Zielseite ist. Das passt sehr gut zum Search-Console-Problem `Alternative Seite mit richtigem kanonischen Tag`.

## Weitere Auffaelligkeiten

- Die Startseite und Wiki-Seiten setzen `hreflang="el"` und `hreflang="en"` auf dieselbe URL. Wenn es keine getrennten Sprach-URLs gibt, kann Google diese Signale als redundant oder unklar behandeln.
- `robots.txt` definiert zuerst fuer `User-agent: *` mehrere Disallow-Regeln, danach aber fuer `Googlebot` explizit `Allow: /`. Fuer Googlebot koennen dadurch die allgemeinen Sperren faktisch nicht greifen. Das ist kein aktueller Indexierungsblocker, aber ein klares Steuerungsproblem.
- Die Sitemap listet mehrere HTML-Dateien sauber, aber `/tickets/` weicht vom finalen URL-Verhalten ab.
- Der Export enthaelt keine URL-Beispiele. Die konkrete betroffene URL muss in der Search Console unter dem jeweiligen Problem geoeffnet werden, um die Zuordnung final zu bestaetigen.

## Empfehlung

1. Sitemap korrigieren:
   - Entweder `https://ekklesia.gr/tickets/index.html` listen, wenn diese URL kanonisch bleiben soll.
   - Oder besser eine klare kanonische Tickets-URL festlegen, z. B. `https://ekklesia.gr/tickets/`, und alle Varianten per 301 genau dorthin fuehren.
2. Redirect-Kette fuer Tickets vereinfachen:
   - keine Kette `/tickets/ -> /tickets -> /el/tickets -> /tickets/index.html`
   - maximal eine Weiterleitung auf die kanonische Ziel-URL.
3. Auf der finalen Tickets-Seite explizit setzen:
   - `<meta name="robots" content="index, follow">`
   - `<link rel="canonical" href="https://ekklesia.gr/tickets/">` oder die bewusst gewaehlte Ziel-URL.
4. Hreflang bereinigen:
   - Wenn `el` und `en` dieselbe URL teilen, Hreflang fuer getrennte Sprachen entweder entfernen oder echte getrennte URLs verwenden.
5. Robots.txt vereinheitlichen:
   - Wenn Google bestimmte App-Routen nicht indexieren soll, die `Googlebot Allow: /` Sondergruppe entfernen oder exakt konfigurieren.
6. Danach in Google Search Console:
   - Sitemap neu einreichen.
   - Fuer das Canonical-Problem `Validierung starten` beziehungsweise laufende Validierung beobachten.
   - URL-Pruefung fuer `/tickets/`, `/tickets`, `/el/tickets`, `/tickets/index.html` ausfuehren und die von Google gewaehlte Canonical vergleichen.

## Status

- Fix lokal umgesetzt:
  - `apps/web/src/middleware.ts`: `/tickets` und `/tickets/` leiten direkt auf `/tickets/index.html`.
  - `docs/sitemap.xml`: Tickets-URL auf `https://ekklesia.gr/tickets/index.html` gesetzt.
  - `docs/tickets/index.html`: `robots` und `canonical` Meta-Tags ergaenzt.
  - Interne Links in statischen Docs auf `tickets/index.html` nachgezogen, damit die Website selbst nicht mehr `tickets/` als bevorzugte URL bewirbt.
- Funktionsumfang:
  - Keine Ticket-Logik geaendert.
  - Keine API geaendert.
  - Keine Auth- oder POLIS-JavaScript-Logik geaendert.
  - Aenderung betrifft nur SEO-/Routing-Signale.
- Checks:
  - `npm run lint` scheitert an bestehender `next lint`/ESLint-Options-Inkompatibilitaet, nicht an der SEO-Aenderung.
  - `npx tsc --noEmit` in `apps/web` erfolgreich.
- Commit/Push/Deployment:
  - Commit `5d43642` wurde auf `main` gepusht und `ekklesia-web` neu deployed.
  - Nachschaerfung interner Links wurde lokal vorbereitet und soll ebenfalls committed/gepusht/deployed werden.
- Keine Secrets gelesen oder ausgegeben.
