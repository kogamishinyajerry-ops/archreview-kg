from __future__ import annotations

from pathlib import Path

import pytest

from samples.make_sample import build as build_sample_pdf


@pytest.fixture(scope="session")
def sample_pdf(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("samples") / "sample_clean.pdf"
    return build_sample_pdf(out)
