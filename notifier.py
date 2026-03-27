"""
Simple notifier that reads camping.py output from stdin and sends
notifications when campsites are available.

Supports two notification methods:
  - stdout (default): prints a summary
  - webhook: POST to a URL (e.g. Slack, Discord, ntfy.sh, etc.)

Usage:
  python camping.py --start-date ... --end-date ... --parks 232447 | python notifier.py
  python camping.py ... | python notifier.py --webhook https://ntfy.sh/my-camping-alerts
"""

import argparse
import json
import sys
from hashlib import md5
from urllib.request import Request, urlopen

from camping import SUCCESS_EMOJI

DELAY_FILE_TEMPLATE = "next_{}.txt"


def send_webhook(url, message):
    req = Request(url, data=message.encode("utf-8"), method="POST")
    req.add_header("Content-Type", "text/plain")
    with urlopen(req) as resp:
        return resp.status


def main():
    parser = argparse.ArgumentParser(description="Campsite availability notifier")
    parser.add_argument(
        "--webhook",
        help="Webhook URL to POST notifications to (e.g. ntfy.sh, Slack, Discord)",
    )
    args = parser.parse_args()

    lines = sys.stdin.read().strip().splitlines()
    if not lines:
        print("No input received.")
        return

    first_line = lines[0]

    if "Something went wrong" in first_line:
        message = "Campsite checker is broken! Please investigate."
        if args.webhook:
            send_webhook(args.webhook, message)
        print(message)
        sys.exit(1)

    available_site_strings = []
    for line in lines:
        line = line.strip()
        if SUCCESS_EMOJI in line:
            available_site_strings.append(line)

    if available_site_strings:
        message = first_line + "\n" + "\n".join(available_site_strings)
        if args.webhook:
            send_webhook(args.webhook, message)
        print("Campsites available!")
        print(message)
    else:
        print("No campsites available, not notifying.")


if __name__ == "__main__":
    main()
