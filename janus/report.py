"""Report assembly: keeps OSINT-discovered and operator-added data separate."""

from __future__ import annotations

import dataclasses
import json
import sys

from .osint.instagram_profile import Profile

RESET = "\033[0m"
HEADER = "\033[1;36m"


@dataclasses.dataclass(frozen=True)
class EmailSet:
    osint: list[str]
    user_added: list[str]


@dataclasses.dataclass(frozen=True)
class WordlistInfo:
    path: str
    count: int


@dataclasses.dataclass(frozen=True)
class Report:
    profile: Profile
    emails: EmailSet
    wordlist_generated: WordlistInfo
    wordlist_user_added: WordlistInfo | None
    rules_path: str


def build_report(
    profile: Profile,
    user_emails: list[str],
    wordlist_path: str,
    wordlist_count: int,
    user_wordlist_path: str | None,
    user_wordlist_count: int,
    rules_path: str,
) -> Report:
    emails = EmailSet(
        osint=[profile.public_email] if profile.public_email else [],
        user_added=list(user_emails),
    )
    wordlist_user_added = (
        WordlistInfo(user_wordlist_path, user_wordlist_count) if user_wordlist_path else None
    )
    return Report(
        profile=profile,
        emails=emails,
        wordlist_generated=WordlistInfo(wordlist_path, wordlist_count),
        wordlist_user_added=wordlist_user_added,
        rules_path=rules_path,
    )


def _use_color() -> bool:
    return sys.stdout.isatty()


def print_report(report: Report) -> None:
    color = _use_color()
    title = "Janus OSINT report"
    if color:
        title = f"{HEADER}{title}{RESET}"
    print()
    print("=" * 72)
    print(title + f" — {report.profile.username}")
    print("=" * 72)

    p = report.profile
    print(f"full name       : {p.full_name}")
    print(f"user id         : {p.user_id}")
    print(f"business account: {p.is_business} ({p.business_category or '-'})")
    print(f"followers       : {p.follower_count} | following : {p.following_count}")
    if p.external_url:
        print(f"external url    : {p.external_url}")
    if p.biography:
        print(f"biography       : {p.biography}")
    if p.public_phone_number:
        print(f"public phone    : {p.public_phone_number}")
    if p.obfuscated_email:
        print(f"obfuscated email: {p.obfuscated_email}")
    if p.obfuscated_phone:
        print(f"obfuscated phone: {p.obfuscated_phone}")
    if p.profile_pic_url:
        print(f"profile picture : {p.profile_pic_url}")

    print()
    print("emails (osint)      : " + (", ".join(report.emails.osint) or "-"))
    print("emails (user_added) : " + (", ".join(report.emails.user_added) or "-"))

    print()
    wg = report.wordlist_generated
    print(f"wordlist (generated)  : {wg.path} ({wg.count} words)")
    if report.wordlist_user_added:
        wu = report.wordlist_user_added
        print(f"wordlist (user_added) : {wu.path} ({wu.count} words)")
    print(f"hashcat rules          : {report.rules_path}")
    print()


def report_to_json(report: Report) -> str:
    return json.dumps(dataclasses.asdict(report), indent=2, ensure_ascii=False)


def save_json(report: Report, path: str) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(report_to_json(report))
