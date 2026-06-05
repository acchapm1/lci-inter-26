#!/usr/bin/python3
import sys
import json
import textwrap
import urllib.request
from datetime import datetime
import time


URL = "https://voyager.rc.asu.edu/api/notifications/feed?format=json&channel=Sol"


try:
    with urllib.request.urlopen(URL) as r:
        data = json.load(r)
except Exception:
    sys.exit(0)

now = time.time()

#print("System Notifications - Phx\n")

width = 80
indent = "  "
wrap_width = width - len(indent)

# ANSI colors (only if stdout is a TTY)
if sys.stdout.isatty():
    BOLD = "\033[1m"
    RESET = "\033[0m"
    COLORS = {
        "warning": "\033[33m",
        "error":   "\033[31m",
        "info":    "\033[34m",
        "success": "\033[32m",
    }
else:
    BOLD = RESET = ""
    COLORS = {}

def parse_ts(ts):
    ts = ts.split(".")[0]
    return time.mktime(datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S").timetuple())

active = []
for n in data.get("notifications", []):
    start = parse_ts(n["startDate"])
    end = parse_ts(n["endDate"])
    if start <= now <= end:
        active.append(n)

if not active:
    #print("No active notifications.")
    sys.exit(0)

for n in active[:5]:
    color = COLORS.get(n.get("level", ""), "")
    print("{}{}{}{}".format(BOLD, color, n["title"], RESET))

    msg = n.get("message", "")
    if msg:
        for line in msg.splitlines():
            if not line.strip():
                print()
                continue
            wrapped = textwrap.fill(line.strip(), width=wrap_width)
            print(textwrap.indent(wrapped, indent))
        print()


    print("-" * width)
    print()

