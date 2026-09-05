import os
import numpy as np
import pandas as pd
import yfinance as yf

BENCHMARK_TICKER = 'SPY'
STRESS_THRESHOLD = -0.01   # benchmark daily return cutoff that defines a "stress" day
MIN_STRESS_OBS = 20        # minimum stress-day observations before trusting the stress matrix


def _load_tickers(tickers_file):
    if not os.path.exists(tickers_file):
        raise FileNotFoundError(f"{tickers_file} not found.")
    df_tickers = pd.read_csv(tickers_file)
    if 'Ticker' in df_tickers.columns:
        tickers = df_tickers['Ticker'].dropna().astype(str).str.strip().tolist()
    else:
        # Fallback if no header 'Ticker' exists, just take the first column
        tickers = df_tickers.iloc[:, 0].dropna().astype(str).str.strip().tolist()
    return [t for t in tickers if t]  # drop empty strings


def _load_weights(weights_file, bench_tickers):
    """Optional 'Ticker,Weight' csv for actual dollar allocation. Tickers missing
    from the file get weight 0; weights are renormalized to sum to 1 over
    bench_tickers. Returns None if the file is absent or unusable."""
    if not weights_file or not os.path.exists(weights_file):
        return None
    try:
        df_w = pd.read_csv(weights_file)
    except Exception as e:
        print(f"Warning: could not read {weights_file}: {e}. Skipping weighted effective N.")
        return None
    cols = {c.lower(): c for c in df_w.columns}
    if 'ticker' not in cols or 'weight' not in cols:
        print(f"Warning: {weights_file} needs 'Ticker' and 'Weight' columns. Skipping weighted effective N.")
        return None
    raw = dict(zip(df_w[cols['ticker']].astype(str).str.strip(), df_w[cols['weight']].astype(float)))
    weights = {t: raw.get(t, 0.0) for t in bench_tickers}
    total = sum(weights.values())
    if total <= 0:
        print(f"Warning: weights in {weights_file} sum to 0. Skipping weighted effective N.")
        return None
    return {t: w / total for t, w in weights.items()}


def _download_close_prices(tickers):
    print("Downloading 1 year of daily close prices...")
    data = yf.download(tickers, period='1y', interval='1d')
    # yf.download returns a MultiIndex-columned DataFrame for multiple tickers,
    # and a flat one for a single ticker.
    if isinstance(data.columns, pd.MultiIndex):
        close_prices = data['Close']
    else:
        close_prices = pd.DataFrame({tickers[0]: data['Close']}) if len(tickers) == 1 else data['Close']
    return close_prices


def _avg_pairwise(corr_df):
    """Mean of the off-diagonal entries of a correlation matrix."""
    arr = corr_df.values
    n = arr.shape[0]
    if n < 2:
        return float('nan')
    iu = np.triu_indices(n, k=1)
    return float(arr[iu].mean())


def _effective_n(corr_df, weights=None):
    """Diversification-equivalent independent-bet count for a set of names.

    Assumes equal per-name variance (only correlation structure and weights
    vary) and computes relative portfolio variance as w' C w, where C is the
    correlation matrix. Effective N = 1 / relative variance. With equal
    weights this reduces to the classic 1 / (1/N + (1-1/N) * avg_corr)
    formula, but using the actual pairwise correlations rather than just
    their average is slightly more precise.
    """
    names = corr_df.columns.tolist()
    n = len(names)
    if n == 0:
        return float('nan')
    if weights is None:
        w = np.full(n, 1.0 / n)
    else:
        w = np.array([weights.get(t, 0.0) for t in names], dtype=float)
        total = w.sum()
        if total <= 0:
            return float('nan')
        w = w / total
    C = corr_df.values
    relative_variance = float(w @ C @ w)
    if relative_variance <= 0:
        return float('inf')
    return 1.0 / relative_variance


