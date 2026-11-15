# Screening and uncertainty before interpreting a plot

## A proposed screening record

For each product/version/mode and epoch, record: the source of every rule; valid vertical domain; required finite values; fill/null handling; retrieval-level convergence/residual checks; level-specific sensitivity criteria; and counts rejected by each condition. Keep raw values and exclusion reasons. Examine how exclusions vary with latitude, altitude, season and processing date.

Do not manufacture a universal `quality == 0`, `response > 0.8`, or positive-VMR rule. The inspected QSMR code assigns `Quality = NaN`; null quality is unknown quality. A UI marker threshold is not a science acceptance rule. Retain finite negative retrievals unless the product documentation supplies a justified screening rule; dropping them solely by sign can bias a mean upward. Invalid uncertainties cannot become zero-width error bars.

The sign-censoring issue is also explained by [NASA's MLS guidance](https://mls.jpl.nasa.gov/eos-aura-mls/data.php). Its lesson about noisy estimates is relevant; MLS quality flags and thresholds are not Odin rules.

## Published rules have bounded scope

| Evidence | What it establishes | What it does not establish |
| --- | --- | --- |
| [Grieco et al. 2021, §2.1/Fig.2](https://amt.copernicus.org/articles/14/5823/2021/) | That FM13/FM19 H2O/temperature study discards response below 0.75 | A universal threshold for all SMR modes/releases |
| [L2_DATA v1.1, §2.3.5, printed p.6](https://odin-smr.org/documents/L2_DATA.pdf) | Historical monthly-netCDF filtering uses MinLmFactor <2 for FM1/2, <10 for FM8/13/19, residual <1.5 K | That raw Parquet has already been screened, or the same rules apply elsewhere |
| [PVER v1.3.0, printed pp.7,13,15–16](https://odin-smr.org/documents/PVER.pdf) | FM1 ozone warning for 2010–2017; broader FM1 warning for 2012–2017 with a late-2017 fix; FM2 ozone useful range 17–77 km | That product-name altitude limits are validated, or every date in late 2017 is safe |

These numbers are documentary examples, not default filters implemented by this service. Retrieve the matching product guidance before execution. If required diagnostics or provenance are missing, label output as an unscreened exploratory sample and identify which inference remains unsupported.

## What error bars mean

Label whether a band is source retrieval precision, sample standard deviation, standard error, or a confidence interval. State confidence level and assumptions. Systematic/common errors do not generally shrink as 1/sqrt(N); correlated levels and scans are not independent replicates. [TUNER, §§3–6](https://amt.copernicus.org/articles/13/4393/2020/)

In the inspected QSMR revision, `error_noise` derives from measurement noise; `error_total` includes cross-state contributions but excludes internal smoothing. It does not certify all calibration/spectroscopy biases. Response is a kernel-row sum, not a probability or uncertainty. Check its definition before interpretation and investigate extreme values; do not clip diagnostics into a plausible range. See `odin-contract` for code provenance.

## First diagnostics

Successful data access and plausible-looking concentration plots are insufficient quality evidence. Check actual files for missing quality flags and anomalous response values before interpreting an aggregate; do not assume that a raw Parquet product has already passed scientific screening.

Suggested first diagnostics: response versus height, error distributions, valid fraction versus month/latitude, duplicates per scan/level, missing levels, and rejection counts by reason. If unresolved anomalies affect a scientific conclusion, report the limitation and compare documented screening alternatives without silently changing the baseline.
