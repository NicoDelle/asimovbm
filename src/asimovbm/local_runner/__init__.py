"""Local-only episode runner for Paper HRI validation."""

from .catalog import DEFAULT_EPISODE_IDS, EpisodeCatalog, LocalEpisodeSpec, load_default_catalog
from .runner import LocalRunConfig, LocalRunResult, run_local_validation
from .traces import LocalEpisodeTrace, LocalStepTrace

__all__ = [
    "DEFAULT_EPISODE_IDS",
    "EpisodeCatalog",
    "LocalEpisodeSpec",
    "LocalRunConfig",
    "LocalRunResult",
    "LocalEpisodeTrace",
    "LocalStepTrace",
    "load_default_catalog",
    "run_local_validation",
]
