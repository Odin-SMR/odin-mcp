# Averaging, comparison and observation operators

## Define the quantity being estimated

For a descriptive mean at one vertical bin, first create at most one contribution per selected scan. Averaging all vertical rows instead would give extra weight to denser grids. Specify whether the scan contribution is an interpolation, a layer average or an integral; they are different quantities. Record sample count, spread, units and the bin's actual vertical support.

For scan estimates x_i and fixed weights w_i, the weighted mean is sum(w_i x_i)/sum(w_i). Its propagated variance is w^T S w/(sum w_i)^2 when S is the relevant covariance. Under independent noise only, this reduces to sum(w_i^2 sigma_i^2)/(sum w_i)^2. Missing covariance is a limitation, not evidence of independence. Do not add sample variability and source errors twice if they describe overlapping variation. [TUNER overview](https://amt.copernicus.org/articles/13/4393/2020/)

Recommended default for an explicitly descriptive sample is equal scan weighting. Inverse-variance weighting estimates a precision-weighted quantity and can favour particular atmospheric states. An area mean instead needs spatial-cell estimates with area weights, for example spherical-cell area proportional to longitude width times (sin upper latitude − sin lower latitude). This geometry does not correct unsampled cells or biased within-cell sampling. Specify time weighting separately. These are proposed estimator choices, not a universal SPARC/Odin prescription.

## Comparison protocol

1. Select compatible quantities, versions, epochs and supported vertical intervals.
2. Define time/distance windows and whether matching is one-to-one or permits reuse. Report separation distributions and sensitivity to reasonable alternatives.
3. Match local time, illumination and dynamical regime where relevant. SZA, local time, PV and tropopause position may require external inputs.
4. Put coordinates and units on compatible grids without extrapolating unsupported layers. Interpolation alone does not equalize vertical sensitivity.
5. Apply a verified observation operator, or clearly label the comparison as lacking kernel harmonization.
6. Report absolute differences, bias, dispersion and pair counts. Define percentage denominators and avoid unstable percentages near zero; correlation alone is insufficient.

Published collocation windows are study choices. For example, the H2O and temperature comparisons in [Grieco et al. 2021, §4](https://amt.copernicus.org/articles/14/5823/2021/) use different windows. The service intentionally supplies no universal matching radius.

## Conditional kernel formula

For compatible linear state vectors, the first-order comparison is:

`x_sim = x_a + A (x_reference − x_a)`

Here the reference has already been mapped to the kernel's input grid; x_a and A must have the same documented state convention. This describes how the retrieval would respond to a reference profile. The reference's own uncertainty and sensitivity still matter. [Rodgers and Connor, 2003, §§2–4](https://doi.org/10.1029/2002JD002299)

**Do not substitute stored Odin VMR and AVK into this formula until their basis is established.** Relative or log-state kernels require the corresponding transformation/Jacobian and reference state. The local source/document conflict is described in `odin-contract`. Applying only a diagonal or the measurement response is not equivalent to the matrix operator. A square matrix alone does not establish correct dimensions or normalization.

For model validation, sample the model at the actual observation locations/times, then apply compatible sensitivity treatment. Comparing that sampled model with its full-domain mean can diagnose model-estimated sampling effects. Such effects depend on model realism and are not measured Odin biases. The SPARC sampling study's quoted numerical results must not be transplanted to SMR. [Toohey et al., 2013](https://doi.org/10.1002/jgrd.50874)

## Partial columns

A supported layer integral requires physical layer weights, gas/air conventions and bounds, rather than an arithmetic mean of profile values. Propagate covariance and derive the corresponding column sensitivity. Missing layers or missing covariance constrain the result. Label it a partial column; it is not a whole-atmosphere dry-air column. [Rodgers and Connor, §4](https://doi.org/10.1029/2002JD002299)
