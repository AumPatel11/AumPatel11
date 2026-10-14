import numpy as np
import pytest

from engine.design import Design


@pytest.fixture
def make_design():
    """Build a validated Design from a few object dicts.

    Objects default to thread "t1" (black); "t2" (red) is also available.
    """

    def _make(*objects, name="Test"):
        return Design.model_validate(
            {
                "name": name,
                "hoop": {"widthMm": 150, "heightMm": 150},
                "threads": [
                    {"id": "t1", "name": "Black", "hex": "#000000"},
                    {"id": "t2", "name": "Red", "hex": "#ff0000"},
                ],
                "objects": [{"threadId": "t1", **o} for o in objects],
            }
        )

    return _make


def stitch_lengths(points) -> np.ndarray:
    """Length of every stitch between consecutive needle points."""
    return np.linalg.norm(np.diff(np.asarray(points, dtype=float), axis=0), axis=1)
