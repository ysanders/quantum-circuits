"""Compatibility with callers that explicitly requested pair reduction."""

from .model import Seq


def cancel_pairs(body: Seq) -> Seq:
    """Return the graph. Direct pair reduction is an invariant of Seq."""
    if not isinstance(body, Seq):
        raise TypeError('cancel_pairs() expects a Seq')
    return body