def _pc1_summary(corr_df):
    """Share of total variance explained by the first principal component of
    the correlation matrix, plus which names load on it most heavily."""
    names = corr_df.columns.tolist()
    eigvals, eigvecs = np.linalg.eigh(corr_df.values)
    order = np.argsort(eigvals)[::-1]
    eigvals = eigvals[order]
    eigvecs = eigvecs[:, order]
    pc1_share = float(eigvals[0] / eigvals.sum())
    pc1_loadings = pd.Series(eigvecs[:, 0], index=names)
    # Orient so the majority of loadings are positive, purely for readability.
    if (pc1_loadings > 0).sum() < (pc1_loadings < 0).sum():
        pc1_loadings = -pc1_loadings
    top_loadings = pc1_loadings.reindex(pc1_loadings.abs().sort_values(ascending=False).index)
    return pc1_share, top_loadings


def _correlation_stderr(n_obs):
    """Rough standard error of a Pearson correlation estimate: ~1/sqrt(n)."""
    if not n_obs or n_obs <= 0:
        return float('nan')
    return 1.0 / np.sqrt(n_obs)


def generate_correlation_matrix(tickers_file='tickers.csv',
                                 output_file='correlation_matrix.csv',
                                 weights_file='weights.csv',
                                 benchmark=BENCHMARK_TICKER,
                                 stress_threshold=STRESS_THRESHOLD,
                                 summary_file='correlation_summary.txt',
                                 stress_output_file='correlation_matrix_stress.csv'):
    try:
        tickers = _load_tickers(tickers_file)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return
    except Exception as e:
        print(f"Error reading {tickers_file}: {e}")
        return

    print(f"Loaded {len(tickers)} tickers from {tickers_file}.")
    if not tickers:
        print("No tickers found to process.")
        return

    try:
        close_prices = _download_close_prices(tickers)
    except Exception as e:
        print(f"Error downloading data: {e}")
        return

    if close_prices.empty:
        print("No data was downloaded.")
        return

    # Calculate daily returns and the full correlation matrix (unchanged core behavior)
    daily_returns = close_prices.pct_change(fill_method=None).dropna(how='all')
    n_obs = len(daily_returns)

    correlation_matrix = daily_returns.corr()
    correlation_matrix.to_csv(output_file)
    print("\n--- Correlation Matrix of Daily Returns ---")
    print(correlation_matrix)
    print(f"\nSuccess! Correlation matrix saved to {output_file}")

    # --- Added analysis layer ---
    has_benchmark = benchmark in correlation_matrix.columns
    if has_benchmark:
        bench_tickers = [t for t in correlation_matrix.columns if t != benchmark]
    else:
        bench_tickers = list(correlation_matrix.columns)
    bench_corr = correlation_matrix.loc[bench_tickers, bench_tickers]

    avg_corr = _avg_pairwise(bench_corr)
    corr_se = _correlation_stderr(n_obs)

    weights = _load_weights(weights_file, bench_tickers)
    eff_n_equal = _effective_n(bench_corr)
    eff_n_weighted = _effective_n(bench_corr, weights) if weights else None

    # PCA is run on the full matrix (including the benchmark) so a broad
    # market factor shows up as a loading rather than being invisible.
    pc1_share, pc1_loadings = _pc1_summary(correlation_matrix)

    benchmark_corr = None
    if has_benchmark:
        benchmark_corr = correlation_matrix[benchmark].drop(benchmark).sort_values(ascending=False)

    # Pairwise extremes, for a quick "what stands out" read.
    n_bench = len(bench_tickers)
    pairs = pd.Series(dtype=float)
    if n_bench >= 2:
        iu = np.triu_indices(n_bench, k=1)
        pair_names = [(bench_tickers[i], bench_tickers[j]) for i, j in zip(*iu)]
        pairs = pd.Series(bench_corr.values[iu], index=pd.MultiIndex.from_tuples(pair_names))
        pairs = pairs.sort_values(ascending=False)

    # Stress-day correlation: recompute using only the days the benchmark fell hard.
    # Full-sample correlation understates how correlated names get in an actual
    # selloff, since the driver shifts from company-specific news to systematic
    # fear and liquidity -- exactly the scenario a put seller cares about.
    stress_corr = None
    stress_avg = None
    stress_eff_n = None
    stress_n_obs = 0
    if has_benchmark:
        stress_mask = daily_returns[benchmark] <= stress_threshold
        stress_n_obs = int(stress_mask.sum())
        if stress_n_obs >= MIN_STRESS_OBS:
            stress_returns = daily_returns.loc[stress_mask]
            stress_corr = stress_returns.corr()
            stress_corr.to_csv(stress_output_file)
            stress_bench_corr = stress_corr.loc[bench_tickers, bench_tickers]
            stress_avg = _avg_pairwise(stress_bench_corr)
            stress_eff_n = _effective_n(stress_bench_corr, weights)

    # --- Build the summary report ---
    lines = []
    lines.append("=== Correlation Summary ===")
    lines.append(f"Observations (trading days): {n_obs}")
    lines.append(f"Approx. standard error per correlation estimate: {corr_se:.3f} "
                 f"(treat |r| below ~{2 * corr_se:.2f} as not reliably different from zero)")
    lines.append("")
    lines.append(f"Average pairwise correlation ({n_bench} names, excl. {benchmark}): {avg_corr:.3f}")
    lines.append(f"Effective N (equal-weight): {eff_n_equal:.2f} of {n_bench} names")
    if eff_n_weighted is not None:
        lines.append(f"Effective N (weighted, from {weights_file}): {eff_n_weighted:.2f} of {n_bench} names")
    else:
        lines.append(f"Effective N (weighted): n/a -- add a '{weights_file}' with Ticker,Weight "
                      f"columns to use your actual dollar allocation instead of equal-weight")
    lines.append("")
    lines.append(f"PC1 share of total variance (incl. {benchmark}): {pc1_share:.1%}")
    lines.append("Top PC1 loadings:")
    for name, val in pc1_loadings.head(8).items():
        lines.append(f"  {name:6s} {val:+.3f}")
    lines.append("")
    if benchmark_corr is not None:
        lines.append(f"Correlation to {benchmark} (highest to lowest):")
        for name, val in benchmark_corr.items():
            lines.append(f"  {name:6s} {val:+.3f}")
        lines.append("")
    if not pairs.empty:
        lines.append("Highest pairwise correlations:")
        for (a, b), val in pairs.head(5).items():
            lines.append(f"  {a}-{b}: {val:+.3f}")
        lines.append("Lowest pairwise correlations:")
        for (a, b), val in pairs.tail(5).sort_values().items():
            lines.append(f"  {a}-{b}: {val:+.3f}")
        lines.append("")
    if has_benchmark:
        if stress_corr is not None:
            lines.append(f"Stress correlation ({benchmark} daily return <= {stress_threshold:.0%}, "
                         f"n={stress_n_obs} days):")
            lines.append(f"  Average pairwise correlation under stress: {stress_avg:.3f} "
                         f"(vs. {avg_corr:.3f} full-sample)")
            lines.append(f"  Effective N under stress: {stress_eff_n:.2f} of {n_bench} names")
            lines.append(f"  Saved to {stress_output_file}")
        else:
            lines.append(f"Stress correlation: not computed -- only {stress_n_obs} day(s) with "
                         f"{benchmark} return <= {stress_threshold:.0%} (need >= {MIN_STRESS_OBS}); "
                         f"widen the window or loosen stress_threshold.")

    summary_text = "\n".join(lines)
    print("\n" + summary_text)
    with open(summary_file, 'w') as f:
        f.write(summary_text + "\n")
    print(f"\nSummary saved to {summary_file}")


if __name__ == "__main__":
    generate_correlation_matrix()
