#!/usr/bin/env python3
"""Checkmk: Add a host.

Input:   Host name plus optional IP, folder, alias, tags and labels
Action:  1. Creates the host in the given folder
          2. Runs a service discovery and monitors all found services
          3. Activates the pending changes
Output:  Progress per step. Exit code 1 if a step failed.

Note: Step 3 activates ALL pending changes of the API user, not only this
      host - just like the "Activate changes" button in the GUI.

Examples:
  cmk_add_host.py web01 --ip 10.0.0.11 --folder /linux/web
  cmk_add_host.py sw-core01 --ip 10.0.0.2 --tag agent=no-agent --tag snmp_ds=snmp-v2
  cmk_add_host.py db01 --label env=prod --label team=dba --no-activate
"""
import argparse
import os
import sys
import time

import requests

# --- Config -------------------------------------------------------------
# Environment variables (CMK_HOST, CMK_SITE, ...) override these values.
HOST   = os.environ.get("CMK_HOST",   "CMK_URL")
SITE   = os.environ.get("CMK_SITE",   "SITE_NAME")
USER   = os.environ.get("CMK_USER",   "API_USER")
SECRET = os.environ.get("CMK_SECRET", "SECRET")

DEFAULT_FOLDER     = "/"
DISCOVERY_TIMEOUT  = 300   # seconds
ACTIVATION_TIMEOUT = 600   # seconds
POLL_INTERVAL      = 2     # seconds
TIMEOUT            = 30    # seconds per HTTP request
# ------------------------------------------------------------------------


BASE = f"{HOST}/{SITE}/check_mk/api/v1"

sess = requests.Session()
sess.headers.update({
    "Authorization": f"Bearer {USER} {SECRET}",
    "Accept": "application/json",
})


def api(method, path, **kwargs):
    # Redirects are handled by hand: the "wait-for-completion" endpoints
    # redirect to themselves until the background job is done.
    return sess.request(method, f"{BASE}{path}", timeout=TIMEOUT,
                        allow_redirects=False, **kwargs)


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


