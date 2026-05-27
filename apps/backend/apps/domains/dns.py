"""Thin DNS lookup wrapper — kept in its own module so tests can patch it.

The verify flow calls `lookup_txt(record_name)` and gets back a list of
strings. In production this resolves over the network. In tests, we
monkeypatch this function to return canned values without touching DNS.
"""
from __future__ import annotations

import dns.exception
import dns.resolver


class DNSLookupError(Exception):
    """Wraps both NXDOMAIN and transient resolver failures.

    Callers should treat this as "verification cannot proceed right now"
    and return a 4xx rather than 5xx — DNS misconfiguration is the
    founder's problem, not ours.
    """


def lookup_txt(record_name: str) -> list[str]:
    """Resolve TXT records for `record_name`. Returns a list of string
    values (the contents of each TXT record, joined and decoded).
    """
    try:
        answers = dns.resolver.resolve(record_name, "TXT", lifetime=5.0)
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
        return []
    except (dns.resolver.NoNameservers, dns.exception.Timeout) as exc:
        raise DNSLookupError(f"DNS resolution failed for {record_name}: {exc}") from exc

    out: list[str] = []
    for rdata in answers:
        # TXT records are sequences of byte strings — join them
        joined = b"".join(rdata.strings).decode("utf-8", errors="replace")
        out.append(joined)
    return out
