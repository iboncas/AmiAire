# Iteration 2 Plan: Enrich Clustering With Color, Spatial Context, and Temporal Signals

## Goal

Run a second clustering iteration that expands the current feature space beyond morphology and grayscale intensity by adding:

1. color-related variables
2. spatial variables based on nearby places from Google Places
3. temporal and seasonal variables

The objective is not to replace the current morphology-driven baseline, but to test whether a richer context-aware representation produces:

- more interpretable clusters
- stronger cluster-context associations
- stable solutions that still satisfy the current robustness thresholds

## Current Baseline

The present clustering pipeline uses `iteration1/output/dataset/image_features_final.csv` and currently emphasizes:

- particle morphology
- grayscale intensity
- orientation structure
- PCA and direct selected-feature clustering

Important current observations:

- The final reduced dataset does not yet include explicit color descriptors.
- The current context analysis already derives `capture_year`, `capture_month`, `capture_dayofyear`, `capture_weekday`, and `capture_season`, but these are used mainly for post-hoc interpretation, not as clustering inputs.
- For iteration 2, the temporal scope should stay narrow: `capture_month` and `capture_season` are the most useful candidates, while `capture_year` is not very informative because the data only span 2025 and 2026.
- There is no nearby-places enrichment yet.

## Iteration 2 Strategy

Instead of mixing everything at once, iteration 2 should be executed as a controlled expansion with three parallel feature families:

1. `color`
2. `spatial_places`
3. `temporal_seasonal`

These should first be added to the enriched image-level dataset, then tested in multiple candidate feature-space variants before deciding whether they belong in the final reduced clustering matrix.

## A. Color Variables

## Why

The current pipeline converts the ROI to grayscale for segmentation, but the original ROI is still available in color before conversion. That makes color enrichment feasible without redesigning ROI extraction.

Color can help capture:

- yellowing or browning of the paper
- darker vs lighter particle deposits
- hue differences linked to lighting, paper aging, or deposit appearance
- background color shifts that grayscale summaries may hide

## Proposed color variables

Start with global ROI-level descriptors, not a high-dimensional histogram.

Recommended first batch:

- `roi_b_mean`, `roi_g_mean`, `roi_r_mean`
- `roi_b_std`, `roi_g_std`, `roi_r_std`
- `roi_h_mean`, `roi_s_mean`, `roi_v_mean`
- `roi_h_std`, `roi_s_std`, `roi_v_std`
- `roi_lab_l_mean`, `roi_lab_a_mean`, `roi_lab_b_mean`
- `roi_lab_l_std`, `roi_lab_a_std`, `roi_lab_b_std`
- `colorfulness`
- `particle_mask_mean_rgb_contrast`
- `particle_mask_mean_v_contrast`

Optional second batch if the first one is useful:

- masked color summaries inside particle regions only
- background-only color summaries outside the particle mask
- simple color ratios such as `r_g_ratio`, `r_b_ratio`, `b_g_ratio`

## Implementation note

Color features should be extracted from the standardized ROI after resize, using the same ROI that feeds the grayscale pipeline, so all descriptors remain aligned row by row.

## B. Spatial Variables With Google Places

## Why

Coordinates alone are weakly interpretable. Nearby places can create practical exposure proxies such as traffic, green areas, industrial surroundings, transit nodes, fuel-related activity, or construction-related surroundings.

This can help move the interpretation from "where on the map" to "what surrounds the sensor."

## Proposed Google Places enrichment

For each image or sensor location, query nearby places once within a `500m` radius and cache the result.

Recommended categories to derive:

- park / natural area density
- transit_station / bus / train density
- gas_station density
- parking density
- industrial / warehouse / logistics proxy density
- construction / hardware / building-material proxy density
- major road proxy if available from place types or route presence

Recommended aggregate variables:

- `places_total_within_500m`
- `places_transit_within_500m`
- `places_park_within_500m`
- `places_gas_station_within_500m`
- `places_parking_within_500m`
- `places_industrial_within_500m`
- `places_construction_within_500m`
- `places_major_road_proxy_within_500m`
- `dominant_place_category`
- `place_diversity_entropy`
- `green_vs_traffic_ratio_500m`

## Practical design

Google Places should enrich unique sensor coordinates, not every image independently.

That means:

- one cache row per unique `(latitude, longitude)` or per `sensor_id`
- the cache is reused across dataset rebuilds
- the clustering dataset only receives the final aggregated numeric/categorical columns

