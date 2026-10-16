#!/usr/bin/env python3
"""
Checks every anime listed in shows.json and posts to Discord when a new
episode appears.

shows.json looks like this:
{
  "shows": [
    {"name": "Psyren", "url": "https://animeheaven.me/anime.php?mc642"},
    {"name": "Other show", "url": "https://animeheaven.me/anime.php?xxxxx",
     "webhook": "DISCORD_WEBHOOK_URL_2", "mentions": "DISCORD_MENTIONS_2"}
  ]
}

"webhook" and "mentions" are the NAMES of GitHub secrets (not the secrets
themselves). If left out, DISCORD_WEBHOOK_URL and DISCORD_MENTIONS are used.

Optional environment variables:
  EPISODE_LINK_PART  Only links containing this text count as episodes. Default: "gate.php"
  DEBUG              Set to 1 to print the episode numbers found for each show.

The last seen episode for each show is stored in state.json.
"""
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urljoin  # noqa: F401  (kept for future use)

import requests
from bs4 import BeautifulSoup

EPISODE_LINK_PART = os.environ.get("EPISODE_LINK_PART", "gate.php")
DEBUG = bool(os.environ.get("DEBUG"))
BASE = Path(__file__).parent
STATE_FILE = BASE / "state.json"
CONFIG_FILE = BASE / "shows.json"

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
        print("  Episode numbers found:", sorted(set(found)))
    return max(found) if found else None


def load_json(path, default):
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, ValueError):
        return default


def check_show(show, state):
    name = show.get("name", "Your anime")
    url = show["url"]
    webhook = os.environ.get(show.get("webhook", "DISCORD_WEBHOOK_URL"), "").strip()
    mentions = os.environ.get(show.get("mentions", "DISCORD_MENTIONS"), "").strip()

    if not webhook:
        raise RuntimeError(f"No Discord webhook found for {name}. Check the secret name in shows.json.")

    episode = latest_episode(url)
    if episode is None:
        raise RuntimeError(f"No episode links found for {name}.")

    last = state.get(url)
    if last is None:
        print(f"{name}: baseline set at episode {episode} (no message sent).")
    elif episode > last:
        content = f"{mentions} New episode out: **{name}** episode {episode}\n{url}".strip()
        r = requests.post(webhook, json={"content": content}, timeout=30)
        r.raise_for_status()
        print(f"{name}: notified for episode {episode}.")
    else:
        print(f"{name}: no new episode (latest is {episode}).")

    state[url] = max(episode, last or 0)


def main():
    config = load_json(CONFIG_FILE, {})
    shows = config.get("shows", [])
    if not shows:
        sys.exit("shows.json is missing or has no shows.")

    state = load_json(STATE_FILE, {})
    failures = []

    for show in shows:
        try:
            if DEBUG:
                print(f"Checking {show.get('name', show.get('url'))}")
            check_show(show, state)
        except Exception as e:  # one broken show must not stop the others
            print(f"ERROR for {show.get('name', show.get('url'))}: {e}")
            failures.append(show.get("name", show.get("url")))

    STATE_FILE.write_text(json.dumps(state))

    if failures:
        sys.exit(f"Problems with: {', '.join(failures)}")


if __name__ == "__main__":
    main()
