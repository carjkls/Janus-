"""Static hashcat .rule content, equivalent in spirit to mutation/rules.py
but applied by hashcat at crack time against an un-expanded base wordlist.
Content here is fixed and never depends on any profile's data."""

from __future__ import annotations

_RULES = """\
:
l
u
c
sa4
se3
si1
so0
ss5
l sa4 se3 si1 so0 ss5
c sa4 se3 si1 so0 ss5
$1
$2
$3
$!
$@
c $1 $2 $3
l $1 $2 $3
"""


def generate_rule_file() -> str:
    return _RULES
