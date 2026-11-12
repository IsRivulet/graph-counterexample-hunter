"""MathCheck backend: finite simple-undirected graph search and verification."""

__version__ = "0.2.0"

from .search import search_task
from .verify import verify_candidate
from .minimize import minimize_counterexample

__all__ = ["search_task", "verify_candidate", "minimize_counterexample"]
