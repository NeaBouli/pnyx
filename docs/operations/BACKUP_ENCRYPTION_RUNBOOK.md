# Runbook: Backups verschlüsseln (ADR-007 S3)

Status: vorbereitet (Code bereit, **nicht aktiv**). Aktivierung = Gio-Gate. Der private Schlüssel ist ein Geheimnis und bleibt nur bei Gio.

---

## Für Gio – einfach erklärt, Schritt für Schritt

**Worum geht es?** Jede Nacht wird eine Sicherungskopie der Ekklesia-Datenbank auf einen zweiten Server geschickt. Bisher ist diese Kopie **unverschlüsselt**. Wer Zugriff auf den Backup-Server hätte, könnte darin lesen. Ab jetzt wird jede Kopie **vor** dem Versenden verschlüsselt, und **nur du** kannst sie wieder öffnen.

**Das Prinzip:** Es gibt zwei Schlüssel, die zusammengehören.
- Ein **öffentlicher Schlüssel** (beginnt mit `age1…`). Damit kann man nur **zuschließen**. Er kommt auf den Server, und es ist nicht schlimm, wenn ihn jemand sieht.
- Ein **privater Schlüssel** (beginnt mit `AGE-SECRET-KEY-…`). Damit kann man **aufschließen**. Den hast **nur du**: nie auf dem Server, nie im Chat, nie per E-Mail.

**Was du tust (ca. 15 Minuten, gio-1c begleitet dich):**
1. **Programm installieren** (auf deinem Mac): Im Terminal `brew install age` eingeben.
2. **Schlüsselpaar erzeugen:** `age-keygen -o ekklesia-backup-2026.key`. Das erzeugt die Datei `ekklesia-backup-2026.key` und zeigt eine Zeile `Public key: age1…`.
3. **Den öffentlichen Schlüssel weitergeben:** Nur die Zeile `age1…` an gio-1c oder gio-dd geben. Das ist kein Geheimnis.
4. **Den privaten Schlüssel sichern (wichtig!):** Die Datei `ekklesia-backup-2026.key` an **zwei** sicheren Orten ablegen:
   - auf einem USB-Stick, den du gut aufbewahrst (gern zusätzlich ausgedruckt: die Zeile `AGE-SECRET-KEY-…`);
   - auf der Synology in einem **verschlüsselten** Ordner.

   Danach die Datei vom Mac löschen, wenn du willst. **Ohne diesen Schlüssel sind alle verschlüsselten Backups wertlos.** Bitte also wirklich an zwei Orten.
5. **Probe machen:** Wir schicken dir eine verschlüsselte Backup-Datei. Du öffnest sie einmal mit deinem Schlüssel (Befehl unten, Abschnitt 4). Klappt das, ist alles richtig eingerichtet.
6. **Alte unverschlüsselte Backups löschen:** Erst wenn mindestens 7 verschlüsselte Backups da sind **und** die Probe geklappt hat, fragen wir dich nach einem Ja zum Löschen der alten, unverschlüsselten Kopien.

---

## Technischer Teil (für die Umsetzung)

### Wie es funktioniert
- `scripts/lib/backup-encrypt.sh` verschlüsselt das Archiv **auf dem Server** mit `age -r <öffentlicher Schlüssel>`, **bevor** es hochgeladen wird. Der Server kann nur verschlüsseln, nie entschlüsseln.
- Hochgeladene Dateien heißen `ekklesia-backup-<ts>.tar.gz.age`.
- `BACKUP_REQUIRE_ENCRYPTION=true`: Ohne gültigen Schlüssel oder ohne `age` bricht das Backup **vor** dem Upload ab. Nichts Unverschlüsseltes verlässt dann den Server.
- `sftp -b -`: Ein fehlgeschlagener Upload lässt das Backup jetzt fehlschlagen. Vorher wurde er als Erfolg gemeldet. Die Retention-Alarmierung greift dann.
- Lokale Kopien auf dem Prod-Server (`/opt/backups/ekklesia`) bleiben unverschlüsselt. Sie liegen auf demselben Host wie die Datenbank selbst.

