"""Hashcat-style wordlist expansion from a SeedSet."""

from __future__ import annotations

from ..seeds import SeedSet

LEET_MAP = {"a": "4", "e": "3", "i": "1", "o": "0", "s": "5"}
SEPARATORS = (".", "_", "-", "")
SUFFIXES = ("123", "!", "@") + tuple(f"{n:02d}" for n in range(100))


def _leet(word: str) -> str:
    result = word.lower()
    for letter, digit in LEET_MAP.items():
        result = result.replace(letter, digit)
    return result


def _case_variants(word: str) -> list[str]:
    variants = [word, word.lower(), word.upper(), word.capitalize()]
    seen: list[str] = []
    for v in variants:
        if v not in seen:
            seen.append(v)
    return seen


def generate_wordlist(seed_set: SeedSet, years: list[str] | None = None) -> list[str]:
    base = list(seed_set.name_parts) + list(seed_set.other)
    for i, a in enumerate(seed_set.name_parts):
        for b in seed_set.name_parts:
            if a == b:
                continue
            for sep in SEPARATORS:
                base.append(f"{a}{sep}{b}")

    candidates: set[str] = set()
    for word in base:
        for variant in _case_variants(word):
            candidates.add(variant)
            candidates.add(_leet(variant))

    result: set[str] = set(candidates)
    for candidate in candidates:
        for suffix in SUFFIXES:
            result.add(candidate + suffix)
        if years:
            for year in years:
                result.add(candidate + year)
                result.add(year + candidate)

    return sorted(result)
