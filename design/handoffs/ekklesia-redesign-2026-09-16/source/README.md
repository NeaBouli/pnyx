# Handoff: ekklesia.gr — Redesign

## Überblick

Dieses Paket enthält einen vollständigen Redesign-Vorschlag für **ekklesia.gr** und den Auftrag, ihn auf alle 35 Seiten des Repos `NeaBouli/pnyx` (Branch `main`, Verzeichnis `docs/`) zu übertragen.

Das Redesign ist **kein inhaltlicher Umbau**. Alle Texte sind wortgetreu aus dem Bestand übernommen. Geändert werden Layout, Typografie, Farbverwendung und Struktur.

Ziele des Redesigns (vom Auftraggeber vorgegeben):

1. Mehr Anfragen/Conversions
2. Inhalte klarer strukturieren

Beibehalten: Farbschema (Blau `#2563eb`), Logo, alle bestehenden Texte.

## Zu den Design-Dateien in diesem Paket

`Ekklesia Redesign.dc.html` ist eine **Design-Referenz in HTML** — ein Prototyp, der Aussehen und Verhalten zeigt. Es ist **kein Produktionscode zum Kopieren**.

Die Aufgabe ist, dieses Design in der bestehenden Umgebung des Repos umzusetzen: `docs/` sind statische HTML-Seiten für GitHub Pages, `apps/web/` ist Next.js 16. Die Seiten unter `docs/` bleiben statisches HTML — dort wird das Design also direkt in den bestehenden Dateien umgesetzt, mit deren eigenen Mustern (bilinguale `data-el`/`data-en`-Attribute, Inline-Styles, kein Build-Schritt).

Die Datei öffnet direkt im Browser. Sie hat vier Bildschirme, umschaltbar über die Kopfnavigation:

| Bildschirm | Schaltfläche | Zeigt |
| --- | --- | --- |
| Startseite | Πλατφόρμα | Alle Abschnitte der Landing |
| Ψηφοφορίες | Ψηφοφορίες | Abstimmungsliste, Tabs, Zyklus-Seitenleiste |
| Λήψη | Λήψη App | Download-Kanäle, iPhone-PWA-Anleitung |
| Τεκμηρίωση | Τεκμηρίωση | Wiki-Layout, Beispielseite Αρχιτεκτονική |

## Fidelity

**High-fidelity.** Farben, Typografie, Abstände und Zustände sind final. Pixelgenau nachbauen.

Ausnahmen, die bewusst offen sind:

- Alle Live-Zahlen stehen als `—` (Leerzustand). Sie kommen aus `api.ekklesia.gr` und dürfen nie als Platzhalterzahl gerendert werden.
- Die Abstimmungszeile auf dem Bildschirm Ψηφοφορίες ist als „Παράδειγμα διάταξης" markiert — sie zeigt das Layout einer Zeile, nicht echte Daten.
- Die Wiki-Beispielseite ist **eine** Seite (Αρχιτεκτονική, wortgetreu aus `docs/wiki/architecture.html`). Die anderen 13 Wiki-Seiten sind nach demselben Muster zu überführen — siehe „Auftrag: Wiki-Seiten".

---

# Design-Tokens

Alle Werte sind final. Keine anderen Farben, Radien oder Schriftgrößen verwenden.

## Farben

| Rolle | Hex | Verwendung |
| --- | --- | --- |
| Tinte | `#0f172a` | Überschriften, starke Rahmen, Fußzeilengrund |
| Fließtext | `#334155` | Absätze |
| Fließtext gedeckt | `#475569` | Einleitungen, Tabellenzellen |
| Sekundärtext | `#64748b` | Beschriftungen, Hilfstexte, Kleintext |
| Akzent | `#2563eb` | Primäraktion, Ziffern, Icons, Akzentband |
| Akzent dunkel | `#1d4ed8` | Textlinks auf hellem Grund (Kontrast) |
| Rahmen stark | `#0f172a` | Abschnittstrenner, Eingabefelder, Tabellenkopf |
| Rahmen mittel | `#e2e8f0` | Spalten- und Zeilentrenner |
| Rahmen schwach | `#f1f5f9` | Listentrenner, Tabellenzeilen |
| Rahmen grau | `#cbd5e1` | Trenner auf `#f8fafc`-Grund, inaktive Marker |
| Grund | `#ffffff` | Standard |
| Grund getönt | `#f8fafc` | Abwechselnde Abschnitte, Hinweisblöcke |
| Auf Akzent hell | `#eff6ff` | Fließtext auf blauem Band |
| Auf Akzent Beschriftung | `#bfdbfe` | Kleintext auf blauem Band |
| Auf Tinte | `#cbd5e1` | Fußzeilentext |
| Auf Tinte gedeckt | `#94a3b8` | Fußzeilen-Überschriften, Fußzeilenleiste |
| Auf Tinte Links | `#e2e8f0` | Fußzeilenlinks |

**Nur zwei Grundfarben pro Seite:** `#ffffff` und `#f8fafc`. Dazu das blaue Band (`#2563eb`) und die Fußzeile (`#0f172a`). Keine Farbverläufe.

## Typografie

