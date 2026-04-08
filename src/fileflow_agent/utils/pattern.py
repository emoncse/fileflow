"""
File pattern matching utility.

Supports two modes:
  - Glob  (default): standard shell wildcards, e.g. ``*.csv``, ``report_?.txt``
  - Regex (prefix):  full Python regex prefixed with ``re:``,
                     e.g. ``re:^report_\\d{4}-\\d{2}-\\d{2}\\.csv$``

Usage
-----
    from fileflow_agent.utils.pattern import match_pattern

    match_pattern("report_2024-01-15.csv", "re:^report_\\d{4}-\\d{2}-\\d{2}\\.csv$")  # True
    match_pattern("data.csv",              "*.csv")                                      # True
    match_pattern("data.csv",              None)                                         # True  (no filter)
"""

import re
import fnmatch
from typing import Optional

_REGEX_PREFIX = "re:"


def match_pattern(filename: str, pattern: Optional[str]) -> bool:
    """Return True if *filename* matches *pattern*.

    Args:
        filename: The bare filename (not a full path) to test.
        pattern:  The pattern string. Use ``re:<regex>`` for full Python
                  regex matching; anything else is treated as a glob pattern.
                  ``None`` matches everything.
    """
    if not pattern:
        return True

    if pattern.startswith(_REGEX_PREFIX):
        regex = pattern[len(_REGEX_PREFIX):]
        try:
            return bool(re.fullmatch(regex, filename))
        except re.error as exc:
            raise ValueError(
                f"Invalid regex pattern '{regex}' (from '{pattern}'): {exc}"
            ) from exc

    # Default: glob / fnmatch behaviour  (e.g. *.csv, report_?.txt)
    return fnmatch.fnmatch(filename, pattern)
