# Climatologies, anomalies and long-term change

## A climatology is more than pooling profiles

A community precedent is monthly zonal statistics on a declared pressure grid with latitude bands, seasonal cycles and inter-instrument comparison fields. [SPARC Data Initiative, §§3.1–3.2](https://essd.copernicus.org/articles/13/1855/2021/)

Proposed Odin implementation choices should follow the question: select one coherent product/version/mode; screen with applicable evidence; map each scan to supported common vertical coordinates; then aggregate in explicit spatial/time bins. Keep occupied-bin counts, distinct days and scan counts. State whether a multi-year monthly climatology gives equal weight to each year or to each observation. Choose bin widths against sensitivity and sample support, not display smoothness.

Sampling can change the estimated mean and its precision. Standard error does not account for every sampling bias. Examine spatial distribution, local time, observation days and their changes through the record. Use an orbit/day-block resampling design only when its blocks and independence assumptions fit the observed dependence; ordinary row bootstrapping is inappropriate for correlated profile levels. [Toohey and von Clarmann, 2013](https://amt.copernicus.org/articles/6/937/2013/)

## Anomalies

Define the baseline years, monthly climatology, reference coordinate and coverage rules before computing `anomaly(t) = value(t) − climatology(calendar_month(t))`. A percentage anomaly additionally needs a justified non-negligible denominator. Keep unsupported months missing. A short or uneven baseline can import sampling structure into anomalies; compare baseline choices and matched coverage. Do not remove an event merely because it is extreme.

## Trends

The 2026 LOTUS update uses generalized least squares on deseasonalized monthly ozone anomalies with QBO, ENSO, solar and aerosol proxies. Its long merged records and breakpoints are not an off-the-shelf fit for Odin, whose observations start in 2001. Use the method as a precedent, not its fitted history or significance claims. [LOTUS 2026, §3.1](https://acp.copernicus.org/articles/26/7387/2026/)

A proposed Odin trend plan must specify the scientific target, interval, coherent processing lineage, annual/seasonal treatment, physically justified proxies and trend model. Test sensitivity to start/end years, instrument epochs, missing periods and reasonable screening variants. Inspect residual autocorrelation; use a method that accounts for it, actual time gaps and parameter uncertainty. Do not treat separated available months as consecutive lags. [Bognar et al., 2022](https://acp.copernicus.org/articles/22/9553/2022/)

Report slope units (such as ppbv/decade or percent/decade), the reference for any percentage, uncertainty/confidence level, fit residuals and effective temporal information. For a latitude–height map, state how many hypotheses are tested and how multiplicity/field significance is handled. A confidence interval omitting zero is not causal attribution. A decreasing ozone series is not by itself a chemical-loss estimate.

## Stop or qualify the inference when

- Coverage, product availability or processing changes covary with the apparent trend.
- Important screening diagnostics are absent or anomalous.
- A coherent versioned record cannot be established.
- Different instruments are merged without quantifying relative drift and overlap uncertainty.
- A multi-instrument mean changes membership without tracking its effect.

These are proposed analysis gates, not automatic rejection of the observations. Descriptive plots may remain useful with explicit limits. The knowledge service does not decide whether a particular Odin trend is scientifically supportable.
