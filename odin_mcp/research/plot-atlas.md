# Plot atlas for atmospheric profile research

The recipes below are proposed Odin workflows informed by the linked literature. All require product/version identity, documented screening, units and coverage. No example here is a computed Odin result. Read `odin-contract` before using kernels and `climatology-trends` before treating a sample mean as a climatology.

## Profiles and sampling

| # / Plot | Question and construction | Companion information / failure to avoid |
| --- | --- | --- |
| 1. Vertical profile | VMR on x; height or log-pressure on y. Overlay the prior and valid source uncertainty for one identified scan. | Mark unsupported levels; a priori agreement alone is not validation. |
| 2. Kernel and response panels | Kernel rows versus input height, coloured by retrieved level; response versus height. Requires verified matrix basis and coordinates. | Distinguish grid spacing, sensitivity and vertical resolution; do not compute unqualified degrees of freedom from an ambiguously normalized kernel. |
| 3. Orbit curtain | Time or along-track distance on x, vertical coordinate on y, concentration colour; keep scan boundaries and acquisition gaps. | Include scan geography; latitude is not monotonic over an orbit, so do not sort a curtain by latitude. |
| 4. Coverage dashboard | Map scan positions; month–latitude counts; days observed, local-time coverage if available, and valid fraction. | Count distinct scans, not vertical rows; independence is an additional assumption. Sampled area and observing frequency are separate. |
| 5. Map on a defined layer | Select a pressure/height layer or documented interpolation, then show points or occupied cells. | Show counts; leave empty cells blank. Specify per-level versus scan-reference location and map projection. |

Examples anchoring profile/kernel practice: [Grieco et al. 2021, Fig.2](https://amt.copernicus.org/articles/14/5823/2021/). Temporal/spatial validation diagnostics: [Grieco et al. 2020, CO](https://amt.copernicus.org/articles/13/5013/2020/). Coverage belongs beside the science plot because sampling changes the estimator: [Toohey et al. 2013](https://doi.org/10.1002/jgrd.50874).

## Climate structure and validation

| # / Plot | Question and construction | Companion information / failure to avoid |
| --- | --- | --- |
| 6. Latitude–height section | Bin screened profiles on a declared common vertical grid; latitude on x, height/log-pressure on y, mean or median colour. | Pair with count and spread panels; document longitude/time sampling and scan weights. |
| 7. Time–height or time–latitude Hovmöller diagram | Fix a latitude band or vertical layer; aggregate by month and display concentration or anomaly. | State calendar, baseline and bins; preserve missing periods instead of connecting them across gaps. |
| 8. Seasonal cycle | Month on x; concentration for a specified band/layer on y; separate years or a declared multi-year estimate. | Show years contributing per month, spread and coverage; compare seasons using matched sampling. |
| 9. Collocated difference profile | Odin minus reference versus height after matching and verified observation-operator treatment. Report mean/median difference and dispersion. | Also show pair counts and distance/time separations; a percent difference needs an explicit stable denominator. |
| 10. Scatter/density comparison | Matched Odin versus reference values, 1:1 line, units, altitude stratum and density/counts. | Report bias and RMSE with their definitions; correlation alone cannot establish agreement. Repeated levels from one scan are correlated. |
| 11. Difference distribution | Histogram/ECDF of collocated differences, optionally by latitude, season or response. | Separate bias from width; normalized residuals need a defensible combined covariance, including shared errors. |
| 12. Trend section/profile | Trend per decade by height/latitude, with confidence interval and spatial significance convention. | Include time series, residuals, sampling and change-point sensitivity. Do not infer causation from slope or isolated significant cells. |

The community uses zonal fields, profiles and seasonal evolution together: [SPARC Data Initiative, §§3.1–3.2](https://essd.copernicus.org/articles/13/1855/2021/). Difference methods need retrieval characterization: [Rodgers and Connor, 2003](https://doi.org/10.1029/2002JD002299). Trend examples: [LOTUS update, 2026, §3/Fig.1](https://acp.copernicus.org/articles/26/7387/2026/).

## Processes and events

| # / Plot | Question and construction | Companion information / failure to avoid |
| --- | --- | --- |
| 13. Polar / equivalent-latitude section | Map an event on a defined pressure/isentropic surface; optionally bin by potential-vorticity-based equivalent latitude. | Requires matched meteorological fields, vortex definition and hemisphere convention; geographic latitude alone is not vortex membership. |
| 14. Tracer–tracer diagram | Collocate O3 and N2O; colour by date/height or vortex membership; compare with a justified reference relationship. | Different retrieval supports, mixing and descent can mimic chemistry; ordinary correlation is not a chemical-loss estimator. |
| 15. Event composite | Anomaly versus time relative to a defined event, stratified by layer/region. Compare multiple events and control periods. | Define event selection independently, show event counts and account for shared observations; do not generalize one event to climate. |

Process examples: [Odin/MLS Arctic ozone loss, 2008](https://doi.org/10.1029/2007JD009560) and [Odin NO during the unusual 2013 winter](https://acp.copernicus.org/articles/14/8009/2014/). Event recipes require auxiliary data beyond the scalar L2 columns.

## Rendering contract proposed for this service

Use a perceptually ordered sequential map for magnitude and a diverging map centred on zero for signed differences. Avoid rainbow scales; preserve a visibly distinct missing-data colour. Use the same colour limits for panels being compared and disclose clipping. [Crameri et al., 2020](https://doi.org/10.1038/s41467-020-19160-7)

Every figure caption should name selection, units, bin edges, estimator/weights, screening source, uncertainty meaning and missingness. A log colour scale cannot display nonpositive retrievals: disclose exclusions or choose another scale. Export the underlying aggregate/count table and analysis record with any publication figure.
