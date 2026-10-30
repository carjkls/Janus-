"""Command-line interface for Janus."""

from __future__ import annotations

import argparse
import os
import sys

from . import __version__
from .mutation.hashcat_rules import generate_rule_file
from .mutation.rules import generate_wordlist
from .osint.instagram_profile import ProfileError, get_profile
from .report import build_report, print_report, save_json
from .seeds import extract_seeds


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="janus",
        description=(
            "OSINT + intelligent wordlist generator for a single Instagram "
            "profile. Authorized security testing / study only."
        ),
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-u", "--username", help="target username")
    group.add_argument("-i", "--id", help="target Instagram ID")
    parser.add_argument("-s", "--session-id", required=True, help="your Instagram session ID")
    parser.add_argument("--years", default=None, help="comma-separated years, e.g. 1998,2015")
    parser.add_argument(
        "--extra-seed", dest="extra_seed", action="append", default=None,
        help="additional seed word (repeatable)",
    )
    parser.add_argument(
        "--user-email", dest="user_email", action="append", default=None,
        help="email you already know was leaked (repeatable)",
    )
    parser.add_argument(
        "--user-wordlist", dest="user_wordlist", default=None,
        help="path to your own wordlist, reported alongside (never merged)",
    )
    parser.add_argument("-o", "--output", default="report.json", help="JSON report path")
    parser.add_argument("--wordlist-out", default="wordlist.txt", help="generated wordlist path")
    parser.add_argument("--rules-out", default="rules.rule", help="hashcat rule file path")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    search = args.username or args.id
    search_type = "username" if args.username else "id"
    try:
        profile = get_profile(search, args.session_id, search_type)
    except ProfileError as exc:
        print(f"[!] {exc}", file=sys.stderr)
        return 2

    if args.user_wordlist and os.path.abspath(args.user_wordlist) == os.path.abspath(args.wordlist_out):
        print(
            f"[!] --wordlist-out and --user-wordlist both point at {args.wordlist_out!r} — "
            "pick different paths so the generated wordlist doesn't overwrite yours",
            file=sys.stderr,
        )
        return 2

    seed_set = extract_seeds(profile, extra_seeds=args.extra_seed or [])
    years = [y.strip() for y in args.years.split(",")] if args.years else None
    wordlist = generate_wordlist(seed_set, years=years)

    with open(args.wordlist_out, "w", encoding="utf-8") as handle:
        handle.write("\n".join(wordlist) + "\n")

    with open(args.rules_out, "w", encoding="utf-8") as handle:
        handle.write(generate_rule_file())

    user_wordlist_count = 0
    if args.user_wordlist:
        with open(args.user_wordlist, encoding="utf-8") as handle:
            user_wordlist_count = sum(1 for line in handle if line.strip())

    report = build_report(
        profile=profile,
        user_emails=args.user_email or [],
        wordlist_path=args.wordlist_out,
        wordlist_count=len(wordlist),
        user_wordlist_path=args.user_wordlist,
        user_wordlist_count=user_wordlist_count,
        rules_path=args.rules_out,
    )
    print_report(report)
    save_json(report, args.output)
    print(f"[+] wordlist saved to {args.wordlist_out}")
    print(f"[+] hashcat rules saved to {args.rules_out}")
    print(f"[+] JSON report saved to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
