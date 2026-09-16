<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=waving&color=0:0f172a,100:0ea5e9&height=200&section=header&text=checkmk_scripts&fontSize=42&fontColor=ffffff&animation=fadeIn&fontAlignY=35&desc=Python-Automatisierung%20f%C3%BCr%20die%20Checkmk%20REST%20API&descAlignY=55&descSize=16" width="100%"/>
</p>

<p align="center">
  <img src="https://readme-typing-svg.demolab.com/?font=Fira+Code&size=20&pause=1200&color=0EA5E9&center=true&vCenter=true&width=600&lines=Checkmk+REST+API+%E2%80%A2+Python;Passw%C3%B6rter+zur%C3%BCcksetzen+per+Skript;Erweiterbar+um+weitere+Tools" alt="Typing SVG" />
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

> Weitere Skripte folgen – siehe [Roadmap](#-roadmap).

---

### ⚙️ Voraussetzungen

- Python **3.8+**
- Paket [`requests`](https://pypi.org/project/requests/)
- Ein Checkmk-**Automation-User** mit API-Secret und ausreichenden Berechtigungen

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

> 💡 Für produktive Setups empfiehlt es sich, `SECRET` statt hardzucoden per Umgebungsvariable oder Secret-Store (z. B. Podman/Docker Secret) einzulesen.

---

### ▶️ Verwendung

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

---

### 🗺️ Roadmap

- [ ] Weitere Automatisierungs-Skripte für wiederkehrende Checkmk-Admin-Aufgaben
- [ ] Secret-Handling über Umgebungsvariablen vereinheitlichen
- [ ] Optionales CLI-Argument-Parsing (`argparse`) für alle Skripte

---

<p align="center">⭐ Wenn dir das Repo weiterhilft, lass gern einen Star da.</p>

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:0ea5e9,100:0f172a&height=120&section=footer" width="100%"/>
