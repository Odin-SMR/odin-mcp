# Researching Odin SMR Level 2

Literature checked 2026-11-15. This is an evidence-linked methods guide for planning and discussing research. Its recipes are recommendations synthesized for this service, not validated numerical results or automatic quality certification. The MCP knowledge tools retrieve documentation; they do not compute plots, trends or emissions.

## What kind of observation is this?

SMR is a passive microwave limb sounder. Its retrieved vertical profiles support studies of middle-atmosphere composition, chemistry and transport. Available species depend on product and frequency mode; examples include ozone, water vapour, nitrous oxide, carbon monoxide and nitric oxide. Read the selected release metadata before choosing a scientific question. [Odin L2 format guide, chapter 1](https://odin-smr.org/documents/L2_DATA.pdf)

For greenhouse-gas research, useful starting questions concern N2O transport and destruction, H2O variability, and ozone–climate interactions. CO is a useful chemical/transport tracer; it is not CO2. Do not infer a methane or carbon-dioxide product from a generic trace-gas label. OCO-style XCO2 is a dry-air, pressure-weighted column with its own observation operator; a mean of Odin profile levels is not that quantity. Surface-emission attribution additionally requires a transport/inverse model and independent constraints. [Taylor et al., 2023, comparison methodology](https://amt.copernicus.org/articles/16/3173/2023/)

## Community paradigms to bring into the conversation

- **Retrieval-aware interpretation:** an L2 value depends on radiances, prior information and vertical sensitivity. Grid spacing does not establish resolving power. [Rodgers and Connor, 2003](https://doi.org/10.1029/2002JD002299)
- **L2 to L3 is an estimator choice:** the mean of observed profiles, a monthly zonal climatology and an area-weighted atmospheric mean answer different questions. Sampling is part of the result. [Toohey and von Clarmann, 2013](https://amt.copernicus.org/articles/6/937/2013/)
- **Uncertainty has several components:** scatter, precision, uncertainty of a mean, smoothing and systematic error are different. A column called total error is not a complete uncertainty budget. [TUNER overview, 2020](https://amt.copernicus.org/articles/13/4393/2020/)
- **Compare like with like:** match observation times, locations, vertical sensitivity and chemical regimes. A multi-instrument mean is a comparison reference, not truth. [SPARC Data Initiative, 2021](https://essd.copernicus.org/articles/13/1855/2021/)
- **Separate chemistry from dynamics:** changing abundance can reflect transport, mixing or sampling as well as chemical production/loss. Tracer and vortex analyses test these alternatives. [Odin/MLS ozone-loss study, 2008](https://doi.org/10.1029/2007JD009560)
- **Reproducibility is part of the product:** retain exact input identity, screening, aggregation, auxiliary datasets, code and derived-output versions. The workflow topic gives a proposed record for this service.

## Choose a route

| Research question | Start with | Then read |
| --- | --- | --- |
| What is in one scan? | `odin-contract`, `quality-screening` | `plot-atlas` recipes 1–3 |
| Where and when do we have usable measurements? | `plot-atlas` recipes 4–5 | `workflow` |
| What is the seasonal/latitudinal structure? | `plot-atlas` recipes 6–8 | `climatology-trends` |
| Does Odin agree with MLS, ACE-FTS or a model? | `averaging-comparisons` | `plot-atlas` recipes 9–11 |
| Is there a long-term change? | `climatology-trends` | `quality-screening`, `plot-atlas` recipe 12 |
| Is an event chemical loss or dynamical redistribution? | `dynamics-events` | `plot-atlas` recipes 13–15 |

Use `list_research_topics_tool`, `get_research_topic_tool` and `search_research_guidance_tool` for cited guidance. Read `odin://research/sources` for publication dates and evidence scope. The `plan_odin_analysis` prompt helps turn a question into a reproducible plan. Access to this guide requires no AWS credentials; the existing S3 data tools have separate access requirements.
