"""Core Engineering State loading, validation and provenance-preserving updates."""

from .state import (  # noqa: F401
    StateError, apply_proposal, build_initial_state, find_core_dir, load_state, state_sha256, validate_state,
)