Schrift: **Archivo** (Google Fonts, Gewichte 400, 500, 600, 700, 800, 900).

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
```

| Rolle | Größe | Gewicht | Laufweite | Zeilenhöhe |
| --- | --- | --- | --- | --- |
| Hero H1 | `clamp(46px, 6.4vw, 92px)` | 900 | `-0.035em` | 0.92 |
| Seiten-H1 | `clamp(34px, 4.6vw, 64px)` | 900 | `-0.03em` | 1 |
| Abschnitts-H2 | `clamp(30px, 3.4vw, 46px)` | 900 | `-0.025em` | 1 |
| Wiki-H2 | `clamp(20px, 2.2vw, 28px)` | 900 | `-0.02em` | 1.15 |
| Karten-H3 | 17–22px | 800 | `-0.015em` | 1.2–1.25 |
| Hero-Lead | `clamp(19px, 2vw, 24px)` | 600 | normal | 1.35 |
| Abschnitts-Lead | 17px | 400 | normal | 1.55–1.6 |
| Fließtext | 15–16px | 400 | normal | 1.55–1.7 |
| Kleintext | 13–14px | 400 | normal | 1.5–1.55 |
| Versalien-Beschriftung | 10–13px | 800–900 | `0.06em`–`0.14em` | — |
| Ziffern (Zyklus, Schritte) | 12–13px | 900 | `0.08em`–`0.1em` | — |
| Kennzahl groß | 20–40px | 900 | normal | 1.1 |
| Codeblock | 13px | 400 | normal | 1.65–1.7 |

Maximale Zeilenlängen: Fließtext `62–68ch`, Leads `52–56ch`, Kleintext in Spalten `38–52ch`. `text-wrap: pretty` auf Absätzen, `text-wrap: balance` auf dem Hero-H1.

## Griechische Versalien — verbindlich

Griechische Großbuchstaben tragen **keine** Akzente. Jedes Element mit `text-transform: uppercase` und griechischem Text braucht den Sprachhinweis, sonst rendert der Browser `ΛΉΨΗ` statt `ΛΗΨΗ`.

```html
<html lang="el">
```

Englische Begriffe im griechischen Text einzeln ausnehmen:

```html
Λήψη <span lang="en">App</span>
<span lang="en">Tier 1</span> — Πλατφόρμα
```

Betroffene Begriffe im Bestand: App, APK, Beta, Alpha, Live, Tier 1–3, CRI, CPLM, GitHub, PDF, Forum, SSO, API, Roadmap, Whitepaper, Modules, Database, Wiki Home, Android, iOS, F-Droid, PWA, Secure Enclave, Ed25519, Cookies, Trackers, Open End, Epic, gates, Stack, Monorepo, Endpoints, Schemas, GDPR, k-Anonymity, Double opt-in, V1, V2, ANNOUNCED, OPEN END.

## Abstände

Abschnittspolster: `56px 24px` (große Abschnitte), `44–48px 24px` (Bänder), `36px 24px` (Wiki-Kopf).
Zellpolster im Raster: `22–28px`.
Inhaltsbreite: `max-width: 1320px; margin: 0 auto; padding: 0 24px`.

## Radien, Schatten, Rahmen

**Radius: 0 überall.** Keine Rundung, auch nicht bei Eingabefeldern und Schaltflächen (`border-radius: 0` explizit setzen, sonst greifen Browser-Vorgaben).

**Keine Schatten.** Die Struktur entsteht ausschließlich aus Rahmen.

Rahmenstärken:

- `2px solid #0f172a` — Abschnittstrenner, Kopfleiste unten, Tabellenkopf, Eingabefelder, Rasterrahmen
- `2px solid #e2e8f0` — Spaltentrenner, Zeilentrenner im Raster
- `2px solid #f1f5f9` — Listentrenner
- `4px solid #2563eb` — linker Akzentbalken an Hinweisblöcken

## Icons

**Lucide** (`https://unpkg.com/lucide@0.454.0/dist/umd/lucide.min.js`), `stroke-width: 1.75`, Größen 15–24px, Farbe `#2563eb` oder `#64748b`.

Nach jedem Render `lucide.createIcons()` aufrufen.

**Keine Emoji.** Der Bestand nutzt Emoji als Icon-System (🔒, ⚠️, 📋, 👥, ℹ️) — diese sind durch Lucide-Icons zu ersetzen. Zuordnung:

| Bestand | Lucide |
| --- | --- |
| 🔒 | `lock` |
| ⚠️ | `alert-triangle` |
| ℹ️ | `info` |
| 📋 | `clipboard-list` |
| 👥 | `users` |
| 🔐 | `shield-check` |
| 📊 | `bar-chart-3` |
| 🗳️ | `landmark` |
| 📍 | `map-pin` |
| 🤖 | `bot` |
| 📖 | `book-open` |
| 💾 | `database` |
| 🧭 | `compass` |

---

# Layout-System

Das ganze Design steht auf einem **sichtbaren Raster**. Das ist die zentrale Entscheidung — alles andere folgt daraus.

## Regeln

1. **Abschnitte sind durch `2px solid #0f172a` getrennt**, nicht durch Weißraum. Jeder `<section>` bekommt `border-bottom`.
2. **Spalten sind durch `2px solid #e2e8f0` getrennt.** Die Trennlinie gehört an das Element, das die volle Zeilenhöhe füllt — nicht an die kürzere Spalte, sonst bricht die Linie mittendrin ab.
3. **Zellen haben asymmetrisches Polster:** die erste Zelle `padding-left: 0`, die letzte `padding-right: 0`, dazwischen beidseitig. So sitzt der Inhalt bündig an der Inhaltsbreite und die Trennlinien sitzen mittig zwischen den Zellen.
4. **Alles ist linksbündig.** Keine zentrierten Überschriften, keine zentrierten Schaltflächenlabels, keine zentrierten Leads.
5. **Keine Karten mit Rahmen um alles.** Ein „Kartenraster" ist ein Raster mit Zelltrennern, nicht eine Reihe umrahmter Boxen.

## Rastermuster

Gleichmäßige Aufteilung, umbruchfähig:

```css
display: grid;
grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
gap: 0;
border-top: 2px solid #e2e8f0;
```

Feste Spaltenzahl, wenn der Inhalt sie verlangt (etwa die 6 Zyklusphasen):

```css
grid-template-columns: repeat(6, minmax(0, 1fr));
```

Zellen brauchen `min-width: 0`, sonst sprengt langer Text das Raster.

## Umbruch bei Kachelrastern

Wenn ein Raster mit `auto-fit` umbricht, hängen Zellrahmen in der Luft. Lösung: das Raster bekommt den Rahmen als Hintergrund und die Zellen einen Grund.

