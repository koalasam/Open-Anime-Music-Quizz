import sys
import json
import time
import argparse
import os
import urllib.request
import urllib.error
from urllib.parse import urlencode


BASE_API = "https://myanimelist.net/animelist/{username}/load.json"
MAL_ANIME_BASE = "https://myanimelist.net/anime/"

# Status codes used by MAL
STATUS_MAP = {
    1: "watching",
    2: "completed",
    3: "on_hold",
    4: "dropped",
    6: "plan_to_watch",
}


def fetch_anime_list(username: str, status: int = 2, offset: int = 0) -> list:
    """
    Fetch a page of anime entries from MAL's internal JSON endpoint.
    status=2 means 'completed'. Use status=7 for all statuses.
    """
    params = urlencode({
        "status": status,
        "offset": offset,
    })
    url = f"{BASE_API.format(username=username)}?{params}"

    req = urllib.request.Request(url, headers={
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"https://myanimelist.net/animelist/{username}",
    })

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status != 200:
                raise RuntimeError(f"HTTP {resp.status}")
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 400:
            # MAL returns 400 when offset is past the end of the list
            return []
        raise


def scrape_user(username: str, all_statuses: bool = False) -> list[dict]:
    """
    Scrapes all entries from a user's animelist.
    If all_statuses=True, fetches every status (watching, completed, on-hold, dropped, PTW).
    Otherwise only fetches 'completed'.
    """
    statuses = [1, 2, 3, 4, 6] if all_statuses else [2]
    results = []
    seen_ids = set()

    for status in statuses:
        status_label = STATUS_MAP.get(status, str(status))
        offset = 0
        page = 1

        print(f"  Fetching '{status_label}' entries...", end="", flush=True)

        while True:
            entries = fetch_anime_list(username, status=status, offset=offset)

            if not entries:
                break

            for entry in entries:
                anime_id = entry.get("anime_id")
                if anime_id in seen_ids:
                    continue
                seen_ids.add(anime_id)

                results.append({
                    "title": entry.get("anime_title", ""),
                    "url": f"{MAL_ANIME_BASE}{anime_id}",
                })

            print(f" {len(entries)}", end="", flush=True)

            # MAL returns up to 300 entries per page
            if len(entries) < 300:
                break

            offset += 300
            page += 1
            time.sleep(0.5)  # be polite

        print(f" ✓ ({len(results)} total so far)")

    return results


def save_results(username: str, entries: list[dict]) -> str:
    out_dir = os.path.join(".", "data", "lists")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{username}.json")

    payload = {
        "username": username,
        "profile_url": f"https://myanimelist.net/profile/{username}",
        "animelist_url": f"https://myanimelist.net/animelist/{username}",
        "total_entries": len(entries),
        "anime": entries,
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    return out_path


def main():
    parser = argparse.ArgumentParser(
        description="Scrape a MyAnimeList user's animelist and save to JSON."
    )
    parser.add_argument("username", help="MAL username to scrape")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Fetch all statuses (watching, completed, on-hold, dropped, plan-to-watch). "
             "Default: completed only.",
    )
    args = parser.parse_args()

    username = args.username.strip()
    print(f"\n🔍 Scraping animelist for: {username}")
    print(f"   Mode: {'all statuses' if args.all else 'completed only'}\n")

    try:
        entries = scrape_user(username, all_statuses=args.all)
    except urllib.error.HTTPError as e:
        if e.code == 403:
            print(f"\n❌ Access denied (403). The user '{username}' may have a private list.")
        elif e.code == 404:
            print(f"\n❌ User '{username}' not found on MyAnimeList.")
        else:
            print(f"\n❌ HTTP error {e.code}: {e.reason}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)

    if not entries:
        print(f"\n⚠️  No entries found for '{username}'. The list may be empty or private.")
        sys.exit(0)

    out_path = save_results(username, entries)
    print(f"\n✅ Done! {len(entries)} entries saved to: {out_path}")




if __name__ == "__main__":
    main()