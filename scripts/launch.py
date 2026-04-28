#!/usr/bin/env python3
"""Continuo launch helper -- interactive Twitter + HN Show launcher.

This is NOT a fully automated poster. Why:

  - Twitter free tier needs OAuth + app credentials to post via API
  - HN has no public posting API; automation is against ToS and gets
    posts flagged by the ranking algorithm
  - HN ranks early OP replies heavily -- you have to be at the keyboard
    in the first hour anyway

What it does instead:

  1. Pre-flight: curl continuo.cloud, verify all 7 tweets fit in 280 chars
  2. Walk through each tweet -- copies to clipboard, opens Twitter compose
  3. 30-minute countdown between Twitter and HN
  4. HN: copies title to clipboard, opens submit page; then copies body
  5. Prints first-hour engagement reminders

Run:
    python scripts/launch.py             # full sequence
    python scripts/launch.py --dry-run   # preview content + char counts
    python scripts/launch.py --only tweets   # twitter only
    python scripts/launch.py --only hn       # HN only (skip the wait)
    python scripts/launch.py --wait 60       # shorter wait for testing
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

# Tweets contain emoji (e.g. the thread emoji); CP1252 default Windows
# console can't print them. Force UTF-8 with replacement so the script
# never crashes on a printable character.
for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

REPO_ROOT = Path(__file__).resolve().parent.parent
TWITTER_DRAFT = REPO_ROOT / "spec" / "launch_drafts" / "twitter_thread.md"
HN_DRAFT = REPO_ROOT / "spec" / "launch_drafts" / "hn_show.md"

LANDING_URL = "https://continuo.cloud"
TWITTER_COMPOSE_URL = "https://twitter.com/intent/tweet"
HN_SUBMIT_URL = "https://news.ycombinator.com/submit"

WAIT_SECONDS_DEFAULT = 30 * 60
TWEET_LIMIT = 280
HN_TITLE_LIMIT = 80
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)

_URL_RE = re.compile(r"https?://\S+")


def tweet_weight(text: str) -> int:
    """Twitter's weighted character count.

    Rules (per twitter-text spec):
      - URLs: always 23 chars regardless of actual length
      - Codepoints in [0x0000-0x10FF], [0x2000-0x200D],
        [0x2010-0x201F], [0x2032-0x2037]: weight 1
      - All other codepoints (arrows, em-dashes, bullets, emoji, CJK): weight 2
    """
    n_urls = len(_URL_RE.findall(text))
    text_no_urls = _URL_RE.sub("", text)
    weight = n_urls * 23
    for ch in text_no_urls:
        cp = ord(ch)
        if (cp <= 0x10FF
                or 0x2000 <= cp <= 0x200D
                or 0x2010 <= cp <= 0x201F
                or 0x2032 <= cp <= 0x2037):
            weight += 1
        else:
            weight += 2
    return weight


def copy_to_clipboard(text: str) -> bool:
    """Pipe text to Windows clip.exe with UTF-16-LE BOM. Returns True on success."""
    try:
        payload = ("﻿" + text).encode("utf-16-le")
        result = subprocess.run(["clip.exe"], input=payload, check=False)
        return result.returncode == 0
    except Exception as e:
        print(f"  [clipboard] failed: {e} -- copy manually from above")
        return False


def parse_tweets(text: str) -> list[tuple[str, str]]:
    """Extract [(label, content), ...] from twitter_thread.md."""
    tweets = []
    parts = re.split(r"^## (Tweet \d+ / [^\n]+)\n", text, flags=re.M)
    # parts = [preamble, "Tweet 1 / Hook", body1, "Tweet 2 / ...", body2, ...]
    for i in range(1, len(parts), 2):
        label = parts[i].strip()
        body = parts[i + 1].split("\n---", 1)[0]
        lines = []
        for line in body.splitlines():
            if line.startswith("> "):
                lines.append(line[2:])
            elif line.strip() == ">":
                lines.append("")
        content = "\n".join(lines).strip()
        tweets.append((label, content))
    return tweets


def parse_hn(text: str) -> tuple[str, str]:
    """Extract (title, body) from hn_show.md. Picks the primary title."""
    title_match = re.search(
        r"## Title\s*\n+> ([^\n]+(?:\n> [^\n]+)*)",
        text,
    )
    title = ""
    if title_match:
        raw = title_match.group(1)
        title = " ".join(
            line.removeprefix("> ").strip() for line in raw.splitlines()
        ).strip()

    body_match = re.search(
        r"## Body[^\n]*\n+(.*?)(?=\n---\n+## )",
        text,
        re.S,
    )
    body = body_match.group(1).strip() if body_match else ""
    return title, body


def preflight(tweets: list[tuple[str, str]], title: str, body: str) -> bool:
    print("\n=== PRE-FLIGHT ===")
    landing_ok = False
    try:
        req = urllib.request.Request(LANDING_URL, headers={"User-Agent": BROWSER_UA})
        with urllib.request.urlopen(req, timeout=10) as r:
            landing_ok = r.status == 200
            tag = "OK" if landing_ok else "FAIL"
            print(f"[{tag}] {LANDING_URL} -> HTTP {r.status}")
    except Exception as e:
        print(f"[FAIL] {LANDING_URL} -> {e}")

    tweets_ok = True
    for label, content in tweets:
        n = tweet_weight(content)
        raw = len(content)
        tag = "OK" if n <= TWEET_LIMIT else "FAIL"
        print(f"[{tag}] {label}: {n}/{TWEET_LIMIT} weighted ({raw} raw)")
        if n > TWEET_LIMIT:
            tweets_ok = False

    title_n = len(title)
    title_tag = "OK" if title_n <= HN_TITLE_LIMIT else "FAIL"
    print(f"[{title_tag}] HN title: {title_n}/{HN_TITLE_LIMIT} chars")
    print(f"       {title!r}")
    print(f"[INFO] HN body : {len(body)} chars")
    title_ok = title_n <= HN_TITLE_LIMIT
    return landing_ok and tweets_ok and title_ok


def confirm(prompt: str) -> None:
    input(f"\n>>> {prompt} [Enter to continue] ")


def post_tweets(tweets: list[tuple[str, str]], dry_run: bool) -> None:
    print("\n=== TWITTER THREAD ===")
    print(f"You'll post {len(tweets)} tweets. For each one I'll:")
    print("  1. Print the content here so you can eyeball it")
    print("  2. Copy it to your clipboard")
    print("  3. Open Twitter compose in your default browser (first tweet only)")
    print("  4. Wait for you to paste, post, then press Enter")
    print()
    print("For tweets 2..N, REPLY to the previous tweet so the thread chains.")
    if dry_run:
        print("\n[DRY RUN -- not opening browser, not copying clipboard]")
    confirm("Ready?")

    for i, (label, content) in enumerate(tweets, 1):
        print(f"\n--- {label} ({len(content)} chars) ---")
        print(content)
        print("---")
        if not dry_run:
            ok = copy_to_clipboard(content)
            if ok:
                print("  [clipboard] copied")
            if i == 1:
                webbrowser.open(TWITTER_COMPOSE_URL)
            else:
                print("  (use the Reply box on your previous tweet)")
        confirm(f"Tweet {i} posted?")


def wait_window(seconds: int) -> None:
    print(f"\n=== WAITING {seconds // 60} MIN BEFORE HN ===")
    print("(let the Twitter thread breathe; HN ranks early posts harder)")
    print("Ctrl-C to abort the wait and skip straight to HN.\n")
    end = time.time() + seconds
    try:
        while time.time() < end:
            remaining = int(end - time.time())
            mm, ss = divmod(remaining, 60)
            print(f"\r  {mm:02d}:{ss:02d} remaining   ", end="", flush=True)
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n  (skipped)")
    print()


def post_hn(title: str, body: str, dry_run: bool) -> None:
    print("\n=== HN SHOW SUBMISSION ===")
    print(f"Title : {title}")
    print(f"URL   : {LANDING_URL}")
    print(f"Body  : {len(body)} chars (will be copied separately)")
    if dry_run:
        print("\n[DRY RUN -- not opening browser, not copying clipboard]")
        print("\n--- HN BODY ---")
        print(body)
        print("---")
        return

    print("\nStep 1: copying TITLE to clipboard, opening submit page.")
    copy_to_clipboard(title)
    webbrowser.open(HN_SUBMIT_URL)
    print(f"  Title copied. URL to paste into 'url' field: {LANDING_URL}")
    confirm("Title pasted into 'title', URL pasted into 'url'?")

    print("\nStep 2: copying BODY to clipboard for the 'text' field.")
    copy_to_clipboard(body)
    print(f"  {len(body)} chars copied.")
    confirm("Body pasted into 'text' field, ready to submit?")

    print("\nStep 3: click submit.")
    confirm("Posted? (Enter once the post is live)")


def post_engagement_reminder() -> None:
    print("\n=== POST-LAUNCH ENGAGEMENT ===")
    print("First hour matters most for HN ranking.\n")
    print("DO:")
    print("  - Pin the Twitter thread to your profile")
    print("  - Cross-link: reply to your tweet 1 with the HN URL")
    print("  - Reply to the first 3-5 substantive HN comments within an hour")
    print("  - Reply to 'have you considered X?' comments")
    print("  - Engage seriously if anyone surfaces actual prior art on")
    print("    recognition-first runtime timing -- highest-value signal")
    print()
    print("DON'T:")
    print("  - Reply to 'this looks like X but worse' drive-bys")
    print("  - Argue about the wedge -- link spec/RELATED_WORK.md instead")
    print("  - Reply to emoji-only Twitter mentions")
    print()
    print("Tracking:")
    print("  - GitHub stars / clones: github.com/getcontinuo/continuo/graphs/traffic")
    print("  - Cloudflare analytics: dash.cloudflare.com -> continuo-cloud-landing")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--wait", type=int, default=WAIT_SECONDS_DEFAULT,
        help=f"Seconds between Twitter and HN (default {WAIT_SECONDS_DEFAULT})",
    )
    parser.add_argument(
        "--skip-preflight", action="store_true",
        help="Skip the pre-flight HTTP + char-count checks",
    )
    parser.add_argument(
        "--only", choices=["tweets", "hn"],
        help="Run only one half of the launch",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview content without copying clipboard or opening browsers",
    )
    args = parser.parse_args()

    if not TWITTER_DRAFT.exists():
        print(f"FATAL: missing {TWITTER_DRAFT}")
        return 2
    if not HN_DRAFT.exists():
        print(f"FATAL: missing {HN_DRAFT}")
        return 2

    tweets = parse_tweets(TWITTER_DRAFT.read_text(encoding="utf-8"))
    title, body = parse_hn(HN_DRAFT.read_text(encoding="utf-8"))

    if not tweets:
        print("FATAL: no tweets parsed from twitter_thread.md")
        return 2
    if not title or not body:
        print("FATAL: title or body missing in hn_show.md")
        return 2

    if not args.skip_preflight:
        if not preflight(tweets, title, body):
            print("\nPre-flight failed. Fix issues or rerun with --skip-preflight.")
            return 1

    if args.only != "hn":
        post_tweets(tweets, args.dry_run)
    if args.only == "tweets":
        return 0
    if args.only != "hn":
        wait_window(args.wait)
    post_hn(title, body, args.dry_run)
    post_engagement_reminder()
    return 0


if __name__ == "__main__":
    sys.exit(main())