```css
.grid { display: grid; gap: 2px; background: #e2e8f0; padding: 2px; }
.grid > * { background: #fff; }
```

## Klickflächen

Mindestens 44px. Schaltflächen mit fester `min-height: 48px`, nicht abgeleitet aus Polster + Zeilenhöhe — sonst verschiebt sich die Kopfleiste bei Umbruch.

## Fluide Breite

Keine festen Breiten außer der Inhaltsbreite. Raster mit `minmax(0, 1fr)`, kein `white-space: nowrap` auf Textboxen, keine festen Höhen auf Inhaltsboxen.

---

# Bildschirm 1: Startseite

Reihenfolge der Abschnitte. Jeder trägt `border-bottom: 2px solid #0f172a`.

| # | Abschnitt | Grund | Aufbau |
| --- | --- | --- | --- |
| 1 | Hero | `#fff` | 2 Spalten: links Anspruch + Aktionen, rechts Απόκλιση-Kennzahlen + Vertrauensband |
| 2 | Πώς λειτουργεί (`#how`) | `#fff` | 4 Spalten, Ziffern 01–04 |
| 3 | Ο Κύκλος της Δημοκρατίας (`#live`) | `#fff` | 6 Spalten Phasen, darunter 2 Spalten: Αντιπροσωπευτικότητα + CPLM |
| 4 | Επαλήθευση (`#transparency`) | `#f8fafc` | 2 Spalten: Beta / Alpha |
| 5 | Τι προσφέρει (`#features`) | `#fff` | 3×3 Raster |
| 6 | εκπρόσωπος | `#fff` | 2 Spalten: links Beschreibung, rechts 2 gestapelte Einträge |
| 7 | Ιστορικό πλαίσιο | `#2563eb` | 2 Spalten: links Titel + Grafik, rechts Zitat |
| 8 | Πνύκα Forum (`#forum`) | `#fff` | 4 Spalten Merkmale + Aktionsleiste |
| 9 | Roadmap (`#roadmap`) | `#f8fafc` | 2×2 Raster: Beta, Alpha 0.1, V1, V2 |
| 10 | Τεκμηρίωση (`#wiki-section`) | `#fff` | 3×3 Raster Wiki-Einstiege |
| 11 | Τι πρέπει να γνωρίζετε | `#fff` | 4 Spalten |
| 12 | Ενημέρωση + Επικοινωνία (`#newsletter`, `#contact`) | `#f8fafc` | 2 Spalten |
| 13 | Fußzeile | `#0f172a` | 4 Spalten + Leiste |

## Was sich gegenüber dem Bestand ändert — und warum

**Der Bestand hat 15 Abschnitte und 13 Navigationspunkte.** Kein Handlungspfad. Die Änderungen:

1. **Hero trägt genau eine Primäraktion** (Λήψη APK), dazu zwei sekundäre (Πώς λειτουργεί, GitHub). Bisher standen mehrere gleichgewichtige Aktionen nebeneinander.

2. **Die Απόκλιση Πολιτών–Βουλής steht im Hero**, rechte Spalte. Das ist das Alleinstellungsmerkmal der Plattform und lag im Bestand weit unten. Mit ehrlichem Leerzustand (`—`), nicht mit Beispielzahlen.

3. **Kopfnavigation auf 5 Punkte reduziert:** Πλατφόρμα, Ψηφοφορίες, Roadmap, Τεκμηρίωση, Community. Dazu Sprachwahl und die Primäraktion. Forum, Tickets, Δήμος, Legal, Mirror wandern in die Fußzeile.

4. **Emoji-Icons durch Lucide ersetzt** (Zuordnung oben).

5. **Fünf Akzentfarben auf eine reduziert.** Nur `#2563eb`.

6. **Farbverläufe entfernt.** Der Bestand nutzt `linear-gradient(135deg, #eff6ff, #f8fafc)` im Newsletter-Abschnitt — ersetzt durch flaches `#f8fafc`.

7. **Rundungen entfernt.** Bestand nutzt `border-radius: 0.4rem`–`0.5rem` — überall 0.

## Hero, linke Spalte

```
[Abzeichen]  Beta — Ανοιχτός Κώδικας       ← 2px Rahmen #0f172a, 7px blaues Quadrat
[H1]         εκκλησία / του έθνους         ← zweite Zeile in #2563eb
[Lead]       Η φωνή σου μετράει. Ψήφισε για πραγματικά νομοσχέδια.
[Kleintext]  Τέσσερα βήματα. Χωρίς λογαριασμό. Χωρίς email.
[Aktionen]   Λήψη APK (blau) · Πώς λειτουργεί (Rahmen) · GitHub (nur Text)
```

Polster: `64px 48px 56px 0`, rechter Rahmen `2px solid #e2e8f0`.

## Hero, rechte Spalte

```
[Kopf]    Απόκλιση Πολιτών — Βουλής          [● Live]   ← Unterstrich 2px #0f172a
[2 Spalten] Απόφαση Βουλής —  |  Βούληση Πολιτών —
[3 Spalten] Tier 1 —  |  Tier 2 —  |  Tier 3 —
[Text]    Πόσο αντιπροσωπεύει η Βουλή…
[Link]    Προβολή τρεχουσών →
[Band]    100% Ανοιχτός κώδικας | GDPR | 0 Cookies · Trackers | Ed25519
```

## Ιστορικό πλαίσιο — blaues Band

Das Zitat war im Bestand ein einziger Block. Neu:

- **Linke Spalte:** Versalien-Beschriftung „Ιστορικό πλαίσιο", H2 „Η Εκκλησία / του Δήμου", ein Satz Lead, darunter die Pnyx/Akropolis-Grafik.
- **Rechte Spalte:** erster Satz des Zitats als Lead (`clamp(19px, 1.7vw, 23px)`, Gewicht 600, weiß), dann `2px` Trennlinie, dann zwei Absätze `16px/1.7` in `#eff6ff`.