## Risks and controls

- API quota and billing
- category noise from broad place typing
- bias toward dense urban zones
- incomplete coverage for rural areas

Controls:

- keep the raw Places response in a cache file
- create deterministic aggregation rules
- include missingness flags
- normalize count variables by total nearby places when useful

## C. Temporal and Seasonal Variables

## Why

Temporal structure is already showing association with the current clusters, so it should be tested as a small input family instead of remaining only in the context step.

## Proposed temporal variables

Recommended first batch:

- `capture_month`
- `capture_season`

Recommended encoding for clustering:

- `capture_month_sin`
- `capture_month_cos`
- one-hot encoding for `capture_season`

## Important caution

Keep the temporal block intentionally small. Since the data only cover 2025 and 2026, `capture_year` is unlikely to add meaningful environmental information and may behave more like a collection-batch artifact than a real seasonal signal.

## Dataset and Pipeline Changes

## 1. Analysis service

Extend image-level feature generation so the ROI outputs include new color descriptors.

Likely insertion points:

- `analysis-service/src/dataset_features.py`
- `analysis-service/src/pipeline.py`

## 2. Dataset builder

Extend dataset assembly so it can join:

- Google Places aggregated features
- derived temporal features
- optional missingness flags for all new groups

Likely insertion point:

- `scripts/dataset/build_dataset.py`

## 3. Downstream clustering inputs

Create iteration-2 versions of the feature datasets, rather than overwriting the current baseline immediately.

Recommended outputs:

- `output/dataset/iteration2/image_features_enriched.csv`
- `output/dataset/iteration2/image_features_final.csv`
- `output/dataset/iteration2/places_cache.csv` or `.json`

## 4. Context analysis

Update context analysis only after the new dataset exists, mainly to:

- avoid duplicating derived temporal logic in multiple places
- compare whether the new variables help both clustering and post-hoc interpretation

## Feature-Space Variants To Benchmark

Do not jump directly to one final matrix. Benchmark several variants:

1. morphology baseline
2. morphology + color
3. morphology + temporal
4. morphology + spatial_places
5. morphology + color + temporal
6. morphology + color + spatial_places
7. morphology + temporal + spatial_places
8. morphology + color + temporal + spatial_places

Also keep PCA and selected-feature versions for each viable variant if dimensionality remains manageable.

## Reduction Rules For New Variables

The new variables should follow the same discipline as the baseline feature set:

- remove near-zero-variance features
- inspect missingness before clustering
- transform skewed count variables with `log1p` when appropriate
- correlation-filter dense families, especially place counts
- prefer cyclical encoding for `capture_month` rather than treating month as a linear integer
- keep category one-hot encoding limited and interpretable

## Validation Questions

Iteration 2 should answer these questions explicitly:

1. Do color variables change the final cluster structure in a stable way?
2. Do nearby-place variables improve interpretability without collapsing the solution into pure geography?
3. Do month and season improve environmental interpretability without acting as dataset-batch shortcuts?
4. Which added family gives the best tradeoff between robustness and interpretability?

## Recommended Execution Order

1. Add color descriptors to the image feature extraction layer.
2. Add deterministic temporal derivations to the dataset builder.
3. Implement Google Places caching and aggregated place features by unique location.
4. Build an enriched iteration-2 dataset without reduction first.
5. Run variable screening, missingness review, and redundancy filtering.
6. Export iteration-2 reduced datasets.
7. Run PCA.
8. Re-run the full clustering benchmark.
9. Re-run selection, explainability, taxonomy, and context analyses.
10. Compare iteration 2 against the current baseline in one summary table.

## Success Criteria

Iteration 2 should be considered successful if at least one enriched feature-space variant:

- passes the same stability thresholds as the current benchmark
- yields clusters that remain balanced and interpretable
- produces clearer contextual narratives than the current baseline
- does not depend entirely on raw location identity or on an overly dominant temporal shortcut

## Deliverables For This Iteration

- an iteration-2 enriched dataset
- a cached spatial enrichment layer from Google Places
- a reduced iteration-2 clustering matrix
- PCA outputs for iteration 2
- clustering benchmark outputs for the new feature-space variants
- a baseline-vs-iteration-2 comparison summary

## Immediate Next Step

Implement the enriched dataset layer first and keep it separate from the current production baseline. The main design principle for iteration 2 should be: add context, but preserve enough modularity to measure what each new feature family contributes.
