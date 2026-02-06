#!/usr/bin/env python3
"""
Drive Devin to fix CodeQL alerts in batches and open PRs.
Assumes Devin API supports a `/codeql/fix` endpoint that accepts alerts metadata
and pushes branches/PRs back to the repo.
"""
from __future__ import annotations

import json
import os
import sys
import time
from typing import Any, Dict, List

import requests

GITHUB_API = os.getenv("GITHUB_API_URL", "https://api.github.com")
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "3"))
MAX_BATCHES = int(os.getenv("MAX_BATCHES", "3"))
POLL_SECONDS = int(os.getenv("DEVIN_POLL_SECONDS", "15"))
POLL_LIMIT = int(os.getenv("DEVIN_POLL_LIMIT", "80"))  # 80 * 15s ≈ 20 minutes


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        print(f"Missing required env var: {name}", file=sys.stderr)
        sys.exit(1)
    return value


def gh_headers(token: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def fetch_repo(token: str, owner: str, repo: str) -> Dict[str, Any]:
    url = f"{GITHUB_API}/repos/{owner}/{repo}"
    resp = requests.get(url, headers=gh_headers(token), timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"GitHub repo fetch failed: {resp.status_code} {resp.text}")
    return resp.json()


def fetch_open_alerts(token: str, owner: str, repo: str) -> List[Dict[str, Any]]:
    url = f"{GITHUB_API}/repos/{owner}/{repo}/code-scanning/alerts"
    params = {"state": "open", "per_page": 100}
    alerts: List[Dict[str, Any]] = []
    while True:
        resp = requests.get(url, headers=gh_headers(token), params=params, timeout=60)
        if resp.status_code != 200:
            raise RuntimeError(f"GitHub alerts fetch failed: {resp.status_code} {resp.text}")
        batch = resp.json()
        alerts.extend(batch)
        if "next" not in resp.links:
            break
        url = resp.links["next"]["url"]
        params = None  # next link already has params
    return alerts


def chunk(items: List[Any], size: int):
    for i in range(0, len(items), size):
        yield i // size, items[i : i + size]


def summarize_alert(alert: Dict[str, Any]) -> Dict[str, Any]:
    instance = alert.get("most_recent_instance", {})
    location = instance.get("location", {})
    return {
        "number": alert.get("number"),
        "rule_id": alert.get("rule", {}).get("id"),
        "severity": alert.get("rule", {}).get("severity"),
        "message": alert.get("most_recent_instance", {}).get("message", {}).get("text"),
        "html_url": alert.get("html_url"),
        "ref": instance.get("ref"),
        "commit_sha": instance.get("commit_sha"),
        "path": location.get("path"),
        "start_line": location.get("start_line"),
        "end_line": location.get("end_line"),
    }


def submit_to_devin(
    url: str,
    api_key: str,
    repo: Dict[str, Any],
    batch_index: int,
    alerts: List[Dict[str, Any]],
) -> Dict[str, Any]:
    payload = {
        "repository": {
            "full_name": repo["full_name"],
            "clone_url": repo["clone_url"],
            "default_branch": repo["default_branch"],
        },
        "batch_index": batch_index,
        "alerts": [summarize_alert(a) for a in alerts],
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    resp = requests.post(f"{url.rstrip('/')}/codeql/fix", headers=headers, json=payload, timeout=60)
    if resp.status_code not in (200, 201, 202):
        raise RuntimeError(f"Devin submission failed: {resp.status_code} {resp.text}")
    return resp.json()


def poll_devin(url: str, api_key: str, job_id: str) -> Dict[str, Any]:
    headers = {"Authorization": f"Bearer {api_key}"}
    for _ in range(POLL_LIMIT):
        resp = requests.get(f"{url.rstrip('/')}/jobs/{job_id}", headers=headers, timeout=30)
        if resp.status_code != 200:
            raise RuntimeError(f"Devin poll failed: {resp.status_code} {resp.text}")
        body = resp.json()
        status = body.get("status")
        if status in {"succeeded", "failed"}:
            return body
        time.sleep(POLL_SECONDS)
    raise RuntimeError("Devin job polling timed out")


def write_summary(lines: List[str]):
    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return
    with open(summary_path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main() -> int:
    token = require_env("GITHUB_TOKEN")
    devin_url = require_env("DEVIN_API_URL")
    devin_key = require_env("DEVIN_API_KEY")

    repo_full = require_env("GITHUB_REPOSITORY")
    owner, repo_name = repo_full.split("/", 1)

    repo = fetch_repo(token, owner, repo_name)
    alerts = fetch_open_alerts(token, owner, repo_name)
    if not alerts:
        print("No open CodeQL alerts found.")
        write_summary(["✅ No open CodeQL alerts to fix."])
        return 0

    lines = [f"Found {len(alerts)} open CodeQL alerts. Processing in batches of {BATCH_SIZE} (max {MAX_BATCHES})."]
    processed_batches = 0

    for batch_index, batch in chunk(alerts, BATCH_SIZE):
        if processed_batches >= MAX_BATCHES:
            lines.append(f"Skipping remaining alerts after reaching MAX_BATCHES={MAX_BATCHES}.")
            break
        print(f"Submitting batch {batch_index} with {len(batch)} alerts to Devin...")
        submission = submit_to_devin(devin_url, devin_key, repo, batch_index, batch)
        job_id = submission.get("job_id") or submission.get("id")
        result = submission
        if job_id:
            result = poll_devin(devin_url, devin_key, job_id)

        status = result.get("status", "unknown")
        pr_url = result.get("pr_url") or result.get("pull_request", {}).get("html_url")
        branch = result.get("branch") or result.get("pull_request", {}).get("head", {}).get("ref")

        if status != "succeeded":
            lines.append(f"❌ Batch {batch_index}: Devin reported status '{status}'.")
            print(json.dumps(result, indent=2))
            continue
        processed_batches += 1
        lines.append(f"✅ Batch {batch_index}: PR opened {pr_url or '(<missing URL>)'} on branch {branch or 'unknown'}.")

    write_summary(lines)
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
