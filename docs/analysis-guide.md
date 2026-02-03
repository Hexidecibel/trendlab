# TrendLab Analysis Guide

A guide to the time-series analysis techniques used in TrendLab's trend
detection engine. Each section explains **what** the technique does,
**why** it matters, the **math** behind it, and **where** to find it in
the codebase.

---

## Table of Contents

1. [Momentum (Rate of Change)](#1-momentum-rate-of-change)
2. [Acceleration (Second Derivative)](#2-acceleration-second-derivative)
3. [Moving Averages](#3-moving-averages)
4. [Direction Classification](#4-direction-classification)
5. [Seasonality Detection](#5-seasonality-detection)
6. [Anomaly Detection](#6-anomaly-detection)
7. [Structural Break Detection](#7-structural-break-detection)
8. [The Analysis Pipeline](#8-the-analysis-pipeline)

---

## 1. Momentum (Rate of Change)

**File:** `app/analysis/trend_metrics.py` — `compute_momentum()`

### What it does
Momentum measures how fast a value is changing at each time step. It
answers: "Is this growing? How quickly?"

### The math
For a series of values `v[0], v[1], ..., v[n]`, momentum at step `i` is:

```
momentum[i] = (v[i+1] - v[i]) / v[i]
```

This is **percentage change** — a value of `0.05` means a 5% increase
from one day to the next. We use percentage change rather than raw
difference so that the metric is comparable across different scales
(a jump from 100 to 110 and a jump from 10,000 to 11,000 are both 10%).

### Why it matters
Raw download counts or prices tell you "how much." Momentum tells you
"how fast." A package with 1,000 downloads growing at 5% per day is
more interesting than one with 100,000 downloads growing at 0.1%.

### Edge cases
- **Division by zero:** If `v[i] = 0`, the percentage change is
  undefined. We replace NaN/inf with 0.0 using `numpy.errstate`.
- **Single point:** Can't compute change, so momentum is 0.

---

## 2. Acceleration (Second Derivative)

**File:** `app/analysis/trend_metrics.py` — `compute_acceleration()`

### What it does
Acceleration is the "change of the change" — the second derivative.
It answers: "Is the growth speeding up or slowing down?"

### The math
```
acceleration[i] = v[i+2] - 2*v[i+1] + v[i]
```

This is equivalent to `numpy.diff(values, n=2)`. When acceleration is:
- **Positive:** The trend is speeding up (growth is accelerating)
- **Negative:** The trend is slowing down (growth is decelerating)
- **Zero:** The trend is changing at a constant rate

### Why it matters
A stock price that's rising but decelerating might be about to plateau.
A package that's losing downloads but decelerating might be stabilizing.
Acceleration gives you early warning of trend reversals.

### Intuition
Think of driving a car:
- **Position** = the value (where you are)
- **Velocity** = momentum (how fast you're moving)
- **Acceleration** = acceleration (how fast your speed is changing)

Just like you feel acceleration when your car speeds up or brakes,
acceleration in data tells you the trend is about to shift.

---

## 3. Moving Averages

**File:** `app/analysis/trend_metrics.py` — `compute_moving_average()`

### What it does
A moving average smooths out day-to-day noise by averaging each point
with its neighbors, revealing the underlying trend.

### The math
For a window size `w`, the trailing moving average at position `i` is:

```
MA[i] = (v[i-w+1] + v[i-w+2] + ... + v[i]) / w
```

We use `numpy.convolve(values, ones(w)/w, mode='valid')` which
efficiently computes this for all positions at once.

### Why trailing (end-aligned)?
TrendLab uses **trailing** moving averages: the value on January 7
(with a 7-day window) is the average of January 1-7. This is the
standard for financial analysis because:
1. It doesn't "look into the future" — each MA value only uses past data
2. It's directly actionable — you can compute it in real-time

The alternative (center-aligned) would use 3 days before AND 3 days
after, which is useful for historical analysis but not for live trends.

### Default windows: 7 and 30
- **7-day MA:** Smooths daily noise, reveals the weekly trend
- **30-day MA:** Smooths weekly noise, reveals the monthly trend

When the 7-day MA crosses above the 30-day MA, it's called a "golden
cross" — a classic bullish signal in finance.

---

## 4. Direction Classification

**File:** `app/analysis/trend_metrics.py` — `analyze_trend()`

### The rule
We classify the overall direction using average momentum:

| Condition | Direction |
|-----------|-----------|
| avg(momentum) > 0.01 | `"rising"` |
| avg(momentum) < -0.01 | `"falling"` |
| otherwise | `"stable"` |

The threshold of 0.01 (1% average daily change) filters out insignificant
fluctuations. A series bouncing between +0.5% and -0.5% daily isn't
really trending — it's noise.

---

## 5. Seasonality Detection

**File:** `app/analysis/seasonality.py`

### What it does
Detects repeating patterns in the data. Many real-world series have
cycles: weekly download patterns (more on weekdays), monthly billing
cycles, seasonal crypto trends, etc.

### The technique: FFT-based Autocorrelation

**Autocorrelation** measures how similar a signal is to a shifted version
of itself. If downloads are high every Monday, the autocorrelation at
lag 7 will be high.

Naive autocorrelation is O(n^2) — for each lag, you compare every pair
of points. We use a faster approach via the **Fast Fourier Transform**:

### The math (Wiener-Khinchin theorem)
```
1. Center the data:      x = values - mean(values)
2. FFT:                  F = FFT(x, zero-padded to 2n)
3. Power spectrum:       P = F * conj(F)
4. Inverse FFT:          acf = IFFT(P)[:n]
5. Normalize:            acf = acf / acf[0]
```

This gives us autocorrelation for all lags in O(n log n) instead of O(n^2).

### Why it works
The Fourier transform decomposes a signal into its frequency components.
Multiplying by the conjugate gives the power spectrum (how much energy
at each frequency). The inverse transform of the power spectrum IS the
autocorrelation — this is the Wiener-Khinchin theorem from signal
processing.

### Finding the dominant period
After computing the autocorrelation:
1. Skip lag 0 (always 1.0 — a signal is perfectly correlated with itself)
2. Find **local peaks** — lags where `acf[i] > acf[i-1]` AND `acf[i] > acf[i+1]`
3. The strongest local peak is the dominant period
4. If its strength exceeds 0.3, we declare seasonality detected

We use local peaks (not the global max) because smooth signals have high
autocorrelation at nearby lags too. A weekly pattern has high
autocorrelation at lag 1, 2, 3... but the **peak** at lag 7 is what
reveals the period.

### Zero-padding
We zero-pad the FFT input to `2n` to avoid **circular correlation**
artifacts. Without padding, the FFT assumes the signal repeats
infinitely, causing the tail to correlate with the head.

---

## 6. Anomaly Detection

**File:** `app/analysis/anomalies.py`

### What it does
Flags individual data points that are unusually far from the norm.
These could be real events (a viral moment, a market crash) or data
quality issues.

### Method 1: Z-Score

**How it works:**
```
z[i] = (value[i] - mean) / std_deviation
```

A z-score measures how many standard deviations a point is from the
mean. In a normal distribution:
- 68% of values are within 1 std (|z| < 1)
- 95% are within 2 std (|z| < 2)
- 99.7% are within 3 std (|z| < 3)

We flag points where `|z| > 2.5` (the default threshold), meaning
they're in the most extreme ~1.2% of values.

**Best for:** Data that's roughly normally distributed. Works well
when outliers are rare and the data has a clear center.

### Method 2: Interquartile Range (IQR)

**How it works:**
```
Q1 = 25th percentile
Q3 = 75th percentile
IQR = Q3 - Q1

Lower fence = Q1 - 1.5 * IQR
Upper fence = Q3 + 1.5 * IQR
```

Any point below the lower fence or above the upper fence is an anomaly.

**Best for:** Data that isn't normally distributed. The IQR method is
robust to existing outliers — a single extreme value won't distort the
bounds (unlike z-score, where a huge outlier inflates the std deviation,
potentially hiding other outliers).

### Why offer both?
Neither method is universally better:
- Z-score is parametric (assumes normality) and simple to interpret
- IQR is non-parametric (no distribution assumption) and more robust
- The `/api/analyze` endpoint lets you choose via `anomaly_method`

### Edge case: constant data
When all values are identical, std = 0 (z-score) or IQR = 0. We handle
both: z-score returns no anomalies, IQR falls back to flagging any value
that differs from the median.

---

## 7. Structural Break Detection

**File:** `app/analysis/structural_breaks.py`

### What it does
Detects points where the statistical properties of the series change
fundamentally — not just an outlier, but a **regime shift**. Examples:
- A product goes viral (download baseline jumps from 100/day to 10,000/day)
- A cryptocurrency enters a new trading range
- A policy change causes a permanent shift in behavior

### Method 1: CUSUM (Cumulative Sum)

**How it works:**
```
1. Compute the mean of all values
2. CUSUM[i] = sum of (values[0..i] - mean)
3. Normalize by std * sqrt(n)
4. Flag where |CUSUM| exceeds threshold
```

**Intuition:** Imagine walking along a balance beam. Each step, you
move forward by `(value - mean)`. If the series is stationary, you
meander around the center. But if there's a regime change, you start
drifting consistently in one direction — the CUSUM wanders far from
zero.

The threshold `1.0 * std * sqrt(n)` is calibrated so random noise
rarely exceeds it, but a real shift in the mean will.

**Clustering:** Multiple consecutive points may exceed the threshold.
We cluster nearby detections (within 5 indices) and report only the
peak per cluster.

### Method 2: Rolling Variance

**How it works:**
```
1. Compute variance in a sliding window (default 30 days)
2. For each pair of adjacent windows, compute variance ratio
3. Flag where ratio > threshold (default 2.0)
```

This detects **volatility shifts** — periods where the data becomes
much noisier or calmer. CUSUM detects shifts in the mean; rolling
variance detects shifts in the spread.

**Example:** A crypto that's been trading in a $100 range for months
suddenly starts swinging $1,000 per day. The mean might not change,
but the variance has exploded — rolling variance catches this.

---

## 8. The Analysis Pipeline

**File:** `app/analysis/engine.py` — `analyze()`

### How it all fits together

```
TimeSeries (raw data)
       |
       v
  +-----------+
  | analyze() |  <-- the orchestrator
  +-----------+
       |
       +---> analyze_trend()         --> TrendSignal
       |       momentum, acceleration, MAs, direction
       |
       +---> analyze_seasonality()   --> SeasonalityResult
       |       FFT autocorrelation, dominant period
       |
       +---> analyze_anomalies()     --> AnomalyReport
       |       z-score or IQR outlier detection
       |
       +---> analyze_structural_breaks() --> [StructuralBreak]
               CUSUM regime change detection
       |
       v
  TrendAnalysis (combined result)
```

### API usage

```bash
# Fetch raw data
curl "http://localhost:8000/api/series?source=pypi&query=fastapi"

# Analyze the trend
curl "http://localhost:8000/api/analyze?source=pypi&query=fastapi"

# Use IQR for anomaly detection
curl "http://localhost:8000/api/analyze?source=pypi&query=fastapi&anomaly_method=iqr"

# With date range
curl "http://localhost:8000/api/analyze?source=crypto&query=bitcoin&start=2024-01-01&end=2024-06-30"
```

### Interpreting the response

The `/api/analyze` endpoint returns a JSON object like:

```json
{
  "source": "pypi",
  "query": "fastapi",
  "series_length": 180,
  "trend": {
    "direction": "rising",
    "momentum": 0.023,
    "acceleration": 0.0004,
    "moving_averages": [...],
    "momentum_series": [...]
  },
  "seasonality": {
    "detected": true,
    "period_days": 7,
    "strength": 0.65,
    "autocorrelation": [...]
  },
  "anomalies": {
    "method": "zscore",
    "threshold": 2.5,
    "anomalies": [...],
    "total_points": 180,
    "anomaly_count": 2
  },
  "structural_breaks": []
}
```

**Reading this:** "FastAPI downloads are rising at ~2.3% per day with
slight acceleration. There's a clear weekly cycle (period=7, strength=0.65).
Two unusual spikes were detected. No fundamental regime changes."

---

## Glossary

| Term | Definition |
|------|-----------|
| **Autocorrelation** | Correlation of a signal with a time-shifted version of itself |
| **CUSUM** | Cumulative Sum — tracks cumulative deviation from the mean |
| **FFT** | Fast Fourier Transform — decomposes a signal into frequencies in O(n log n) |
| **IQR** | Interquartile Range — the range between the 25th and 75th percentiles |
| **Momentum** | Rate of change; first derivative of the series |
| **Moving Average** | Smoothed value computed as the mean of a sliding window |
| **Regime Shift** | A fundamental change in the statistical properties of a series |
| **Seasonality** | Regular, repeating patterns at fixed intervals (weekly, monthly) |
| **Structural Break** | A point where the series transitions from one regime to another |
| **Z-score** | Number of standard deviations a value is from the mean |
| **Wiener-Khinchin** | Theorem: autocorrelation = inverse FFT of the power spectrum |

---

## Further Reading

- [Time Series Analysis (Wikipedia)](https://en.wikipedia.org/wiki/Time_series)
- [Autocorrelation via FFT](https://en.wikipedia.org/wiki/Wiener%E2%80%93Khinchin_theorem)
- [CUSUM Control Charts](https://en.wikipedia.org/wiki/CUSUM)
- [Box Plot / IQR Method](https://en.wikipedia.org/wiki/Interquartile_range)
