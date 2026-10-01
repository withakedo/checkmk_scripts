#!/usr/bin/env python3
"""Checkmk: Schedule, remove or list downtimes.

Input:   One or more host names (space or comma separated)
Action:  Sets a downtime on the hosts - optionally on all services of the
          host (--with-services) or only on selected services (--service).
          With --remove the matching downtimes are deleted instead,
          with --list they are only shown.
Output:  One line per host / downtime. Exit code 1 if any host failed.

Examples:
  cmk_downtime.py web01 web02 --minutes 90 --comment "Patchday"
  cmk_downtime.py web01,web02 --with-services --start "2026-10-03 22:00" --end "2026-10-04 02:00"
  cmk_downtime.py db01 --service "MySQL Version" --service "Filesystem /var"
  cmk_downtime.py web01 web02 --remove --comment "Patchday"
  cmk_downtime.py web01 --list
"""
import argparse
import os
import sys
from datetime import datetime, timedelta

import requests

# --- Config -------------------------------------------------------------
# Environment variables (CMK_HOST, CMK_SITE, ...) override these values.
HOST   = os.environ.get("CMK_HOST",   "CMK_URL")
SITE   = os.environ.get("CMK_SITE",   "SITE_NAME")
USER   = os.environ.get("CMK_USER",   "API_USER")
SECRET = os.environ.get("CMK_SECRET", "SECRET")

DEFAULT_MINUTES = 60
DEFAULT_COMMENT = "Maintenance"
TIMEOUT         = 30
# ------------------------------------------------------------------------


BASE = f"{HOST}/{SITE}/check_mk/api/v1"

sess = requests.Session()
sess.headers.update({
    "Authorization": f"Bearer {USER} {SECRET}",
    "Accept": "application/json",
})


def api(method, path, **kwargs):
    return sess.request(method, f"{BASE}{path}", timeout=TIMEOUT, **kwargs)


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


def parse_time(value):
    try:
        return datetime.fromisoformat(value).astimezone()
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid time '{value}', use 'YYYY-MM-DD HH:MM'") from None


def fmt_time(value):
    """Format a timestamp from the API (epoch or ISO string) as local time."""
    try:
        if isinstance(value, (int, float)):
            t = datetime.fromtimestamp(value)
        else:
            t = datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone()
        return t.strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return str(value)


def iso(t):
    return t.isoformat(timespec="seconds")


# --- Set ----------------------------------------------------------------

def set_downtime(host, start, end, comment, services, with_services):
    times = {"start_time": iso(start), "end_time": iso(end), "comment": comment}

    if services:
        r = api("post", "/domain-types/downtime/collections/service", json={
            "downtime_type": "service",
            "host_name": host,
            "service_descriptions": services,
            **times,
        })
        return None if r.status_code == 204 else error_text(r)

    r = api("post", "/domain-types/downtime/collections/host", json={
        "downtime_type": "host",
        "host_name": host,
        **times,
    })
    if r.status_code != 204:
        return error_text(r)

    if with_services:
        r = api("post", "/domain-types/downtime/collections/service", json={
            "downtime_type": "service_by_query",
            "query": {"op": "=", "left": "host_name", "right": host},
            **times,
        })
        # 422 = host has no services, the host downtime is still set
        if r.status_code not in (204, 422):
            return f"host downtime set, services failed: {error_text(r)}"
    return None


# --- List / Remove ------------------------------------------------------

def is_service(ext):
    # 2.3 returns "yes"/"no", newer versions return a boolean
    return ext.get("is_service") in (True, "yes")


def find_downtimes(host, services, with_services, comment, all_types=False):
    params = {"host_name": host}
    if services:
        params["downtime_type"] = "service"
    elif not (with_services or all_types):
        params["downtime_type"] = "host"

    r = api("get", "/domain-types/downtime/collections/all", params=params)
    if r.status_code != 200:
        return None, error_text(r)

    found = []
    for dt in r.json().get("value", []):
        ext = dt.get("extensions", {})
        if services and ext.get("service_description") not in services:
            continue
        if comment is not None and ext.get("comment") != comment:
            continue
        found.append(dt)
    return found, None


