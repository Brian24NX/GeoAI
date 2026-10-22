#!/usr/bin/env python3
"""
Scoring for models built outside the harness (T3, weeks 10-11; see
docs/T3_learned_tobler_design.md), so their numbers compare with Table I.
All scores are in log speed (y = ln km/h).

  residual_quantiles(resid)         the harness's spread: quantiles of the
                                    calibration residuals at QL
  crps_quantiles(pred, r, y)        the harness's CRPS (t3_harness.score_rows):
                                    the predictive distribution is pred + r
  crps_gaussian(mu, sigma, y)       closed form
  crps_student_t(mu, sigma, nu, y)  closed form (nu > 1)
  coverage_quantiles / coverage_student_t
                                    share of y inside a central interval
  skill(crps, crps_ref)             CRPS skill in %, as in Table I:
                                    100 * (1 - sum(crps) / sum(crps_ref))
  crps_gaussian_torch(mu, sigma, y) differentiable, usable as a loss
  nll_student_t_torch(mu, sigma, nu, y)

Run this file to check every formula against brute-force sampling:
    ../.venv/bin/python t3_scoring.py
"""
import math

import numpy as np
from scipy import stats
from scipy.special import beta as beta_fn

QL = (np.arange(100) + 0.5) / 100        # t3_harness.QL


def residual_quantiles(resid):
    return np.quantile(np.asarray(resid, float), QL)


def crps_quantiles(pred, r, y):
    """CRPS of the sample {pred + r_j} (t3_harness.score_rows, crps_log):
    mean |z - y| minus half the mean |z - z'| (sorted-sample formula)."""
    pred, y = np.asarray(pred, float), np.asarray(y, float)
    r = np.sort(np.asarray(r, float))
    m = len(r)
    half = float(r @ ((2 * np.arange(1, m + 1) - m - 1) / m ** 2))
    out = np.empty(len(y))
    for a in range(0, len(y), 20000):
        b = slice(a, a + 20000)
        out[b] = np.abs(pred[b, None] + r[None, :] - y[b, None]).mean(1) - half
    return out


def crps_gaussian(mu, sigma, y):
    z = (np.asarray(y, float) - mu) / sigma
    return sigma * (z * (2 * stats.norm.cdf(z) - 1)
                    + 2 * stats.norm.pdf(z) - 1 / math.sqrt(math.pi))


def crps_student_t(mu, sigma, nu, y):
    """Location-scale Student-t with nu > 1 degrees of freedom."""
    z = (np.asarray(y, float) - mu) / sigma
    c = (2 * np.sqrt(nu) * beta_fn(0.5, nu - 0.5)
         / ((nu - 1) * beta_fn(0.5, nu / 2) ** 2))
    return sigma * (z * (2 * stats.t.cdf(z, nu) - 1)
                    + 2 * stats.t.pdf(z, nu) * (nu + z ** 2) / (nu - 1) - c)


def coverage_quantiles(pred, r, y, level=0.9):
    lo, hi = np.quantile(r, [(1 - level) / 2, (1 + level) / 2])
    e = np.asarray(y, float) - pred
    return float(np.mean((e >= lo) & (e <= hi)))


def coverage_student_t(mu, sigma, nu, y, level=0.9):
    q = stats.t.ppf((1 + level) / 2, nu)
    return float(np.mean(np.abs(np.asarray(y, float) - mu) <= q * sigma))


def skill(crps, crps_ref):
    return 100 * (1 - np.sum(crps) / np.sum(crps_ref))


def crps_gaussian_torch(mu, sigma, y):
    import torch
    z = (y - mu) / sigma
    cdf = 0.5 * (1 + torch.erf(z / math.sqrt(2)))
    pdf = torch.exp(-0.5 * z ** 2) / math.sqrt(2 * math.pi)
    return sigma * (z * (2 * cdf - 1) + 2 * pdf - 1 / math.sqrt(math.pi))


def nll_student_t_torch(mu, sigma, nu, y):
    import torch
    return -torch.distributions.StudentT(nu, mu, sigma).log_prob(y)


def _sample_crps(x, y):
    """Brute force: E|X - y| - E|X - X'| / 2 from samples x."""
    x = np.sort(x)
    m = len(x)
    return (np.abs(x - y).mean()
            - float(x @ ((2 * np.arange(1, m + 1) - m - 1) / m ** 2)))


def selftest():
    rng = np.random.default_rng(0)
    ys = np.array([-1.5, -0.3, 0.0, 0.4, 2.5])
    mu, sigma, nu = 0.2, 0.35, 4.0
    xg = mu + sigma * rng.standard_normal(1_000_000)
    xt = mu + sigma * rng.standard_t(nu, 1_000_000)
    for y in ys:
        a, b = crps_gaussian(mu, sigma, y), _sample_crps(xg, y)
        assert abs(a - b) < 2e-3 * max(1, b), ("gaussian", y, a, b)
        a, b = crps_student_t(mu, sigma, nu, y), _sample_crps(xt, y)
        assert abs(a - b) < 3e-3 * max(1, b), ("student_t", y, a, b)
    # the harness's quantile CRPS approaches the closed form
    r = sigma * stats.norm.ppf(QL)
    a = crps_quantiles(np.full(len(ys), mu), r, ys)
    b = crps_gaussian(mu, sigma, ys)
    assert np.all(np.abs(a - b) < 0.01 * sigma), (a, b)
    # torch matches numpy
    import torch
    t = crps_gaussian_torch(torch.tensor(mu), torch.tensor(sigma),
                            torch.tensor(ys)).numpy()
    assert np.allclose(t, crps_gaussian(mu, sigma, ys), atol=1e-6)
    nll = nll_student_t_torch(torch.tensor(mu), torch.tensor(sigma),
                              torch.tensor(nu), torch.tensor(ys)).numpy()
    assert np.allclose(nll, -stats.t.logpdf(ys, nu, mu, sigma), atol=1e-5)
    # coverage and skill
    yy = mu + sigma * rng.standard_normal(200_000)
    assert abs(coverage_quantiles(mu, r, yy, 0.9) - 0.9) < 0.01
    assert abs(coverage_student_t(mu, sigma, 1e6, yy, 0.9) - 0.9) < 0.01
    assert skill([1.0, 2.0], [1.0, 2.0]) == 0
    assert abs(skill([0.9], [1.0]) - 10) < 1e-9
    print("t3_scoring: all checks passed (Gaussian and Student-t CRPS vs "
          "1M samples; harness quantile CRPS; torch; coverage; skill)")


if __name__ == "__main__":
    selftest()
