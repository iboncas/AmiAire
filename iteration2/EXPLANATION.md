# Iteration 2 Explanation

## Purpose

This document explains the current state of iteration 2 after rebuilding the dataset and rerunning the downstream analysis.

The goal of iteration 2 was to extend the iteration-1 clustering workflow with three additional feature families:

- color variables
- spatial context from Google Places
- temporal and seasonal variables

At this point, all three families are represented in the current iteration-2 outputs.

## Main Outputs

The main files for iteration 2 are:

- `iteration2/output/dataset/images_metadata.csv`
- `iteration2/output/dataset/places_cache.json`
- `iteration2/output/dataset/places_features.csv`
- `iteration2/output/dataset/image_features_enriched.csv`
- `iteration2/output/dataset/image_features_preprocessed.csv`
- `iteration2/output/dataset/image_features_final.csv`
- `iteration2/output/analysis/pca/`
- `iteration2/output/analysis/kmeans/`
- `iteration2/output/analysis/ward/`
- `iteration2/output/analysis/gmm/`
- `iteration2/output/analysis/fuzzy/`
- `iteration2/output/analysis/hdbscan/`
- `iteration2/output/analysis/selection/`
- `iteration2/output/analysis/explainability/`
- `iteration2/output/analysis/taxonomy/`
- `iteration2/output/analysis/context/`

## What Was Added

### Google Places enrichment

`iteration2/google_places_enrichment.py` queries Google Places once per unique location and stores the raw responses in `places_cache.json`.

Design choices kept in the current version:

- the cache is keyed by unique latitude and longitude
- only air-quality-relevant groups are exported
- `construction` was removed as a feature because it was not a reliable pollution proxy
- column names were simplified to short names such as `total`, `transit`, `park`, `gas_station`, `parking`, and `industrial`

Current Places counts:

- `1636` unique cached locations in `places_cache.json`
- `2565` rows in `places_features.csv`

Coverage in `places_features.csv`:

- `2037` rows have `total > 0`
- `1020` rows have `transit > 0`
- `528` rows have `park > 0`
- `767` rows have `gas_station > 0`
- `869` rows have `parking > 0`
- `310` rows have `industrial > 0`
- `0` rows have `major_road_proxy > 0`

So `major_road_proxy` still exists in the enriched data, but it did not contribute useful nonzero signal in the current exported Places table.

### Temporal variables

The dataset builder derives temporal features from `capture_datetime`.

The implemented temporal block includes:

- `capture_month`
- `capture_season`
- `capture_month_sin`
- `capture_month_cos`
- season one-hot variables

Only the temporal variables that survived preprocessing and reduction remain in `image_features_final.csv`.

### Color variables

Color is now working in the current pipeline.

The dataset builder computes:

- RGB means and standard deviations
- HSV means and standard deviations
- LAB means and standard deviations
- `colorfulness`
- `particle_mask_mean_rgb_contrast`
- `particle_mask_mean_v_contrast`

Current population counts in `image_features_enriched.csv`:

- `roi_b_mean`: `2578`
- `roi_h_mean`: `2578`
- `roi_lab_l_mean`: `2578`
- `colorfulness`: `2578`
- `particle_mask_mean_rgb_contrast`: `2576`
- `particle_mask_mean_v_contrast`: `2576`

So color variables are no longer just implemented in code. They are now present in the actual dataset and are influencing the current results.

## Dataset Assembly

`iteration2/build_dataset.py` merges `places_features.csv` into the image-level feature rows.

Join logic:

- primary key: `sensor_id`
- fallback key: `image_id`

Current output sizes:

- `2652` rows in `image_features_enriched.csv`
- `2578` rows in `image_features_final.csv`
- `63` columns in `image_features_final.csv`

The difference between enriched rows and final rows is expected because preprocessing and reduction remove rows or columns that do not meet the phase-5 and phase-6 requirements.

## Final Reduced Dataset

The final clustering input is:

- `iteration2/output/dataset/image_features_final.csv`

The final reduced dataset now includes three kinds of information at once:

- morphology and intensity variables
- Google Places variables
- temporal variables
- selected color variables

Places-derived variables present in the final file:

- `total`
- `transit`
- `park`
- `gas_station`
- `parking`
- `industrial`
- `place_diversity_entropy`
- `green_vs_traffic_ratio_500m`

Selected color variables that survived reduction:

- `roi_s_mean`
- `roi_s_std`
- `roi_v_mean`
- `roi_v_std`
- `roi_lab_l_mean`
- `roi_lab_b_mean`
- `roi_lab_b_std`
- `particle_mask_mean_rgb_contrast`
- `roi_h_mean`
- `roi_h_std`
- `roi_lab_a_mean`
- `roi_lab_a_std`

Temporal variables that survived include:

- `capture_month_sin`
- `season_winter`
- `season_spring`
- `season_summer`
- `season_autumn`

Still absent from the final reduced matrix:

- `dominant_place_category`
- `major_road_proxy`
- some raw color columns that were available in the enriched file but were later dropped by reduction

`dominant_place_category` remains useful for enriched interpretation, but not as a final clustering input.

## PCA Results

PCA was run on the rebuilt `image_features_final.csv`.

Current PCA summary:

- `2578` rows used
- `46` numeric feature columns used for PCA
- variance threshold: `0.85`
- retained components: `17`

This is larger than the earlier PCA run because color variables are now part of the usable feature space.

## Benchmarking Results

The following clustering families were benchmarked:

- K-means
- Ward linkage
- Gaussian mixture models
- fuzzy C-means
- HDBSCAN

The selection step evaluated:

- `72` candidates total
- `7` eligible final candidates

HDBSCAN is still treated as a robustness-only method, not the default final model.

### Selected final candidate

