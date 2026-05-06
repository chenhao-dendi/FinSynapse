"""Champion-challenger diff and gate rules.

Pure functions: compare two SuiteResult objects against GateRules.
No file I/O, no side effects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class GateRule:
    metric_path: str
    direction: str  # "higher_better"
    tolerance: float
    severity: str  # "block" | "warn"


@dataclass
class DiffRow:
    metric: str
    champion: float | None
    challenger: float | None
    delta: float | None
    direction: str
    tolerance: float
    severity: str
    passed: bool


@dataclass
class DiffReport:
    rows: list[DiffRow] = field(default_factory=list)

    @property
    def block_failures(self) -> list[DiffRow]:
        return [r for r in self.rows if not r.passed and r.severity == "block"]

    @property
    def warn_failures(self) -> list[DiffRow]:
        return [r for r in self.rows if not r.passed and r.severity == "warn"]

    @property
    def passed(self) -> bool:
        return len(self.block_failures) == 0

    @property
    def exit_code(self) -> int:
        if self.block_failures:
            return 1
        if self.warn_failures:
            return 2
        return 0

    def format_text(self) -> str:
        lines = []
        lines.append(f"{'metric':<45} {'champ':>10} {'chal':>10} {'delta':>10} {'severity':>10} {'result':>8}")
        lines.append("-" * 95)
        for r in self.rows:
            champ_s = f"{r.champion:+.4f}" if r.champion is not None else "N/A"
            chal_s = f"{r.challenger:+.4f}" if r.challenger is not None else "N/A"
            delta_s = f"{r.delta:+.4f}" if r.delta is not None else "N/A"
            result = "PASS" if r.passed else "FAIL"
            lines.append(f"{r.metric:<45} {champ_s:>10} {chal_s:>10} {delta_s:>10} {r.severity:>10} {result:>8}")
        lines.append("")
        if self.passed and not self.warn_failures:
            lines.append("GATE: PASSED — all rules satisfied.")
        elif self.passed:
            lines.append(f"GATE: PASSED (block) — {len(self.warn_failures)} warn rule(s) failed.")
        else:
            lines.append(f"GATE: FAILED — {len(self.block_failures)} block rule(s) failed.")
        return "\n".join(lines)


DEFAULT_GATES = [
    GateRule("pivot_directional_rate", "higher_better", 0.0, "block"),
    GateRule("mean_reversion_strength.3m.us", "higher_better", 0.02, "block"),
    GateRule("mean_reversion_strength.3m.cn", "higher_better", 0.02, "block"),
    GateRule("mean_reversion_strength.3m.hk", "higher_better", 0.02, "block"),
    GateRule("pivot_strict_rate", "higher_better", 0.0, "warn"),
]


def _get_nested(d: dict, path: str) -> Any:
    if path in d:
        return d[path]
    keys = path.split(".")
    val = d
    for k in keys:
        if isinstance(val, dict):
            val = val.get(k)
        else:
            return None
    return val


def diff(champion: dict, challenger: dict, rules: list[GateRule] | None = None) -> DiffReport:
    """Compare champion vs challenger SuiteResult dicts against gate rules."""
    if rules is None:
        rules = DEFAULT_GATES

    champ_metrics = champion.get("metrics", champion)
    chal_metrics = challenger.get("metrics", challenger)

    rows: list[DiffRow] = []
    for rule in rules:
        cv = _get_nested(champ_metrics, rule.metric_path)
        nv = _get_nested(chal_metrics, rule.metric_path)

        champ_val = float(cv) if cv is not None else None
        chal_val = float(nv) if nv is not None else None

        delta = chal_val - champ_val if champ_val is not None and chal_val is not None else None

        if rule.direction == "higher_better":
            passed = delta >= -rule.tolerance if delta is not None else False
        else:
            passed = delta <= rule.tolerance if delta is not None else False

        rows.append(
            DiffRow(
                metric=rule.metric_path,
                champion=champ_val,
                challenger=chal_val,
                delta=delta,
                direction=rule.direction,
                tolerance=rule.tolerance,
                severity=rule.severity,
                passed=passed,
            )
        )

    return DiffReport(rows=rows)
