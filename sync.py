"""Refresh public, saved Bio accounts without a desktop application or paid host."""

import os
import time
from urllib.parse import quote
from curl_cffi import requests

PROFILE_API = "https://bio.riftroam.com/p/api/bot/valorant"
TRACKER_API = "https://api.tracker.gg/api/v2/valorant/standard"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024


class SourceError(Exception):
    pass


def tracker_data(session, path):
    response = session.get(f"{TRACKER_API}/{path}", timeout=15)
    if response.status_code != 200:
        raise SourceError(f"Tracker HTTP {response.status_code}")
    if len(response.content) > MAX_RESPONSE_BYTES:
        raise SourceError("Tracker response too large")
    try:
        body = response.json()
    except ValueError:
        raise SourceError("Tracker returned an access challenge") from None
    codes = [error.get("code") for error in body.get("errors", [])]
    if "CollectorResultStatus::Private" in codes:
        return None, "private"
    if "CollectorResultStatus::NotFound" in codes:
        return None, "notFound"
    if codes or not isinstance(body.get("data"), dict):
        raise SourceError("Tracker source unavailable")
    return body["data"], None


def fetch_snapshot(session, account):
    riot = quote(f"{account['gameName']}#{account['tagLine']}", safe="")
    observed = int(time.time() * 1000)
    profile, reason = tracker_data(session, f"profile/riot/{riot}")
    snapshot = {"account": account, "observedAt": observed, "profile": profile, "history": None}
    if reason:
        snapshot["reason"] = reason
        return snapshot
    if profile.get("metadata", {}).get("privacy") == "private":
        return snapshot
    try:
        snapshot["history"], _ = tracker_data(session, f"matches/riot/{riot}?platform=pc")
    except SourceError:
        pass  # Preserve the available rank and the last successful history.
    return snapshot


def run():
    key = os.environ.get("PROFILE_SYNC_KEY", "")
    if len(key) < 32:
        raise SourceError("PROFILE_SYNC_KEY is missing")
    tracker = requests.Session(impersonate="chrome", headers={
        "Accept": "application/json", "Origin": "https://tracker.gg", "Referer": "https://tracker.gg/"
    })
    api = requests.Session(headers={"Authorization": f"Bearer {key}", "Accept": "application/json"})
    after = None
    success = failed = 0
    deadline = time.monotonic() + 270
    while time.monotonic() < deadline:
        response = api.get(PROFILE_API, params={"after": after} if after else {}, timeout=15)
        if response.status_code != 200:
            raise SourceError(f"Profile jobs HTTP {response.status_code}")
        jobs = response.json()
        for account in jobs["accounts"]:
            if time.monotonic() >= deadline:
                break
            try:
                snapshot = fetch_snapshot(tracker, account)
                result = api.post(PROFILE_API, json=snapshot, timeout=15)
                if result.status_code != 200:
                    raise SourceError(f"Snapshot upload HTTP {result.status_code}")
                success += 1
            except Exception as error:
                failed += 1
                # No Riot IDs, upstream private identifiers or response bodies in public logs.
                print(str(error) if isinstance(error, SourceError) else type(error).__name__)
        after = jobs.get("next")
        if not after:
            break
    tracker.close()
    api.close()
    print(f"Updated {success} account(s); {failed} failure(s)")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(run())
