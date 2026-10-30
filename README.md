# Janus

OSINT + intelligent wordlist generator. Janus looks both ways: one face
gathers public data from an Instagram profile (profile-fetch logic adapted
from [toutatis](https://github.com/megadose/toutatis)), the other turns
what it finds into a mutation-based wordlist and a matching hashcat rule
file.

> **For authorized security testing / study only.** This tool queries
> Instagram's private API using your own authenticated session and
> generates password-guessing material. Only use it against accounts you
> are authorized to test.

## Attribution

The profile-fetch logic in `janus/osint/instagram_profile.py` is adapted
from [toutatis](https://github.com/megadose/toutatis) by **megadose**,
licensed under the **GNU GPLv3**. Because of that, Janus as a whole is
GPLv3 (see [LICENSE](LICENSE)) rather than MIT.

## Install

```bash
pip install -e .
```

Python 3.10+. Dependencies: `requests`, `phonenumbers`, `pycountry`.

## Usage

```bash
janus -u target_username -s YOUR_INSTAGRAM_SESSIONID \
      --years 1998,2015 \
      --extra-seed "Empresa X" \
      --user-email already-leaked@example.com \
      --user-wordlist my-list.txt \
      -o report.json --wordlist-out wordlist.txt --rules-out rules.rule
```

- `-u/--username` or `-i/--id` — target (mutually exclusive, like toutatis)
- `-s/--session-id` — your own Instagram session cookie (same way toutatis
  obtains it — log in to instagram.com, copy the `sessionid` cookie)
- `--years` — comma-separated years to mix into the wordlist (e.g. company
  founding year, birth year — anything you already know)
- `--extra-seed` — additional seed word (repeatable)
- `--user-email` — an email you already know was leaked (tagged separately
  from anything the OSINT pass finds on the profile itself)
- `--user-wordlist` — your own wordlist to report alongside (never merged
  into the generated one)
- `-o` — JSON report path (default `report.json`)
- `--wordlist-out` — generated wordlist path (default `wordlist.txt`)
- `--rules-out` — hashcat rule file path (default `rules.rule`)

## How it works

1. Fetches the target's public profile data via Instagram's API (name,
   username, bio, external URL, business category, public email if any).
2. Extracts seed words from that data, plus anything you add manually.
3. Mutates the seeds (leetspeak, case variants, separators, year/suffix
   patterns) into a wordlist (`.txt`) and generates an equivalent hashcat
   `.rule` file for use with `hashcat base_wordlist.txt -r rules.rule`.
4. Produces a report where every email and every wordlist entry is tagged
   by origin — found by the OSINT pass, or added by you — never merged
   silently.

## Known limitations (v1)

- Covers a **single Instagram profile per run** — no other OSINT sources
  yet (username enumeration across platforms, certificate transparency are
  future work).
- **No automatic breach checking.** Whether an email is "leaked" is
  entirely your own call via `--user-email` — Janus never queries a
  breach-checking service on its own.
- **No local hash cracking.** The wordlist is a deliverable; running it
  against a hash dump happens in your own separate tooling.
