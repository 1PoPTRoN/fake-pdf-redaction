"""Core data model for the PDF redaction auditor.

Everything a detector produces is a :class:`Finding`. The :class:`Engine`
aggregates findings into a :class:`Report`. Reporters consume the Report.
Detectors never print or format anything themselves — they return data.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import IntEnum
from typing import Optional


class Severity(IntEnum):
    """Ordered so the numeric value can drive CI exit codes and sorting.

    Higher value = worse. ``INFO`` is informational (not necessarily a leak),
    ``CRITICAL`` is a confirmed recovery of content that was meant to be gone.
    """

    INFO = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

    @property
    def label(self) -> str:
        return self.name.lower()

    @classmethod
    def from_label(cls, label: str) -> "Severity":
        return cls[label.strip().upper()]


@dataclass
class Finding:
    """A single thing the auditor noticed.

    ``vector`` identifies which detector produced it (e.g. ``covered_text``).
    ``evidence`` is the *proof* — ideally the actual recovered text, not just a
    description that a problem exists. That distinction is the whole point of an
    auditor: it shows you the leaked bytes, it does not merely assert risk.
    """

    vector: str
    severity: Severity
    description: str
    page: Optional[int] = None  # 1-based page number, when applicable
    bbox: Optional[tuple[float, float, float, float]] = None
    evidence: Optional[str] = None
    recommendation: Optional[str] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["severity"] = self.severity.label
        return d


@dataclass
class Report:
    """The full result of scanning one document."""

    path: str
    findings: list[Finding] = field(default_factory=list)
    detector_errors: dict[str, str] = field(default_factory=dict)

    def add(self, finding: Finding) -> None:
        self.findings.append(finding)

    @property
    def worst_severity(self) -> Optional[Severity]:
        if not self.findings:
            return None
        return max(f.severity for f in self.findings)

    def by_severity(self) -> list[Finding]:
        """Findings sorted worst-first, stable within a severity."""
        return sorted(
            self.findings,
            key=lambda f: (-int(f.severity), f.vector, f.page or 0),
        )

    def count(self, minimum: Severity = Severity.INFO) -> int:
        return sum(1 for f in self.findings if f.severity >= minimum)

    def to_dict(self) -> dict:
        worst = self.worst_severity
        return {
            "path": self.path,
            "worst_severity": worst.label if worst is not None else None,
            "finding_count": len(self.findings),
            "findings": [f.to_dict() for f in self.by_severity()],
            "detector_errors": self.detector_errors,
        }
