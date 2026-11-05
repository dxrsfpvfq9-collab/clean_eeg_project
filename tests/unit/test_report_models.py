"""The report's frozen model bundle: intact, de-identified, and scored without sklearn."""
import json
import os
import re
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "tools"))
import drowsiness_model  # noqa: E402
import report_models  # noqa: E402

TOP = {"format", "counts", "reference", "group_stats", "source", "coupling", "drowsiness", "sha256", "version"}


def _strings(x):
    if isinstance(x, dict):
        for k, v in x.items():
            yield k
            yield from _strings(v)
    elif isinstance(x, list):
        for v in x:
            yield from _strings(v)
    elif isinstance(x, str):
        yield x


@pytest.fixture(scope="module")
def bundle():
    return report_models.load()


def test_top_level_is_exactly_the_known_sections(bundle):
    assert set(bundle) == TOP


def test_no_paths_ids_or_free_text(bundle):
    for s in set(_strings(bundle)):
        if s == bundle["sha256"]:
            continue
        bare = s.replace("cingulate/deep", "cingulate")     # the one region name with a slash
        assert not re.search(r"[\\/:]|\.edf|\b[0-9a-f]{12}\b", bare, re.I), "unexpected string in the bundle"
        assert len(s) < 70


def test_damaged_bundle_is_refused(bundle, tmp_path):
    b = json.loads(json.dumps(bundle))
    b["drowsiness"]["cut"] += 0.01
    p = tmp_path / "b.json"
    p.write_text(json.dumps(b))
    with pytest.raises(ValueError):
        report_models.load(str(p))


def test_numpy_scorer_matches_sklearn():
    rng = np.random.default_rng(0)
    X = rng.normal(size=(200, 4))
    X[rng.random(X.shape) < 0.05] = np.nan
    y = (np.nan_to_num(X[:, 0]) + rng.normal(size=200) > 0).astype(int)
    pipe = drowsiness_model._ridge(len(y)).fit(X, y)
    m = dict(names=list("abcd"), medians=pipe[0].statistics_.tolist(), quantiles=pipe[1].quantiles_.tolist(),
             references=pipe[1].references_.tolist(), coef=pipe[2].coef_[0].tolist(),
             intercept=float(pipe[2].intercept_[0]))
    # includes values past the ends of the reference, and exactly on them
    Q = rng.normal(size=(50, 4)) * 3
    Q[0] = pipe[1].quantiles_[0]
    Q[1] = pipe[1].quantiles_[-1]
    ours = [drowsiness_model.apply_note(m, dict(zip("abcd", row))) for row in Q]
    assert np.allclose(ours, pipe.predict_proba(Q)[:, 1], atol=1e-10)
