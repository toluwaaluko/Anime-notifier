#!/usr/bin/env python3
"""
Posts to a Discord webhook when a new episode of an anime shows up on its page.

Setup:
  pip install requests beautifulsoup4

Environment variables:
  DISCORD_WEBHOOK_URL  (required) Discord channel -> Settings -> Integrations -> Webhooks
  SHOW_URL             (required) The show's page on animeheaven (copy it from your browser)
  SHOW_NAME            (optional) Name used in the message
  EPISODE_LINK_PART    (optional) Only links containing this text count as episodes.
                       Default: "gate.php"
  DEBUG                (optional) Set to 1 to print the episode numbers it finds.

Run it on a schedule (cron, Task Scheduler, GitHub Actions). It stores the last
seen episode in state.json next to the script.
"""
import json
import os
import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL")
SHOW_URL = os.environ.get("SHOW_URL")
SHOW_NAME = os.environ.get("SHOW_NAME", "Your anime")
# Who to tag in Discord, e.g. "<@123456789> <@&987654321>". Optional.
MENTIONS = os.environ.get("DISCORD_MENTIONS", "").strip()
# Only links whose address contains this text count as episodes.
# Similar-show links (anime.php?...) are ignored.
EPISODE_LINK_PART = os.environ.get("EPISODE_LINK_PART", "gate.php")
DEBUG = bool(os.environ.get("DEBUG"))
STATE_FILE = Path(__file__).with_name("state.json")

HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}


def latest_episode(url):
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    found = []
    for a in soup.find_all("a", href=True):
        if EPISODE_LINK_PART not in a["href"]:
            continue
        m = re.search(r"\d+", a.get_text(" ", strip=True))
        if m:
            found.append(int(m.group(0)))
    if DEBUG:
        print("Episode numbers found:", sorted(set(found)))
    if not found:
        return None, url
    return max(found), url


def load_state():
    try:
        return json.loads(STATE_FILE.read_text())
    except (FileNotFoundError, ValueError):
        return {}


def main():
    if not WEBHOOK or not SHOW_URL:
        sys.exit("Set DISCORD_WEBHOOK_URL and SHOW_URL first.")

    episode, link = latest_episode(SHOW_URL)
    if episode is None:
        sys.exit("No episode links found. Adjust EPISODE_REGEX or check that the page loads normally.")

    state = load_state()
    last = state.get(SHOW_URL)

    if last is None:
        # First run: record the current episode without notifying.
        print(f"Baseline set at episode {episode}.")
    elif episode > last:
        r = requests.post(
            WEBHOOK,
            json={"content": f"{MENTIONS} New episode out: **{SHOW_NAME}** episode {episode}\n{link}".strip()},
            timeout=30,
        )
        r.raise_for_status()
        print(f"Notified for episode {episode}.")
    else:
        print(f"No new episode (latest is {episode}).")

    state[SHOW_URL] = max(episode, last or 0)
    STATE_FILE.write_text(json.dumps(state))


if __name__ == "__main__":
    main()