Das Zitat ist **wortgetreu** zu übernehmen, einschließlich der französischen Anführungszeichen «».

**Grafik:** `assets/pnyx-acropolis-white.png` — im Textfluss direkt hinter dem Lead, `width: 116%`, `max-width: 520px`, `margin: 28px 0 -170px -3%`, `opacity: 0.17`. Absichtlich im Fluss und nicht absolut positioniert, damit der Bezug zum Text bei jeder Fensterbreite hält.

## Ο Κύκλος της Δημοκρατίας

Sechs Phasen, Beschriftungen wortgetreu aus `docs/animations/svg/bill-lifecycle-ring.svg`:

| # | Titel | Unterzeile |
| --- | --- | --- |
| 01 | Ανακοίνωση | AI σύνοψη |
| 02 | Ενεργό | Ψηφοφορία |
| 03 | Πολίτες | Υπέρ / Κατά |
| 04 | 24ω | Παράθυρο |
| 05 | Βουλή | Απόφαση |
| 06 | Αρχείο | Open End · Arweave |

Unterzeile des Abschnitts: `ANNOUNCED → OPEN END · χωρίς νομική δέσμευση`.

## Αντιπροσωπευτικότητα Βουλής

Aufbau nach `docs/animations/svg/divergence-balance.svg`: **zwei Vergleichsbalken**, nicht eine Prozentskala.

```
Απόφαση Βουλής    —        Βούληση Πολιτών   —
[Balken 14px, 2px Rahmen]  [Balken 14px, 2px Rahmen]
[Hinweis] Απόκλιση εμφανίζεται όταν η θεσμική απόφαση και η δημόσια ψήφος διαφέρουν.
[4 Kennzahlen] Αντιπροσωπευτικότητα | Μέση Απόκλιση | Ψηφοφορίες | Ψήφοι Πολιτών
[Stimmungsindikator]
```

### Stimmungsindikator — Anforderung

Ein Smiley in Schwarz/Weiß als Strichzeichnung, `104×104px`, `viewBox="0 0 120 120"`. Kein Farbeinsatz.

- Kreis: `cx=60 cy=60 r=55`, `fill: none`, `stroke: #0f172a`, `stroke-width: 4`
- Augen: `r=6`, gefüllt `#0f172a`, bei `(42,47)` und `(78,47)`
- Mund: `stroke-width: 5`, `stroke-linecap: round`, `fill: none`

Mundform nach Wert der Repräsentativität:

| Bereich | Zustand | Pfad |
| --- | --- | --- |
| ≥ 50% | Lächeln | `M36 74 Q60 96 84 74` |
| 45–50% | Neutral | `M36 80 L84 80` |
| < 45% | Traurig | `M36 88 Q60 66 84 88` |

Ohne Daten: neutral, mit dem Text „Αναμονή πραγματικών δεδομένων. Ο δείκτης ενεργοποιείται με την πρώτη ολοκληρωμένη ψηφοφορία."

Begleittext rechts daneben: Versalien-Beschriftung „Δείκτης Διάθεσης", darunter der Zustandstext, darunter die Legende „≥50% χαμόγελο · 45–50% ουδέτερο · &lt;45% λυπημένο".

Zustandstexte mit Wert:

- Lächeln: `Η Βουλή αντιπροσωπεύει τη γνώμη των πολιτών στο {n}%.`
- Neutral: `Οριακή αντιπροσωπευτικότητα: {n}%.`
- Traurig: `Η Βουλή αποκλίνει από τη γνώμη των πολιτών: {n}%.`

## Πολιτικός Καθρέφτης (CPLM)

Quadranten-Diagramm, Achsen **wortgetreu und in der Ausrichtung** aus `docs/animations/svg/cplm-compass.svg`:

- Oben: **Αυταρχικό**
- Unten: **Ελευθεριακό**
- Links: **Αριστερά**
- Rechts: **Δεξιά**

Die Achsen sind in dieser Richtung verbindlich — vertikal gedreht ist die Aussage falsch.

Aufbau: `2px solid #0f172a` Rahmen, `aspect-ratio: 1.35`, innen 2×2 mit `2px solid #e2e8f0` Trennern, obere rechte Zelle `#f8fafc` getönt. Mittelpunkt: `14×14px`, `3px solid #2563eb`, weiß gefüllt. Darunter der Text „Αναμονή δεδομένων".

Vier Kennzahlen darunter: Οικονομία (X), Κοινωνία (Y), Ψηφοφόροι, Τεταρτημόριο.

Fußnote: `Live 6h · Σωρευτική θέση κοινωνίας από ανώνυμες ψήφους πολιτών. Περιλαμβάνει όλες τις ψήφους (και Open End).`

## Newsletter-Formular

Felder wortgetreu aus `docs/index.html:1398–1425`:

**Συχνότητα** (Radio, `name="freq"`):
- `weekly` — Εβδομαδιαίο — **vorausgewählt**
- `monthly` — Μηνιαίο

**Θέματα** (Checkbox):
- Ψηφοφορίες — **vorausgewählt**
- Αποτελέσματα — **vorausgewählt**
- Νέες Προτάσεις
- Σύστημα
- Ειδήσεις

Dann E-Mail-Feld (`placeholder="email@example.com"`) und Schaltfläche Εγγραφή, direkt aneinander (das Feld ohne rechten Rahmen, damit die 2px-Linie nicht doppelt liegt).

Fußnote mit `lock`-Icon: `Double opt-in · GDPR · Θα λάβετε email επιβεβαίωσης`.

Radios und Checkboxen: `18×18px`, `accent-color: #2563eb`, Label als `<label>` mit `min-height: 44px`.

Endpunkt: `POST https://api.ekklesia.gr/api/v1/newsletter/subscribe`.

