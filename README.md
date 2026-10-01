<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=waving&color=0:0f172a,100:0ea5e9&height=200&section=header&text=checkmk_scripts&fontSize=42&fontColor=ffffff&animation=fadeIn&fontAlignY=35&desc=Python-Automatisierung%20f%C3%BCr%20die%20Checkmk%20REST%20API&descAlignY=55&descSize=16" width="100%"/>
</p>

<p align="center">
  <img src="https://readme-typing-svg.demolab.com/?font=Fira+Code&size=20&pause=1200&color=0EA5E9&center=true&vCenter=true&width=600&lines=Checkmk+REST+API+%E2%80%A2+Python;Passw%C3%B6rter+zur%C3%BCcksetzen+per+Skript;Downtimes%2C+Hosts+%26+Problem-Reports;Erweiterbar+um+weitere+Tools" alt="Typing SVG" />
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.8+-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/checkmk-REST%20API-FF6600?style=for-the-badge&logo=checkmk&logoColor=white" />
  <img src="https://img.shields.io/github/last-commit/withakedo/checkmk_scripts?style=for-the-badge&color=0EA5E9&labelColor=0f172a" />
  <img src="https://img.shields.io/github/repo-size/withakedo/checkmk_scripts?style=for-the-badge&color=0EA5E9&labelColor=0f172a" />
  <img src="https://img.shields.io/github/stars/withakedo/checkmk_scripts?style=for-the-badge&color=0EA5E9&labelColor=0f172a" />
</p>

<p align="center">
  Sammlung kleiner, eigenständiger Python-Skripte zur Automatisierung wiederkehrender Aufgaben über die <b>Checkmk REST API</b>.
</p>

---

### 📑 Inhalt

