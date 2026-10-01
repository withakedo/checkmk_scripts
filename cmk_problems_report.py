#!/usr/bin/env python3
"""Checkmk: Problems report.

Input:   Optional filters (states, host regex, unhandled only, hard states only)
Action:  Reads all hosts that are DOWN/UNREACHABLE and all services in
          WARN/CRIT/UNKNOWN from the monitoring core.
Output:  Table (default), CSV or JSON on stdout.
          Exit code 2 on API errors; with --fail-on-problems exit code 1
          if anything was found.

Examples:
  cmk_problems_report.py
  cmk_problems_report.py --unhandled --states crit,unknown
  cmk_problems_report.py --host '^web' --format csv > problems.csv
  cmk_problems_report.py --unhandled --hard-only --format json --fail-on-problems
"""
import argparse
import csv
import json
import os
import shutil
import sys
from datetime import datetime

import requests

# --- Config -------------------------------------------------------------
# Environment variables (CMK_HOST, CMK_SITE, ...) override these values.
HOST   = os.environ.get("CMK_HOST",   "CMK_URL")
SITE   = os.environ.get("CMK_SITE",   "SITE_NAME")
USER   = os.environ.get("CMK_USER",   "API_USER")
SECRET = os.environ.get("CMK_SECRET", "SECRET")

TIMEOUT = 60
# ------------------------------------------------------------------------


BASE = f"{HOST}/{SITE}/check_mk/api/v1"

sess = requests.Session()
sess.headers.update({
    "Authorization": f"Bearer {USER} {SECRET}",
    "Accept": "application/json",
})

SERVICE_STATES = {"warn": 1, "crit": 2, "unknown": 3}
SERVICE_NAMES  = {0: "OK", 1: "WARN", 2: "CRIT", 3: "UNKNOWN"}
HOST_NAMES     = {0: "UP", 1: "DOWN", 2: "UNREACH"}
SEVERITY       = {"DOWN": 0, "UNREACH": 1, "CRIT": 2, "UNKNOWN": 3, "WARN": 4}

FIELDS = ["type", "host", "service", "state", "since", "duration",
          "acknowledged", "downtime", "soft", "output"]


def error_text(r):
    """Turn a REST API problem response into a readable one-liner."""
    try:
        problem = r.json()
    except ValueError:
        return f"HTTP {r.status_code}: {r.text.strip()[:200]}"
    msg = f"HTTP {r.status_code}: {problem.get('title', '')}"
    if problem.get("detail"):
        msg += f" - {problem['detail']}"
    if problem.get("fields"):
        msg += f" {problem['fields']}"
    return msg


def query(table, columns, filters):
    """POST a Livestatus query to /domain-types/{host|service}/collections/all."""
    body = {"columns": columns}
    if len(filters) == 1:
        body["query"] = filters[0]
    elif filters:
        body["query"] = {"op": "and", "expr": filters}
    r = sess.post(f"{BASE}/domain-types/{table}/collections/all", json=body, timeout=TIMEOUT)
    if r.status_code != 200:
        print(f"ERROR: {error_text(r)}", file=sys.stderr)
        sys.exit(2)
    return [entry.get("extensions", {}) for entry in r.json().get("value", [])]


def eq(column, value):
    return {"op": "=", "left": column, "right": str(value)}


def to_datetime(value):
    if not value:
        return None
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value).astimezone()
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone()
    except (ValueError, OverflowError, OSError):
        return None


