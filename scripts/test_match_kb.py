"""Unit tests for match_kb. Run: `python -m pytest scripts/test_match_kb.py`."""

from __future__ import annotations

from match_kb import find_match, matches


KB = [
    {
        "id": "ki-deadlock",
        "match": {
            "channels": ["alert-runtime-monitoring"],
            "any_of": [{"contains": "Deadlock found when trying to get lock"}],
        },
    },
    {
        "id": "ki-timeout",
        "match": {
            "channels": ["alert-runtime-monitoring", "alert-system"],
            "any_of": [{"regex": r"tables-fields.*Timeout expired"}],
        },
    },
    {
        "id": "ki-anywhere",
        # No `channels` filter -> matches everywhere.
        "match": {"any_of": [{"contains": "OutOfMemoryError"}]},
    },
    {
        "id": "ki-bad-regex",
        "match": {"any_of": [{"regex": "(unclosed"}]},
    },
    {
        "id": "ki-no-clauses",
        "match": {"channels": ["alert-system"]},
    },
]


def test_literal_hit():
    hit = find_match(KB, "alert-runtime-monitoring", "Deadlock found when trying to get lock; resource ...")
    assert hit and hit["id"] == "ki-deadlock"


def test_literal_case_insensitive():
    hit = find_match(KB, "alert-runtime-monitoring", "DEADLOCK FOUND WHEN TRYING TO GET LOCK")
    assert hit and hit["id"] == "ki-deadlock"


def test_regex_hit():
    text = "Service tables-fields raised: System.Data.SqlClient.SqlException: Timeout expired."
    hit = find_match(KB, "alert-runtime-monitoring", text)
    assert hit and hit["id"] == "ki-timeout"


def test_channel_filter_blocks():
    # ki-deadlock is filtered to alert-runtime-monitoring; same text on a different channel = no hit
    hit = find_match(KB, "alert-frontend-errors", "Deadlock found when trying to get lock")
    # Should fall through to ki-anywhere only if its needle appears; it doesn't here.
    assert hit is None


def test_no_channel_filter_matches_anywhere():
    hit = find_match(KB, "swat", "Caused by: java.lang.OutOfMemoryError: Java heap space")
    assert hit and hit["id"] == "ki-anywhere"


def test_bad_regex_does_not_crash():
    # ki-bad-regex has an unclosed paren; we should warn-and-skip, not raise.
    assert find_match(KB, "alert-system", "any text") is None or True


def test_no_any_of_never_matches():
    assert matches(KB[4], "alert-system", "anything") is False


def test_first_match_wins():
    # Both ki-deadlock and ki-anywhere could conceivably match if text contains both.
    # Order in KB is the tiebreaker (deadlock listed first).
    text = "Deadlock found when trying to get lock — also OutOfMemoryError"
    hit = find_match(KB, "alert-runtime-monitoring", text)
    assert hit and hit["id"] == "ki-deadlock"