- [Über das Projekt](#-über-das-projekt)
- [Skripte](#-skripte)
- [Voraussetzungen](#-voraussetzungen)
- [Installation](#-installation)
- [Konfiguration](#-konfiguration)
- [Verwendung](#-verwendung)
- [Roadmap](#-roadmap)

---

### 📌 Über das Projekt

Jedes Skript in diesem Repo ist bewusst **schlank und ohne Framework** gehalten – ein `.py`-File, eine `requests`-Session, ein klarer Zweck. Gedacht für den schnellen Einsatz auf der Kommandozeile oder als Baustein in größeren Automatisierungs-Workflows (z. B. Rundeck).

---

### 🧩 Skripte

| Skript | Beschreibung | Aufruf |
|---|---|---|
| [`cmk_change_user_password.py`](./cmk_change_user_password.py) | Entsperrt einen Checkmk-User (falls gesperrt) und setzt ein zufälliges 20-stelliges Passwort – ohne erzwungenen Passwortwechsel beim nächsten Login. | `python3 cmk_change_user_password.py <username>` |
| [`cmk_downtime.py`](./cmk_downtime.py) | Setzt, entfernt oder listet Downtimes für einen oder mehrere Hosts – wahlweise inkl. aller Services oder nur für einzelne Services. Ideal für Patch-Jobs in Rundeck. | `python3 cmk_downtime.py <host> [<host> ...] --minutes 90` |
| [`cmk_add_host.py`](./cmk_add_host.py) | Legt einen Host im gewünschten Ordner an (IP, Alias, Tags, Labels), führt die Service-Erkennung durch und aktiviert die Änderungen. | `python3 cmk_add_host.py <host> --ip <ip> --folder /linux` |
| [`cmk_problems_report.py`](./cmk_problems_report.py) | Listet alle Hosts in DOWN/UNREACH und alle Services in WARN/CRIT/UNKNOWN – als Tabelle, CSV oder JSON. | `python3 cmk_problems_report.py --unhandled` |

> Weitere Skripte folgen – siehe [Roadmap](#-roadmap).

---

### ⚙️ Voraussetzungen

- Python **3.8+**
- Paket [`requests`](https://pypi.org/project/requests/)
- Ein Checkmk-**Automation-User** mit API-Secret und ausreichenden Berechtigungen
- Checkmk **2.3 oder neuer** für `cmk_downtime.py`, `cmk_add_host.py` und `cmk_problems_report.py`

```bash
pip install requests
```

---

### 🚀 Installation

```bash
git clone https://github.com/withakedo/checkmk_scripts.git
cd checkmk_scripts
```

---

### 🔧 Konfiguration

Die Zugangsdaten stehen im Config-Block am Kopf des jeweiligen Skripts und müssen vor dem ersten Lauf angepasst werden:

```python
HOST   = "CMK_URL"     # z. B. https://checkmk.example.com
SITE   = "SITE_NAME"
USER   = "API_USER"
SECRET = "SECRET"
```

`cmk_downtime.py`, `cmk_add_host.py` und `cmk_problems_report.py` lesen die Werte zusätzlich aus Umgebungsvariablen. Diese haben Vorrang vor dem Config-Block – praktisch für Rundeck oder Cron, weil das Secret dann nicht im Skript steht:

```bash
export CMK_HOST="https://checkmk.example.com"
export CMK_SITE="mysite"
export CMK_USER="automation"
export CMK_SECRET="..."
```

> 💡 Für produktive Setups empfiehlt es sich, `SECRET` statt hardzucoden per Umgebungsvariable oder Secret-Store (z. B. Podman/Docker Secret) einzulesen.

---

### ▶️ Verwendung

Alle Optionen eines Skripts zeigt `python3 <skript>.py --help`.

#### `cmk_change_user_password.py`

```bash
# Username als Argument
python3 cmk_change_user_password.py max.mustermann

# oder interaktiv, wenn kein Argument übergeben wird
python3 cmk_change_user_password.py
```

**Ausgabe:**

```text
Username: max.mustermann
Password: X7f!kQ2m...
```

#### `cmk_downtime.py`

```bash
# Host-Downtime für 90 Minuten ab jetzt (mehrere Hosts mit Leerzeichen oder Komma)
python3 cmk_downtime.py web01,web02 --minutes 90 --comment "Patchday"

# Host + alle Services in einem festen Zeitfenster
python3 cmk_downtime.py web01 --with-services --start "2026-10-03 22:00" --end "2026-10-04 02:00"

# Nur einzelne Services
python3 cmk_downtime.py db01 --service "MySQL Version" --service "Filesystem /var" --minutes 30

# Downtimes wieder entfernen – mit --comment nur die eigenen, andere bleiben unberührt
python3 cmk_downtime.py web01,web02 --remove --comment "Patchday"

# Aktuelle Downtimes anzeigen
python3 cmk_downtime.py web01 --list
```

Ohne `--with-services`/`--service` wirkt `--remove` nur auf Host-Downtimes. Exit-Code `1`, sobald ein Host fehlschlägt – die übrigen Hosts werden trotzdem abgearbeitet.

#### `cmk_add_host.py`

```bash
python3 cmk_add_host.py web01 --ip 10.0.0.11 --folder /linux/web --label env=prod
python3 cmk_add_host.py sw-core01 --ip 10.0.0.2 --tag agent=no-agent --tag snmp_ds=snmp-v2
```

```text
[1/3] Host 'web01' created in folder '/linux/web'
[2/3] Service discovery: 42 services monitored (2 ignored)
[3/3] Activated 1 pending change(s)
```

- Der Ordner muss bereits existieren. Ohne `--ip` löst Checkmk den Namen per DNS auf.
- Die Service-Erkennung läuft im Modus „Remove all and find new“ (`tabula_rasa`) und übernimmt alle gefundenen Services.
- Schritt 3 aktiviert **alle** ausstehenden Änderungen des API-Users – wie der Button „Activate changes“ in der GUI. Hat ein anderer User offene Änderungen, bricht das Skript ab, außer du gibst `--force-foreign-changes` an.
- Mit `--no-discovery` bzw. `--no-activate` lassen sich die Schritte 2 und 3 überspringen.

#### `cmk_problems_report.py`

```bash
# Alle Probleme als Tabelle
python3 cmk_problems_report.py

# Nur unbearbeitete, harte CRIT/UNKNOWN-Probleme auf Web-Servern
python3 cmk_problems_report.py --unhandled --hard-only --states crit,unknown --host '^web'

# Als CSV-Datei bzw. JSON für weitere Verarbeitung
python3 cmk_problems_report.py --format csv > problems.csv
python3 cmk_problems_report.py --format json --fail-on-problems
```

```text
HOST PROBLEMS (1)
STATE  HOST   SINCE  FLAGS  OUTPUT
DOWN   web03  2h 5m         CRIT - 10.0.0.3: rta nan, lost 100%

SERVICE PROBLEMS (2)
STATE  HOST   SERVICE          SINCE  FLAGS  OUTPUT
CRIT   web01  HTTPS shop       10m    ack    CRIT - HTTP 503
WARN   db01   Filesystem /var  3d 2h         WARN - 85% used

Summary: 1 DOWN, 1 CRIT, 1 WARN
```

`--unhandled` blendet quittierte Probleme, Probleme in einer Downtime und Services auf Hosts aus, die nicht UP sind. `FLAGS`: `ack` = quittiert, `dt` = in Downtime, `soft` = Soft-State. Exit-Code `2` bei API-Fehlern; mit `--fail-on-problems` Exit-Code `1`, sobald etwas gefunden wurde – z. B. um in Rundeck eine Benachrichtigung auszulösen.

---

### 🗺️ Roadmap

- [x] Downtimes setzen/entfernen (`cmk_downtime.py`)
- [x] Host anlegen inkl. Service-Erkennung und Aktivierung (`cmk_add_host.py`)
- [x] Problem-Report als Tabelle/CSV/JSON (`cmk_problems_report.py`)
- [ ] Weitere Automatisierungs-Skripte für wiederkehrende Checkmk-Admin-Aufgaben
- [ ] Secret-Handling über Umgebungsvariablen vereinheitlichen (neue Skripte ✔, `cmk_change_user_password.py` fehlt noch)
- [ ] Optionales CLI-Argument-Parsing (`argparse`) für alle Skripte (neue Skripte ✔, `cmk_change_user_password.py` fehlt noch)

---

<p align="center">⭐ Wenn dir das Repo weiterhilft, lass gern einen Star da.</p>

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:0ea5e9,100:0f172a&height=120&section=footer" width="100%"/>