def die(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def wait_for(path, timeout, what):
    """Poll a wait-for-completion endpoint until it answers 204."""
    deadline = time.monotonic() + timeout
    while True:
        r = api("get", path)
        if r.status_code in (204, 404):    # done / no job running anymore
            return
        if not r.is_redirect:
            die(f"{what}: {error_text(r)}")
        if time.monotonic() > deadline:
            die(f"{what} still running after {timeout}s - check the GUI.")
        time.sleep(POLL_INTERVAL)


def key_value(text):
    if "=" not in text:
        raise argparse.ArgumentTypeError(f"'{text}' is not in KEY=VALUE format")
    key, value = text.split("=", 1)
    return key.strip(), value.strip()


# --- Steps --------------------------------------------------------------

def host_exists(name):
    r = api("get", f"/objects/host_config/{name}")
    if r.status_code == 404:
        return False
    if r.status_code != 200:
        die(error_text(r))
    return True


def create_host(name, folder, attributes):
    r = api("post", "/domain-types/host_config/collections/all", json={
        "host_name": name,
        "folder": folder,
        "attributes": attributes,
    })
    if r.status_code != 200:
        die(f"Creating host failed: {error_text(r)}")


def discover_services(name):
    # tabula_rasa = "Remove all and find new": fresh scan, then accept all
    r = api("post", "/domain-types/service_discovery_run/actions/start/invoke", json={
        "host_name": name,
        "mode": "tabula_rasa",
    })
    if r.status_code != 409 and not (r.ok or r.is_redirect):   # 409 = already running
        die(f"Service discovery failed: {error_text(r)}")

    wait_for(f"/objects/service_discovery_run/{name}/actions/wait-for-completion/invoke",
             DISCOVERY_TIMEOUT, "Service discovery")

    r = api("get", f"/objects/service_discovery/{name}")
    if r.status_code != 200:
        die(f"Reading discovery result failed: {error_text(r)}")
    phases = {}
    for svc in r.json().get("extensions", {}).get("check_table", {}).values():
        phases[svc.get("value")] = phases.get(svc.get("value"), 0) + 1
    return phases


def discovery_log(name):
    r = api("get", f"/objects/service_discovery_run/{name}")
    if r.status_code != 200:
        return []
    result = r.json().get("extensions", {}).get("logs", {}).get("result", [])
    return result if isinstance(result, list) else [str(result)]


def activate_changes(force_foreign):
    r = api("get", "/domain-types/activation_run/collections/pending_changes")
    if r.status_code != 200:
        die(f"Reading pending changes failed: {error_text(r)}")
    pending = len(r.json().get("value", []))
    if not pending:
        return 0

    r = api("post", "/domain-types/activation_run/actions/activate-changes/invoke",
            headers={"If-Match": r.headers.get("ETag", "*")},
            json={"redirect": False, "sites": [], "force_foreign_changes": force_foreign})
    if r.status_code == 422:     # nothing to activate (anymore)
        return 0
    if r.status_code == 403 and not force_foreign:
        die(f"Activation refused: {error_text(r)}\n"
            "       Other users have pending changes - use --force-foreign-changes "
            "or activate in the GUI.")
    if r.status_code != 200:
        die(f"Activation failed: {error_text(r)}")

    activation_id = r.json()["id"]
    wait_for(f"/objects/activation_run/{activation_id}/actions/wait-for-completion/invoke",
             ACTIVATION_TIMEOUT, "Activation")

    # Per-site result is only reported by newer Checkmk versions
    r = api("get", f"/objects/activation_run/{activation_id}")
    if r.status_code == 200:
        for site in r.json().get("extensions", {}).get("status_per_site", []):
            if site.get("state") not in (None, "success"):
                die(f"Activation on site {site.get('site')} failed: "
                    f"{site.get('status_text')} {site.get('status_details', '')}")
    return pending


# --- Main ---------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(
        description="Create a Checkmk host, discover its services and activate changes.",
        epilog="Credentials are read from CMK_HOST, CMK_SITE, CMK_USER and CMK_SECRET "
               "or from the config block at the top of this script.",
    )
    p.add_argument("host_name")
    p.add_argument("--ip", help="IPv4 address (default: resolved via DNS)")
    p.add_argument("--folder", default=DEFAULT_FOLDER,
                   help=f"existing folder, e.g. /linux/web (default: {DEFAULT_FOLDER})")
    p.add_argument("--alias")
    p.add_argument("--site", help="monitoring site (distributed setups)")
    p.add_argument("--tag", type=key_value, action="append", default=[], metavar="GROUP=ID",
                   help="host tag, e.g. agent=no-agent or criticality=prod (repeatable)")
    p.add_argument("--label", type=key_value, action="append", default=[], metavar="KEY=VALUE",
                   help="host label, e.g. env=prod (repeatable)")
    p.add_argument("--no-discovery", action="store_true", help="skip the service discovery")
    p.add_argument("--no-activate", action="store_true", help="do not activate changes")
    p.add_argument("--force-foreign-changes", action="store_true",
                   help="also activate pending changes of other users")
    return p.parse_args()


def main():
    args = parse_args()
    name = args.host_name.strip()
    folder = args.folder if args.folder.startswith("/") else f"/{args.folder}"

    attributes = {}
    if args.ip:
        attributes["ipaddress"] = args.ip
    if args.alias:
        attributes["alias"] = args.alias
    if args.site:
        attributes["site"] = args.site
    for group, tag_id in args.tag:
        attributes[f"tag_{group}"] = tag_id
    if args.label:
        attributes["labels"] = dict(args.label)

    if host_exists(name):
        die(f"Host '{name}' already exists.")

    create_host(name, folder, attributes)
    print(f"[1/3] Host '{name}' created in folder '{folder}'")

    if args.no_discovery:
        print("[2/3] Service discovery skipped")
    else:
        phases = discover_services(name)
        monitored = phases.pop("monitored", 0)
        rest = ", ".join(f"{n} {phase}" for phase, n in sorted(phases.items()))
        print(f"[2/3] Service discovery: {monitored} services monitored"
              + (f" ({rest})" if rest else ""))
        if not monitored:
            print("      WARNING: no services found - is the agent installed and reachable?",
                  file=sys.stderr)
            for line in discovery_log(name):
                print(f"      {line}", file=sys.stderr)

    if args.no_activate:
        print("[3/3] Activation skipped - changes are pending")
    else:
        count = activate_changes(args.force_foreign_changes)
        print(f"[3/3] Activated {count} pending change(s)" if count
              else "[3/3] Nothing to activate")


if __name__ == "__main__":
    main()