## Chat-Einstieg

Fest positioniert unten rechts, `right: 24px; bottom: 24px`, `z-index: 60`. Grund `#0f172a`, weiße Schrift, `min-height: 52px`, `message-circle`-Icon, Text „Ρωτήστε την εκκλησία".

---

# Bildschirm 2: Ψηφοφορίες

Im Bestand war das ein Abschnitt der Startseite (`#votes`). Neu eine eigene Seite.

**Kopf:** Versalien-Beschriftung „Βουλή · Περιφέρεια · Δήμος", H1 „Ψηφοφορίες σε Εξέλιξη", Lead, darunter drei Tabs mit `3px solid #2563eb` unter dem aktiven.

Tabs: Τρέχουσες (`/el/bills`), Τελευταίες 24ω (`?status=WINDOW_24H`), Αποτελέσματα (`/el/results`).

**Hauptspalte:** Abstimmungszeile mit Ebenen-Abzeichen (`#0f172a` Grund, weiße Versalien), Status, Titel, AI-Sinopsis, dreiteiliger Balken (Υπέρ `#2563eb` / Κατά `#cbd5e1` / Αποχή `#f1f5f9`, `2px solid #0f172a` Rahmen), Aktionen Ψηφίστε + Forum.

**Seitenleiste:** die 6 Phasen als Liste, darunter CPLM-Kurzfassung.

---

# Bildschirm 3: Λήψη

**Linke Spalte:** Drei Kanäle als Liste mit `2px` Trennern, nicht als Karten.

| Kanal | Version | Status | Ziel |
| --- | --- | --- | --- |
| Λήψη APK — Android | v1.0.32 · vC61 | Διαθέσιμο (blau) | GitHub Release |
| Google Play | vC61 υποβλήθηκε | Υπό έλεγχο (Rahmen) | `play.google.com/apps/testing/ekklesia.gr` |
| F-Droid | v1.0.29 · vC584 | Διαθέσιμο (blau) | `f-droid.org/packages/ekklesia.gr/` |

Darunter der Warnhinweis zum Installationskanal (wortgetreu, `alert-triangle`-Icon, `4px solid #2563eb` links).

**Rechte Spalte:** iPhone-Anleitung in 3 Schritten, darunter die vier Screenshots in einem 2px-Raster mit `filter: grayscale(1)`.

Bildquellen: `https://ekklesia.gr/assets/screenshots/screenshot-{home,votes,politicians,polis}.jpg`.

---

# Bildschirm 4: Τεκμηρίωση (Wiki)

Das ist das **Muster für alle 14 Wiki-Seiten**.

## Aufbau

Dreispaltig: `minmax(220px,260px) minmax(0,1fr) minmax(180px,220px)`.

1. **Links — Seitenleiste.** Alle 14 Wiki-Seiten, aktive Seite mit `4px solid #2563eb` links und `#f8fafc` Grund. `position: sticky; top: 104px; max-height: calc(100vh - 104px); overflow-y: auto`.
2. **Mitte — Inhalt.** `border-left` und `border-right` je `2px solid #e2e8f0`. Die Trennlinie gehört hierher, nicht an die Seitenleiste — der Artikel füllt die Zeilenhöhe, die Seitenleiste nicht.
3. **Rechts — Seiten-Inhaltsverzeichnis.** `position: sticky; top: 104px`.

**Seitenkopf** über der Dreispaltigkeit, Grund `#f8fafc`: Brotkrumen (εκκλησία · Τεκμηρίωση · Seitenname), H1, Lead, dazu „Τελευταία ενημέρωση" und „Επεξεργασία στο GitHub".

## Umbruch

```css
@media (max-width: 1180px) {
  /* Inhaltsverzeichnis weg, Artikel bekommt die Breite */
  grid-template-columns: minmax(220px,250px) minmax(0,1fr);
  [toc] { display: none; }
  [article] { border-right: 0; padding-right: 0; }
}
@media (max-width: 860px) {
  /* alles gestapelt, Seitenleiste als Streifen oben */
  grid-template-columns: minmax(0,1fr);
  [nav] { position: static; max-height: none; overflow: visible;
          border-bottom: 2px solid #0f172a; padding: 24px 0 28px; }
  [article] { border-left: 0; padding-left: 0; }
}
```

## Inhaltstypografie — verbindlich für alle 14 Seiten

| Element | Stil |
| --- | --- |
| H2 (Hauptabschnitt) | `clamp(20px,2.2vw,28px)`, 900, `-0.02em`, `padding-bottom: 12px`, `border-bottom: 2px solid #0f172a`, `margin-top: 44px` |
| H3 (Unterabschnitt) | `13px`, 900, `0.12em`, Versalien, Farbe `#2563eb`, `margin-top: 32px` |
| Absatz | `16px/1.7`, `#334155`, `max-width: 68ch`, `text-wrap: pretty` |
| Liste | `15px/1.7`, Einzug `22px` |
| Tabelle | Kopf `11px/900/0.1em` Versalien `#64748b` auf `2px solid #0f172a`; Zellen `14px/1.6`, erste Spalte 800 in `#0f172a`, Zeilentrenner `2px solid #f1f5f9`; Wrapper `overflow-x: auto`, `min-width: 420px` |
| Codeblock | Grund `#0f172a`, Text `#e2e8f0`, `13px/1.7`, Monospace, `padding: 20px`, `overflow-x: auto`; Kommentare in `#64748b` |
| Hinweisblock | `4px solid` links (`#2563eb` neutral, `#1d4ed8` Warnung), Grund `#f8fafc`, `padding: 16px 18px`, Lucide-Icon `20px` |
| Ablaufkette | Knoten mit `2px` Rahmen (`#2563eb` betont, `#cbd5e1` neutral), `12px/800` Versalien, `arrow-right`-Icons dazwischen, Wrapper `2px solid #e2e8f0` auf `#f8fafc` |
| Verweisraster am Fuß | 2px-Rasterhintergrund, Zellen weiß, je Titel + `arrow-right` |