The current recommended final candidate is:

- `pca_scores__kmeans__k-3`

Main metrics:

- silhouette score: `0.23815774241001894`
- Calinski-Harabasz score: `378.4001543596621`
- Davies-Bouldin score: `1.886221722772742`
- repeat mean ARI: `0.9991310968664148`
- bootstrap mean ARI: `0.9886472360439026`
- smallest cluster fraction: `0.14235841737781227`
- noise fraction: `0.0`

This means the best current solution is a stable 3-cluster K-means model on PCA scores.

### Shortlist

The top shortlist currently begins with:

1. `pca_scores__kmeans__k-3`
2. `pca_scores__kmeans__k-4`
3. `selected_features__kmeans__k-3`
4. `selected_features__kmeans__k-4`
5. `selected_features__kmeans__k-5`

So K-means dominates the final shortlist in the current run.

## Explainability Results

Explainability was run on:

- `pca_scores__kmeans__k-3`

The selected solution has `3` clusters:

- cluster `1`: `1773` rows, `0.6877424359968968`
- cluster `2`: `367` rows, `0.14235841737781227`
- cluster `3`: `438` rows, `0.16989914662529093`

### Top discriminative features

The strongest discriminators now are:

- `eccentricity_iqr`
- `mean_pixel_intensity`
- `aspect_ratio_iqr`
- `roi_v_std`
- `roi_s_std`
- `area_median`
- `eccentricity_p90`
- `solidity_iqr`
- `feret_p90`
- `circularity_median`

This is an important change from the earlier state. Color variables are now among the top discriminative features, especially:

- `roi_v_std`
- `roi_s_std`

### Cluster 1

Summary:

- heterogeneous circularity
- less circular particles

Top positive signature:

- `aspect_ratio_iqr`
- `mean_intensity_median`
- `roi_h_mean`
- `circularity_iqr`

Top negative signature:

- `circularity_median`
- `transit`
- `parking`
- `gas_station`

This cluster is still strongly morphology-driven, but it also shows spatial signal in the negative signature.

### Cluster 2

Summary:

- very elongated tail cases
- heterogeneous circularity
- less circular particles
- darker overall deposits

Top positive signature:

- `roi_v_std`
- `roi_s_std`
- `aspect_ratio_p90`
- `aspect_ratio_iqr`

Top negative signature:

- `mean_pixel_intensity`
- `mean_intensity_median`
- `circularity_median`
- `roi_h_mean`

This is the clearest evidence that color variables are contributing meaningfully in the current iteration-2 results.

### Cluster 3

Summary:

- larger particle bodies
- round compact particles
- high orientation dispersion
- broad directional spread

Top positive signature:

- `area_median`
- `circularity_median`
- `area_iqr`
- `orientation_entropy`

Top negative signature:

- `eccentricity_iqr`
- `aspect_ratio_iqr`
- `circularity_iqr`
- `aspect_ratio_p90`

## Taxonomy Results

The taxonomy step gives cautious morphology-based source suggestions.

Current suggestions:

- cluster `1`: `fibrous_synthetic_materials`, confidence `moderate`
- cluster `2`: `fibrous_synthetic_materials`, confidence `high`
- cluster `3`: `mixed_unknown`, confidence `moderate`

These are heuristic interpretation aids, not chemical identification.

## Context Analysis Results

The context step was run on the selected `pca_scores__kmeans__k-3` solution.

Top numeric associations:

- `capture_year`
- `official_pm25`
- `capture_dayofyear`
- `abs_pm10_gap`
- `record_pm10`

Top categorical associations:

- `official_station_id`
- `capture_season`
- `official_pm25_band`
- `station_distance_band`
- `official_pm10_band`

Strongest categorical signal:

- `official_station_id`
- chi-square: `1311.2589170454214`
- Cramer's V: `0.5042986121287667`

This suggests the current cluster structure is strongly associated with location and station context.

Context-model summary:

- random forest balanced accuracy mean: `0.6508827667451272`
- logistic balanced accuracy mean: `0.6075079406277887`

So context explains a meaningful part of the clustering structure, but it does not fully determine it.

## What Changed Compared With the Earlier Iteration-2 State

The earlier explanation is no longer valid in two important ways.

First, color variables are now populated and active.

Second, the selected final candidate changed from an older 2-cluster interpretation to the current:

- `pca_scores__kmeans__k-3`

Because of that, the current iteration-2 explanation should always be based on the new outputs, not on the older pre-color run.

## Main Interpretation

The current results support these conclusions:

- iteration 2 successfully adds real color, spatial, and temporal information to the pipeline
- morphology still matters strongly
- color now clearly contributes to discrimination, especially for the darker and more elongated cluster
- Google Places variables still help interpretation, even if they are not the dominant signal
- temporal and contextual variables remain associated with the final solution
- the best current solution is a stable 3-cluster PCA-based K-means model

## Caveats

- `major_road_proxy` still does not contribute useful nonzero values in the current Places export
- `construction` was intentionally removed from the Places grouping logic
- `dominant_place_category` remains descriptive only and is not part of the final reduced matrix
- the context analysis suggests that geography and capture-time structure are still influential, so interpretation should avoid claiming that the clusters are driven by morphology alone

## Practical Summary

Iteration 2 is now in a much better state than before.

The pipeline currently includes:

- working color features
- merged Google Places features
- temporal features
- full PCA, clustering, selection, explainability, taxonomy, and context outputs

The current thesis-ready summary is:

- iteration 2 produced a richer dataset than iteration 1
- color features now genuinely contribute to the clustering
- Places variables contribute mainly to interpretability
- the selected final solution is `pca_scores__kmeans__k-3`
- the final structure is still interpretable, stable, and more context-aware than the earlier baseline
