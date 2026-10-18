"""Check that rendering preserves chronological evidence and failed endpoints."""

import numpy as np
import pytest

from tools.replay_paper_traces import frame_indices, write_gallery


def test_replay_samples_in_order_and_keeps_timeout_endpoint() -> None:
    times = np.arange(1, 1501) * 0.02
    indices = frame_indices(times, fps=12)
    assert len(indices) == 360  # All 30 seconds, including a timed-out episode.
    assert indices[0] == 0
    assert indices[-1] == 1499
    assert np.all(np.diff(indices) >= 0)
    assert np.max(abs(times[indices[:-1]] - np.arange(359) / 12)) <= 0.020001


@pytest.mark.parametrize("times", [[], [0.02, 0.02], [0.1, 0.02], [float("nan")], [-1]])
def test_replay_rejects_unusable_timestamps(times) -> None:
    with pytest.raises(ValueError):
        frame_indices(np.asarray(times), fps=24)


def test_gallery_links_videos_and_provenance(tmp_path) -> None:
    write_gallery(tmp_path, [{"block": "q1", "episode": "open", "video": "q1/open.mp4"}], [])
    gallery = (tmp_path / "index.html").read_text()
    assert "AsimovBM episode videos" in gallery
    assert 'href="manifest.json"' in gallery
    assert 'src="q1/open.mp4"' in gallery
    assert "controls" in gallery
