"""Evaluation module: benchmark suite, champion-challenger gate, and metrics.

Import from sub-modules directly:
    from finsynapse.eval.suite import SuiteResult, run, write_latest
    from finsynapse.eval.champion import diff, GateRule
"""

# Deliberately empty — importing sub-modules here causes RuntimeWarning
# when suite.py or gate.py are invoked as `python -m finsynapse.eval.suite`.
