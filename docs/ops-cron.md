# Betrieb: Cron für die Kennzahlen-Erinnerung (MEAS-03, D-07)

Der Host (shared mit polymarkt-watch) führt bereits Cron-Jobs per `docker exec`/`docker compose` aus. Für nd-content kommt genau eine Zeile dazu; sie schreibt die fällige Snapshot-Liste als JSON, die die Handy-UI unter `/due` anzeigt.

```cron
*/30 * * * * cd /home/nd-content && /usr/bin/docker compose run --rm ndc metrics due --write /data/due.json >> /var/log/nd-content-due.log 2>&1
```

- **Warum 30 min:** die Fenster (24 h: 20–30 h, 72 h: 66–84 h, 7 d: 156–192 h) sind Stunden breit; häufiger bringt nichts, seltener verpasst nichts.
- **Ressourcen:** `ndc` ist auf 1 GB / 1 CPU gekappt, Laufzeit wenige Sekunden; keine Netzwerkzugriffe.
- **Sicherheit:** `--write` akzeptiert nur Pfade unter `/data`; die UI liest ausschließlich den festen Pfad `/data/due.json`.
- **Installation (Host-Aktion des Operators, Plan 03-05 Vorflug):** `crontab -e` als root, Zeile einfügen. Prüfen mit `crontab -l | grep "metrics due"` und nach spätestens 30 min `cat /home/nd-content-volumes/data/due.json`.
- **Manuell auslösen:** `docker compose run --rm ndc metrics due --write /data/due.json`.
