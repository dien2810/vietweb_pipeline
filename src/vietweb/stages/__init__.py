"""Processing stages 3-8. Each stage receives the DataFrame of documents still kept and returns its result.

Conventions:
- A transformation stage returns a new `text` column.
- A filter stage returns a `drop_reason` Series (None = keep, string = removal reason).
Removed documents are not deleted: the runner records the reason in `drop_reason` and `drop_stage`.
"""
from .base import StageResult  # noqa: F401
