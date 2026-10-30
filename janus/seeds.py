"""Seed-word extraction from a Profile, for the mutation engine."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlsplit

from .osint.instagram_profile import Profile

_STOPWORDS = {"the", "and", "for", "com", "de", "da", "do", "que", "para"}
_MAX_BIO_WORDS = 15   # shortcut: bounds wordlist growth for long bios
_MAX_OTHER_SEEDS = 20  # shortcut: bounds overall seed/wordlist size


@dataclass(frozen=True)
class SeedSet:
    name_parts: list[str]   # from full_name, lowercased, deduped
    other: list[str]         # username + bio tokens + url domain + business_category + extra_seeds


def _dedupe(words: list[str]) -> list[str]:
    seen: list[str] = []
    for word in words:
        if word and word not in seen:
            seen.append(word)
    return seen


def extract_seeds(profile: Profile, extra_seeds: list[str] | None = None) -> SeedSet:
    name_parts = _dedupe(
        [part.lower() for part in profile.full_name.split() if len(part) >= 2]
    )

    other: list[str] = [profile.username.lower()]

    if profile.biography:
        tokens = re.split(r"[^\w]+", profile.biography.lower())
        bio_words = [t for t in tokens if len(t) >= 3 and t not in _STOPWORDS]
        other.extend(bio_words[:_MAX_BIO_WORDS])

    if profile.external_url:
        netloc = urlsplit(profile.external_url).netloc
        if netloc.startswith("www."):
            netloc = netloc[4:]
        domain_label = netloc.split(".")[0] if netloc else ""
        if domain_label:
            other.append(domain_label.lower())

    if profile.business_category:
        other.extend(word.lower() for word in profile.business_category.split())

    if profile.public_email and "@" in profile.public_email:
        local_part = profile.public_email.split("@", 1)[0].lower()
        if local_part:
            other.append(local_part)

    if extra_seeds:
        other.extend(seed.lower() for seed in extra_seeds)

    other = _dedupe(other)[:_MAX_OTHER_SEEDS]

    return SeedSet(name_parts=name_parts, other=other)