Codeblöcke und Tabellen scrollen **intern**, nie die Seite.

## Auftrag: Wiki-Seiten

Die Beispielseite Αρχιτεκτονική ist vollständig und wortgetreu aus `docs/wiki/architecture.html` aufgebaut. Die restlichen 13 Seiten sind nach demselben Muster zu überführen:

| Datei | Seitentitel | Umfang | Besonderheit |
| --- | --- | --- | --- |
| `docs/wiki/index.html` | Αρχική | 20 KB | Übersichtsraster über alle Seiten |
| `docs/wiki/architecture.html` | Αρχιτεκτονική | 32 KB | **fertig — als Vorlage nutzen** |
| `docs/wiki/security.html` | Ασφάλεια | 42 KB | viele Codeblöcke |
| `docs/wiki/zk-voting.html` | ZK Voting | 15 KB | Ablaufketten |
| `docs/wiki/api.html` | API | 34 KB | 16 Endpunkte — als Tabelle, nicht als Karten |
| `docs/wiki/database.html` | Database | 20 KB | 13 Tabellen — Schema-Tabellen |
| `docs/wiki/modules.html` | Modules | 28 KB | MOD-01 bis MOD-19 — Tabelle |
| `docs/wiki/privacy.html` | Ιδιωτικότητα | 28 KB | GDPR-Abschnitte |
| `docs/wiki/broadcasting.html` | Broadcasting | 29 KB | Push + Newsletter |
| `docs/wiki/delete-account.html` | Διαγραφή Λογαριασμού | 26 KB | Schrittanleitung — Ziffernmuster wie `#how` |
| `docs/wiki/roadmap.html` | Roadmap | 65 KB | **umfangreichste Seite** — 4 Phasen als 2×2 Raster wie auf der Startseite |
| `docs/wiki/whitepaper.html` | Whitepaper | 25 KB | Langtext — Inhaltsverzeichnis besonders wichtig |
| `docs/wiki/contributing.html` | Contributing | 17 KB | Setup-Codeblöcke |
| `docs/wiki/faq.html` | FAQ | 110 KB | **Sonderfall — siehe unten** |

### FAQ — Sonderfall

`faq.html` nutzt aufklappbare Einträge (`.faq-q` / `.faq-a` mit `classList.toggle('open')`) und enthält JSON-LD für strukturierte Daten.

Im neuen Design:

- Aufklappmechanik beibehalten, Interaktion nicht ändern.
- Fragen als `16px/800` in `#0f172a`, Zeilentrenner `2px solid #f1f5f9`.
- Kein Rahmen um den Einzeleintrag, keine Rundung, kein Schatten.
- Aufklappmarker: `plus` / `minus` (Lucide) rechts, nicht ein gedrehtes Dreieck.
- Antwortbereich: `16px/1.7` in `#334155`, Polster `0 0 20px`.
- **JSON-LD unverändert erhalten** — es steuert die Google-Darstellung.
- Die Kategorien der Seite bleiben; sie werden zu H2 nach obiger Definition.

### Vorgehen pro Seite

1. Bestandsdatei lesen. **Alle Texte wortgetreu übernehmen**, auch die `data-el`/`data-en`-Paare für beide Sprachen.
2. Seitenkopf aufbauen: Brotkrumen, H1, Lead aus dem bestehenden Einleitungstext.
3. Inhalt in die Typografie oben übertragen. Bestehende Karten/Boxen werden Raster oder Tabellen.
4. Seitenleiste identisch auf allen 14 Seiten, aktive Seite markieren.
5. Inhaltsverzeichnis rechts aus den H2 der Seite erzeugen.
6. Emoji durch Lucide ersetzen.
7. `lang="el"` prüfen, englische Begriffe einzeln auszeichnen.

---

# Auftrag: restliche Seiten

Alle 35 HTML-Dateien unter `docs/`. Zuordnung zum Design-Muster:

## Landing-Muster (Raster + Bänder)

| Datei | Muster |
| --- | --- |
| `docs/index.html` | **Bildschirm 1** — 1:1 aus der Vorlage |
| `docs/community.html` | Landing-Muster; Live-Statistiken als Kennzahlenraster wie im Hero; Kostenrechner als Tabelle |
| `docs/representative.html` | Landing-Muster; Abschnitt εκπρόσωπος der Startseite als Vorbild |
| `docs/municipality/index.html` | Landing-Muster, kurz |
| `docs/municipality/article.html` | **Wiki-Muster** (Langtext, 105 KB) |
| `docs/govgr-dimos.html` | Landing-Muster; enthält ein Formular mit Einverständnis-Checkbox → Formularregeln oben |
| `docs/demo/index.html` | Landing-Muster; Emoji-Karten → Lucide-Raster |

## Wiki-Muster (Dreispalter)

Alle 14 Dateien unter `docs/wiki/` plus `docs/municipality/article.html`.

## Dokumentmuster (schmal, einspaltig)

| Datei | Hinweis |
| --- | --- |
| `docs/legal.html` | Impressum — einspaltig, `max-width: 68ch`, H2-Regeln wie Wiki |
| `docs/mirror-setup.html` | Anleitung — Codeblöcke wie Wiki |

## Werkzeugseiten (eigene Behandlung)

| Datei | Hinweis |
| --- | --- |
| `docs/tickets/index.html` | POLIS Ticket Board — Listenmuster wie Abstimmungszeile |
| `docs/tickets/auth/…` | Anmeldeseite — Formularregeln |
| `docs/sso-verify.html` | Zwischenseite — zentriert ist hier zulässig, da reiner Statusbildschirm |
| `docs/demo/admin.html` | Demo-Verwaltung — Tabellenmuster |
| `docs/demo/bills.html` | Demo-Abstimmungen — Bildschirm 2 als Vorbild |

