"""Specialist capability adapters.

Each adapter wraps one capability of a specialist repository behind the
:class:`aipe_workflows.engine.runner.TaskAdapter` interface and returns an
:class:`aipe_workflows.engine.envelope.ExecutionEnvelope`. Adapters locate
sibling repositories or installed packages at run time and report a *blocker*
instead of failing when the specialist capability is unavailable.
"""

from .common import find_sibling_repo, import_from_checkout  # noqa: F401