### 1. Aktivieren (Server, nach Gios Ja; öffentlicher Schlüssel von Gio)
```bash
apt-get install -y age && age --version
# /etc/ekklesia-offsite-backup.env (root, Modus 600) ergänzen:
BACKUP_AGE_RECIPIENT=age1…            # öffentlicher Schlüssel aus Schritt 2
BACKUP_REQUIRE_ENCRYPTION=true
```
Dann einmal manuell `/usr/local/sbin/ekklesia-run-offsite-backup` starten. Im Log muss `Uploading ekklesia-backup-…tar.gz.age` stehen.

### 2. Folge-Skripte anpassen (gleiches Gate)
- `/usr/local/sbin/ekklesia-offsite-retention`: Namensmuster und Wächter „neuestes Backup > 1 MB“ auf `ekklesia-backup-*.tar.gz.age` erweitern.
- Der Restore-Check läuft auf dem Server ohne privaten Schlüssel absichtlich nicht mehr; er wird zur Offline-Probe (Abschnitt 4).

### 3. Ziel-Parameter
Upload-Ziel, Port, Pfad und SSH-Schlüssel kommen aus `/etc/ekklesia-offsite-backup.env`: `STORAGE_BOX_USER`, `STORAGE_BOX_HOST`, `STORAGE_BOX_PORT` (Skript-Default 23), `STORAGE_BOX_PATH` (Default `/backups/ekklesia`), `STORAGE_BOX_IDENTITY_FILE`. Für die Probe dieselben Werte verwenden. Nachsehen mit `grep -E "^STORAGE_BOX_(USER|HOST|PORT|PATH)=" /etc/ekklesia-offsite-backup.env`; der Identity-Pfad ist kein Geheimnis, die Schlüsseldatei selbst schon.

### 4. Probe-Wiederherstellung (offline)
gio-dd lädt eine Datei auf dem Prod-Server mit den Werten aus Abschnitt 3 herunter:
```bash
sftp -P "$STORAGE_BOX_PORT" -i "$STORAGE_BOX_IDENTITY_FILE" "$STORAGE_BOX_USER@$STORAGE_BOX_HOST:$STORAGE_BOX_PATH/daily/ekklesia-backup-<ts>.tar.gz.age" /tmp/
```
Sie geht an Gio (verschlüsselt, also unkritisch). Gio entschlüsselt sie auf seinem Rechner:
```bash
age --decrypt -i ekklesia-backup-2026.key -o restore.tar.gz ekklesia-backup-<ts>.tar.gz.age
tar -tzf restore.tar.gz            # zeigt db-<ts>.dump, redis-<ts>.rdb, alembic-<ts>.txt
```
Optional: Wiederherstellung in eine temporäre PostgreSQL (nicht Prod) und Zählungen vergleichen.

### 5. Alte unverschlüsselte Backups
Sie bleiben lesbar, bis sie gelöscht werden. Das Löschen ist ein eigenes Gio-Gate. Voraussetzung: mindestens 7 verschlüsselte Dailies und eine erfolgreiche Probe (Abschnitt 4). Danach Listenabgleich wie bei der Retention-Bereinigung.

### Rollback
`BACKUP_AGE_RECIPIENT` und `BACKUP_REQUIRE_ENCRYPTION` aus der env-Datei entfernen. Danach wird wieder unverschlüsselt gesichert (mit Log-Warnung). Bereits verschlüsselte Backups bleiben mit dem Offline-Schlüssel lesbar.

### Nachweis
`scripts/tests/test_backup_encryption.py`, läuft in CI im API-Job mit `age`:
- verschlüsselter Upload, Entschlüsselung mit Testschlüssel ergibt ein identisches Archiv, kein Klartext;
- `REQUIRE` ohne Schlüssel, ungültiger Schlüssel, `age` fehlt, `age`-Fehler mit Teilausgabe, Ausgabe ohne age-Header, zu kleine Ausgabe: jeweils kein Upload und keine Rest-Datei;
- fehlgeschlagener Upload lässt das Backup fehlschlagen;
- Default unverschlüsselt mit Warnung.

Mutation „Verschlüsselung übersprungen“ lässt 3 Tests fehlschlagen.