## Einbettungen — nicht anfassen

`docs/embed/qr-login.html`, `docs/embed/results.html`, `docs/embed/vote.html` und die drei Weiterleitungen unter `docs/votes/` (je unter 600 Byte).

Die `embed/`-Seiten laufen in `<iframe>` auf fremden Seiten. Sie brauchen keine Kopfleiste, keine Fußzeile und keine feste Breite. Nur Schrift, Farben und Radius (0) angleichen — Layout unverändert.

---

# Verhalten und Zustände

## Navigation

Die Vorlage schaltet die vier Bildschirme über einen internen Zustand um. **Im Repo sind es echte Seiten** — die Umschaltung ist nur ein Vorführmittel der Vorlage.

Kopfnavigation → echte Ziele:

| Beschriftung | Ziel |
| --- | --- |
| Πλατφόρμα | `/` |
| Ψηφοφορίες | `/el/bills` |
| Roadmap | `/wiki/roadmap.html` |
| Τεκμηρίωση | `/wiki/` |
| Community | `/community.html` |
| EN | Sprachumschaltung (bestehender Mechanismus `data-el`/`data-en`) |
| Λήψη App | `#download` bzw. `/download` |

## Kopfleiste

`position: sticky; top: 0; z-index: 50`, Grund `#fff`, `border-bottom: 2px solid #0f172a`, `min-height: 86px`.

**Wichtig:** Kein Vorfahre der Kopfleiste darf `overflow-x: hidden` tragen — das macht ihn zum Scroll-Container und `position: sticky` greift auf der ganzen Seite nicht mehr. Wenn seitliches Überlaufen abgeschnitten werden muss, `overflow-x: clip` verwenden.

Die Navigation bricht bei schmaler Breite als rechtsbündige zweite Zeile um (`flex-wrap: wrap; justify-content: flex-end`). Die Primäraktion behält `min-height: 48px`.

## Zustände

| Zustand | Umsetzung |
| --- | --- |
| Hover Primäraktion | `#1d4ed8` |
| Hover Sekundäraktion | Rahmen `#2563eb`, Text `#1d4ed8` |
| Hover Textlink | `#2563eb` |
| Hover Rasterzelle (klickbar) | Grund `#f8fafc` |
| Tastaturfokus | `outline: 2px solid #2563eb; outline-offset: 2px` — nie der Browser-Standard |
| Aktiver Tab | `border-bottom: 3px solid #2563eb`, Text `#0f172a` |
| Aktive Wiki-Seite | `border-left: 4px solid #2563eb`, Grund `#f8fafc`, Gewicht 900 |
| Deaktiviert | Deckkraft 45% |
| `::selection` | `#dbeafe` |

Standard-Linkfarben in der Grundlage festlegen (`a` und `a:hover`), sonst rendern nachträglich eingefügte Links in Browser-Blau.

## Leerzustände

Verbindlich: **keine Beispielzahlen.** Alle Kennzahlen ohne Daten als `—` mit einem erklärenden Kleintext. Der Bestand zeigt an einigen Stellen Platzhalterwerte — die sind zu entfernen.

Betroffen: Απόφαση Βουλής, Βούληση Πολιτών, Tier 1–3, Αντιπροσωπευτικότητα, Μέση Απόκλιση, Ψηφοφορίες, Ψήφοι Πολιτών, CPLM X/Y/Ψηφοφόροι/Τεταρτημόριο, Stimmungsindikator.

## Datenquellen

| Anzeige | Endpunkt |
| --- | --- |
| Newsletter-Statistik | `GET /api/v1/newsletter/stats` |
| Newsletter-Anmeldung | `POST /api/v1/newsletter/subscribe` |
| Abstimmungen | `GET /api/v1/bills` |
| Ergebnisse | `GET /api/v1/results` |
| Regionen | `GET /api/v1/periferia` |
| Gemeinden | `GET /api/v1/periferia/{id}/dimos` |

Basis: `https://api.ekklesia.gr`.

---

# Barrierefreiheit

- **Kontrast:** Fließtext mindestens 4.5:1. `#64748b` auf `#fff` ist der hellste zulässige Textwert; `#94a3b8` nur auf `#0f172a`.
- Fließtext im Akzent nie in `#2563eb` — `#1d4ed8` verwenden.
- Auf dem blauen Band: Fließtext `#eff6ff`, Beschriftungen `#bfdbfe`, Überschriften `#ffffff`. Keine transparenten Weißtöne für Text.
- Klickflächen mindestens 44px.
- `lang="el"` am Wurzelelement, englische Begriffe einzeln.
- Dekorative Grafiken: `alt=""` und `aria-hidden="true"`.
- Tastaturfokus sichtbar (siehe Zustände).

---

# Assets

| Datei | Herkunft | Verwendung |
| --- | --- | --- |
| `assets/ekklesia-mark.png` | freigestellt aus `docs/logo/ekklesia-play-icon-512.png` | Kopfleiste, 60px Höhe |
| `assets/ekklesia-mark-white.png` | dieselbe Quelle, invertiert | Fußzeile, 46px Höhe |
| `assets/pnyx-acropolis-white.png` | Vorlage des Auftraggebers, freigestellt | Ιστορικό πλαίσιο, Deckkraft 0.17 |
| `docs/logo/ekklesia-play-icon-512.png` | Repo | Quelle — nicht direkt einsetzen |

**Zum Logo:** Die Repo-Datei hat einen hellblauen Hintergrund (`#93c5fd`) eingebrannt. Die freigestellten PNGs haben echte Transparenz. Ideal wäre eine SVG-Fassung der Marke — dann diese verwenden.

**Zur Pnyx-Grafik:** Die Vorlage kam als JPG mit eingebranntem Transparenz-Schachbrett. Die freigestellte Fassung ist aus der Tusche extrahiert. Sie ist eine Zeichnung, kein Foto — wenn eine hochauflösende Illustration oder ein Foto vorliegt, an dieselbe Stelle setzen und die Deckkraft prüfen.

