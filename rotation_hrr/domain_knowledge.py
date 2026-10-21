"""
The analyst's edits, kept apart from the log (the log itself is never changed).

  activity_equivalences  "these are the same": canonical name -> its aliases, e.g.
                         {"Release": ["Release A", "Release B"]}
  ignored_activities     "I don't care about this activity": it leaves every tree, which stays in
                         normal form, and the activities after it move up ("pretend it never
                         happened"), so →(A, X, B, C) and →(A, B, C) become the same
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DomainKnowledge:
    activity_equivalences: dict = field(default_factory=dict)
    ignored_activities: set = field(default_factory=set)
