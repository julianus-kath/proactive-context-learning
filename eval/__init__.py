"""
Evaluation & Tracking System
Autonomous benchmark runner and immutable artifact storage for thesis validation.
"""

from eval.eval_client import EvalClient, get_eval_client

__all__ = ["EvalClient", "get_eval_client"]