def human_duration(seconds):
    minutes = int(seconds // 60)
    days, rest = divmod(minutes, 1440)
    hours, minutes = divmod(rest, 60)
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def make_row(kind, entry, host, service, state):
    since = to_datetime(entry.get("last_state_change"))
    now = datetime.now().astimezone()
    in_downtime = (entry.get("scheduled_downtime_depth", 0) > 0
                   or entry.get("host_scheduled_downtime_depth", 0) > 0)
    output = (entry.get("plugin_output") or "").strip()
    return {
        "type": kind,
        "host": host,
        "service": service,
        "state": state,
        "since": since.isoformat(timespec="seconds") if since else "",
        "duration": human_duration((now - since).total_seconds()) if since else "",
        "acknowledged": bool(entry.get("acknowledged")),
        "downtime": in_downtime,
        "soft": entry.get("state_type") == 0,
        "output": output.splitlines()[0] if output else "",
    }


# --- Collect ------------------------------------------------------------

def host_problems(args):
    filters = [{"op": "!=", "left": "state", "right": "0"}, eq("has_been_checked", 1)]
    if args.host:
        filters.append({"op": "~~", "left": "name", "right": args.host})
    if args.unhandled:
        filters += [eq("acknowledged", 0), eq("scheduled_downtime_depth", 0)]
    if args.hard_only:
        filters.append(eq("state_type", 1))

    columns = ["name", "state", "state_type", "plugin_output", "last_state_change",
               "acknowledged", "scheduled_downtime_depth"]
    return [make_row("host", e, e["name"], "", HOST_NAMES.get(e["state"], str(e["state"])))
            for e in query("host", columns, filters)]


def service_problems(args, states):
    if len(states) == 1:
        state_filter = eq("state", states[0])
    else:
        state_filter = {"op": "or", "expr": [eq("state", s) for s in states]}
    filters = [state_filter, eq("has_been_checked", 1)]
    if args.host:
        filters.append({"op": "~~", "left": "host_name", "right": args.host})
    if args.unhandled:
        # Same idea as the "unhandled problems" view: services of a host
        # that is not UP are covered by the host problem.
        filters += [eq("acknowledged", 0), eq("scheduled_downtime_depth", 0),
                    eq("host_scheduled_downtime_depth", 0), eq("host_state", 0)]
    if args.hard_only:
        filters.append(eq("state_type", 1))

    columns = ["host_name", "description", "state", "state_type", "plugin_output",
               "last_state_change", "acknowledged", "scheduled_downtime_depth",
               "host_scheduled_downtime_depth"]
    return [make_row("service", e, e["host_name"], e["description"],
                     SERVICE_NAMES.get(e["state"], str(e["state"])))
            for e in query("service", columns, filters)]


# --- Output -------------------------------------------------------------

def flags(row):
    return ",".join(f for f, on in (("ack", row["acknowledged"]), ("dt", row["downtime"]),
                                    ("soft", row["soft"])) if on)


def print_table(title, rows, with_service):
    if not rows:
        return
    headers = ["STATE", "HOST"] + (["SERVICE"] if with_service else []) + ["SINCE", "FLAGS", "OUTPUT"]
    lines = [[r["state"], r["host"]] + ([r["service"]] if with_service else [])
             + [r["duration"], flags(r), r["output"]] for r in rows]

    widths = [max(len(str(x)) for x in col) for col in zip(headers, *lines)]
    used = sum(widths[:-1]) + 2 * (len(widths) - 1)
    widths[-1] = max(30, shutil.get_terminal_size((160, 20)).columns - used)

    print(f"{title} ({len(rows)})")
    for line in [headers] + lines:
        cells = [str(c).ljust(w) for c, w in zip(line[:-1], widths)]
        print("  ".join(cells + [str(line[-1])[:widths[-1]]]))
    print()


def print_summary(rows):
    counts = {}
    for r in rows:
        counts[r["state"]] = counts.get(r["state"], 0) + 1
    parts = [f"{counts[s]} {s}" for s in sorted(counts, key=lambda s: SEVERITY.get(s, 9))]
    print("Summary: " + (", ".join(parts) if parts else "no problems"))


def parse_states(text):
    states = []
    for s in text.lower().split(","):
        s = s.strip()
        if s not in SERVICE_STATES:
            raise argparse.ArgumentTypeError(f"unknown state '{s}', use warn, crit, unknown")
        states.append(SERVICE_STATES[s])
    return states


def parse_args():
    p = argparse.ArgumentParser(
        description="List current Checkmk host and service problems.",
        epilog="Credentials are read from CMK_HOST, CMK_SITE, CMK_USER and CMK_SECRET "
               "or from the config block at the top of this script.",
    )
    p.add_argument("--format", choices=["table", "csv", "json"], default="table")
    p.add_argument("--states", type=parse_states, default=[1, 2, 3], metavar="LIST",
                   help="service states to include (default: warn,crit,unknown)")
    p.add_argument("--host", metavar="REGEX", help="only hosts matching this regex (case-insensitive)")
    p.add_argument("--unhandled", action="store_true",
                   help="hide acknowledged problems, problems in downtime and "
                        "services on hosts that are not UP")
    p.add_argument("--hard-only", action="store_true", help="hide soft states")
    p.add_argument("--no-hosts", action="store_true", help="only report services")
    p.add_argument("--fail-on-problems", action="store_true",
                   help="exit with code 1 if any problem was found")
    return p.parse_args()


def main():
    args = parse_args()

    hosts = [] if args.no_hosts else host_problems(args)
    services = service_problems(args, args.states)

    def order(r):
        return (SEVERITY.get(r["state"], 9), r["host"].lower(), r["service"].lower())
    hosts.sort(key=order)
    services.sort(key=order)
    rows = hosts + services

    if args.format == "json":
        json.dump(rows, sys.stdout, indent=2)
        print()
    elif args.format == "csv":
        writer = csv.DictWriter(sys.stdout, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    else:
        print_table("HOST PROBLEMS", hosts, with_service=False)
        print_table("SERVICE PROBLEMS", services, with_service=True)
        print_summary(rows)

    sys.exit(1 if args.fail_on_problems and rows else 0)


if __name__ == "__main__":
    main()