## Repo-SVGs als Referenz

`docs/animations/svg/` enthält fertige Diagramme. Sie sind **Strukturreferenz**, nicht zum Einbetten — sie sind für dunklen Grund mit Gold-Akzent gestaltet und animiert.

| Datei | Steuert |
| --- | --- |
| `cplm-compass.svg` | Achsenbeschriftung und -richtung des CPLM |
| `divergence-balance.svg` | Aufbau der Abweichungsanzeige |
| `bill-lifecycle-ring.svg` | Beschriftungen der 6 Zyklusphasen |
| `voting-flow.svg` | Ablauf Επαλήθευση → Ψήφος |
| `privacy-flow.svg` | Ablauf Ιδιωτικότητα |

Wenn diese Diagramme als Grafiken in die Seiten sollen, sind sie auf hellen Grund und die Palette oben umzufärben — das ist eine eigene Aufgabe, im Vorschlag nicht enthalten.

---

# Umsetzungsreihenfolge

1. **Grundlage:** Tokens, Archivo laden, Lucide laden, `lang="el"`, Kopfleiste, Fußzeile, Basiszustände. Als gemeinsames Teilstück, das alle Seiten einbinden.
2. **`docs/index.html`** — Bildschirm 1 vollständig. Das ist die Referenzimplementierung; alles Weitere folgt ihren Mustern.
3. **Wiki-Grundgerüst** — Dreispalter, Seitenleiste, Inhaltstypografie, Umbruchregeln. Danach `architecture.html` als erste Seite (Inhalt liegt in der Vorlage fertig vor).
4. **Wiki-Seiten** in der Reihenfolge: `index`, `security`, `api`, `database`, `modules`, `privacy`, `zk-voting`, `broadcasting`, `delete-account`, `contributing`, `whitepaper`, `roadmap`, `faq`.
5. **Landing-Seiten:** `community`, `representative`, `municipality/index`, `govgr-dimos`, `demo/index`.
6. **Dokumentseiten:** `legal`, `mirror-setup`, `municipality/article`.
7. **Werkzeugseiten:** `tickets`, `sso-verify`, `demo/admin`, `demo/bills`.
8. **Einbettungen:** nur Schrift, Farben, Radius.

---

# Abnahmekriterien

- [ ] Kein `border-radius` außer 0 in der ganzen Auslieferung
- [ ] Kein Farbverlauf
- [ ] Kein Schatten
- [ ] Keine Emoji als Icon
- [ ] Genau eine Akzentfarbe (`#2563eb`) plus `#1d4ed8` für Text
- [ ] Höchstens zwei Grundfarben pro Seite (`#fff`, `#f8fafc`)
- [ ] `lang="el"` gesetzt, griechische Versalien ohne Akzente
- [ ] Englische Begriffe einzeln mit `lang="en"` ausgezeichnet
- [ ] Alle Texte wortgetreu aus dem Bestand, beide Sprachen erhalten
- [ ] Keine Platzhalterzahlen — Leerzustände als `—`
- [ ] Kein `overflow-x: hidden` auf Vorfahren der Kopfleiste
- [ ] Kopfleiste bleibt beim Scrollen stehen
- [ ] Wiki-Seitenleiste bleibt stehen und scrollt intern
- [ ] Spaltentrenner brechen nicht mittendrin ab
- [ ] Kein seitliches Scrollen der Seite auf 360px Breite
- [ ] Codeblöcke und Tabellen scrollen intern
- [ ] Klickflächen mindestens 44px
- [ ] Tastaturfokus sichtbar, nicht Browser-Standard
- [ ] Newsletter: Εβδομαδιαίο, Ψηφοφορίες, Αποτελέσματα vorausgewählt und klickbar
- [ ] CPLM: Αυταρχικό oben, Ελευθεριακό unten
- [ ] Stimmungsindikator in Schwarz/Weiß, drei Zustände an den Schwellen 45% und 50%
- [ ] JSON-LD auf `faq.html` unverändert

---

# Dateien in diesem Paket

| Datei | Inhalt |
| --- | --- |
| `README.md` | dieses Dokument |
| `Ekklesia Redesign.dc.html` | Design-Referenz, vier Bildschirme |
| `support.js` | Laufzeit der Referenzdatei — nur damit sie im Browser öffnet |
| `assets/ekklesia-mark.png` | Logo freigestellt |
| `assets/ekklesia-mark-white.png` | Logo weiß |
| `assets/pnyx-acropolis-white.png` | Pnyx-Grafik freigestellt |
| `github.md` | Zuordnung Projekt ↔ Repo, Bildschirm-Quellen |

Die Referenzdatei im Browser öffnen: `Ekklesia Redesign.dc.html` doppelklicken. Die vier Bildschirme über die Kopfnavigation umschalten.

Der Stimmungsindikator hat in der Referenz einen Regler (Tweaks-Feld `representativeness`), um die drei Zustände durchzuprobieren. Der ist reines Vorführmittel — im Repo kommt der Wert aus der API.

---

# Offene Punkte für den Auftraggeber

1. **Pnyx-Grafik:** liegt als Zeichnung vor. Ein Foto oder eine hochauflösende Illustration wäre besser.
2. **Logo als SVG** wäre der Freistellung vorzuziehen.
3. **Repo-Diagramme** (`docs/animations/svg/`) einbetten oder nicht — dafür müssten sie umgefärbt werden.
4. **εκπρόσωπος-Screenshots** sind im Vorschlag nicht enthalten; falls gewünscht, in den Abschnitt εκπρόσωπος einsetzen.
5. **Einzelne Wiki-Seiten** sind als Muster spezifiziert, nicht als fertige Entwürfe. Falls Roadmap oder FAQ vor der Umsetzung als Entwurf gewünscht sind, sind das die beiden heikelsten.