def describe(dt):
    ext = dt.get("extensions", {})
    target = ext.get("service_description", "-") if is_service(ext) else "(host)"
    return (
        f"{ext.get('host_name')} | {target} | "
        f"{fmt_time(ext.get('start_time'))} -> {fmt_time(ext.get('end_time'))} | "
        f"{ext.get('comment', '')} ({ext.get('author', '?')})"
    )


def remove_downtime(dt):
    r = api("post", "/domain-types/downtime/actions/delete/invoke", json={
        "delete_type": "by_id",
        "site_id": dt["extensions"]["site_id"],
        "downtime_id": str(dt["id"]),
    })
    return None if r.status_code == 204 else error_text(r)


# --- Main ---------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(
        description="Schedule, remove or list Checkmk downtimes.",
        epilog="Credentials are read from CMK_HOST, CMK_SITE, CMK_USER and CMK_SECRET "
               "or from the config block at the top of this script.",
    )
    p.add_argument("hosts", nargs="+", help="host names, space or comma separated")

    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--remove", action="store_true",
                      help="delete matching downtimes instead of creating one")
    mode.add_argument("--list", action="store_true", help="only show current downtimes")

    scope = p.add_mutually_exclusive_group()
    scope.add_argument("--with-services", action="store_true",
                       help="also put all services of the host into downtime")
    scope.add_argument("--service", action="append", metavar="NAME",
                       help="only this service (repeatable), no host downtime")

    p.add_argument("--start", type=parse_time, metavar="TIME",
                   help="start time 'YYYY-MM-DD HH:MM' (default: now)")
    length = p.add_mutually_exclusive_group()
    length.add_argument("--minutes", type=int, default=DEFAULT_MINUTES,
                        help=f"duration in minutes (default: {DEFAULT_MINUTES})")
    length.add_argument("--end", type=parse_time, metavar="TIME",
                        help="end time 'YYYY-MM-DD HH:MM' instead of --minutes")
    p.add_argument("--comment",
                   help=f"downtime comment (default: '{DEFAULT_COMMENT}'). "
                        "With --remove/--list only downtimes with exactly this comment match.")
    return p.parse_args()


def main():
    args = parse_args()
    hosts = [h.strip() for arg in args.hosts for h in arg.split(",") if h.strip()]
    if not hosts:
        print("No host given.", file=sys.stderr)
        sys.exit(1)
    failed = 0

    if args.list or args.remove:
        for host in hosts:
            found, err = find_downtimes(host, args.service, args.with_services,
                                        args.comment, all_types=args.list)
            if err:
                print(f"{host}: ERROR {err}", file=sys.stderr)
                failed += 1
                continue
            if not found:
                print(f"{host}: no matching downtimes")
            for dt in found:
                if args.list:
                    print(describe(dt))
                    continue
                err = remove_downtime(dt)
                if err:
                    print(f"{host}: ERROR removing downtime {dt['id']}: {err}", file=sys.stderr)
                    failed += 1
                else:
                    print(f"removed: {describe(dt)}")
        sys.exit(1 if failed else 0)

    start = args.start or datetime.now().astimezone()
    end = args.end or start + timedelta(minutes=args.minutes)
    if end <= start:
        print("End time must be after start time.", file=sys.stderr)
        sys.exit(1)
    comment = args.comment or DEFAULT_COMMENT

    if args.service:
        target = "services " + ", ".join(args.service)
    elif args.with_services:
        target = "host + all services"
    else:
        target = "host"

    for host in hosts:
        err = set_downtime(host, start, end, comment, args.service, args.with_services)
        if err:
            print(f"{host}: ERROR {err}", file=sys.stderr)
            failed += 1
        else:
            print(f"{host}: downtime set ({target}) "
                  f"{start:%Y-%m-%d %H:%M} -> {end:%Y-%m-%d %H:%M} '{comment}'")

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
