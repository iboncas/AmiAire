# Execution Log

## Scope

This file tracks the implementation work completed from [`PLAN.md`](/Users/ibon-personal/Desktop/INFOR/iteration1/docs/PLAN.md), now covering phases 1 to 12 in code.

Current execution date: `2026-04-09`

## Status Overview

| Phase | Status | Notes |
| --- | --- | --- |
| 1. Define dataset and unit of analysis | Implemented in code | The pipeline emits image-level and particle-level outputs around one ROI per observation. |
| 2. Standardize image acquisition and QC | Implemented in code | ROI normalization and QC/status metadata are included in the dataset outputs. |
| 3. Build segmentation and feature extraction pipeline | Implemented in code | The classical CV pipeline exports per-particle measurements and image-level aggregations. |
| 4. Define the exact feature set | Implemented in code | Core, extended, and final-reduced feature catalogs are exposed. |
| 5. Clean the data before clustering | Implemented in dataset builder | The exporter applies winsorization, transforms, variance filtering, and scaling. |
| 6. Reduce redundancy and select variables properly | Implemented in dataset builder | Correlation filtering and family-balance rules produce the final reduced matrix. |
| 7. Perform PCA correctly | Implemented and executed | PCA now retains 7 components for 85% variance after the circularity/scaling fix. |
| 8. Run a proper clustering benchmark | Implemented and executed | Per-method benchmarks were run for K-means, Ward, GMM, fuzzy C-means, and HDBSCAN. |
| 9. Select the final clustering solution rigorously | Implemented and executed | A dedicated selection step now recommends a final candidate from the benchmark outputs. |
| 10. Explain the clusters properly | Implemented and executed | Cluster profiles, discriminative features, PCA-colored plots, representative examples, and surrogate explanations are produced. |
| 11. Build a taxonomy of likely contaminant or source categories | Implemented and executed | A cautious heuristic taxonomy layer now suggests likely source-category labels per cluster. |
| 12. Relate clusters to external environmental context | Implemented and executed on project-native context | Numeric and categorical association tests now run against the available station and capture-time variables. |

## Main Decisions Implemented

### Phase 1

- One processed ROI is the main observation unit.
- One segmented particle is the secondary observation unit.
- Three conceptual tables are produced:
  - `images_metadata`
  - `particles`
  - `image_features`

### Phase 2

- ROIs are standardized to `1000 x 1000` pixels before feature extraction.
- The dataset records:
  - `roi_detected`
  - `roi_width_px`
  - `roi_height_px`
  - `segmentation_method`
  - `analysis_success`
  - `segmentation_success`
  - `manual_qc_flag`
  - `failure_reason`
  - `blur_score_laplacian`
  - `zero_particle_flag`
- Rejected images remain represented in the raw analysis layer with failure metadata.

### Phase 3

- The baseline remains the current classical computer-vision flow:
  - ROI extraction
  - grayscale conversion
  - background correction
  - intensity rescaling
  - CLAHE contrast enhancement
  - Sauvola thresholding
  - region-based particle extraction
  - morphology-based filtering
- Per-particle measurements are exported instead of only aggregate counts.

### Phase 4

- Global descriptors included:
  - `num_particles`
  - `area_percentage`
  - `particle_density`
  - `mean_pixel_intensity`
  - `std_pixel_intensity`
  - `orientation_entropy`
  - `circular_variance`
- Particle descriptor families included:
  - `area`
  - `solidity`
  - `aspect_ratio`
  - `feret`
  - `equivalent_diameter`
  - `eccentricity`
  - `circularity`
  - `mean_intensity`
- Summary statistics included:
  - `median`
  - `iqr`
  - `p25`
  - `p75`
  - `p90`
  - `mean`
  - `std`

### Phase 5

- Images with failed ROI detection or failed analysis are excluded from the final clustering matrix.
- Zero-particle images are retained and marked with `zero_particle_flag`.
- Near-zero-variance features are removed.
- Numeric features are winsorized at the 1st and 99th percentiles.
- Strongly skewed count and size features are transformed with `log1p`.
- Retained features are scaled with a robust median/IQR transform.

### Phase 6

- Variable reduction starts from the extended morphological feature pool.
- Correlation filtering uses Spearman correlation with threshold `|rho| >= 0.90`.
- Family balance is applied so each descriptor family keeps only a limited set of summary roles.
- The exporter writes the reduced final matrix to:
  - `output/dataset/image_features_final.csv`

### Phase 7

- PCA is executed as a dedicated downstream step on the reduced Phase 6 matrix.
- The analysis step:
  - fits PCA on the selected standardized features
  - retains the smallest number of components reaching the configured explained-variance threshold
  - writes retained PCA scores
  - writes PCA loadings and variance tables
  - writes a 2D PCA projection
  - writes scree-plot artifacts when `matplotlib` is available
- The first PCA export was not accepted because PC1 was dominated by `circularity_p90`.
- Two upstream stabilizations were then applied:
  - particle `circularity` is now clipped to the valid `[0, 1]` range in [`analysis-service/src/dataset_features.py`](/Users/ibon-personal/Desktop/INFOR/analysis-service/src/dataset_features.py)
  - robust scaling now falls back to standard-deviation scaling when IQR-based scaling would explode a near-saturated feature in [`scripts/dataset/build_dataset.py`](/Users/ibon-personal/Desktop/INFOR/scripts/dataset/build_dataset.py)
- After rebuilding the dataset and rerunning PCA, the current accepted PCA result is:
  - `7` retained components for the `0.85` variance threshold
  - explained variance ratios starting with `0.3039`, `0.1760`, `0.1619`
  - a more balanced loading structure instead of a single-feature collapse

### Phase 8

- The clustering benchmark is implemented as separate downstream scripts, one per method.
- It benchmarks both:
  - the reduced selected features directly
  - the retained PCA scores
- Implemented methods:
  - K-means
  - Agglomerative clustering with Ward linkage
  - Gaussian Mixture Models with `full` and `diag` covariance options
  - fuzzy C-means
  - HDBSCAN as a robustness check
- For each candidate, the benchmark writes:
  - cluster assignments
  - internal clustering metrics
  - cluster-size distributions
  - repeat-fit stability summaries
  - bootstrap stability summaries

### Phase 9

- A dedicated selection step now aggregates all benchmark outputs and applies thesis-oriented gates before recommending a final candidate.
- The implemented default selection rule requires:
  - repeat-fit ARI `>= 0.95`
  - bootstrap ARI `>= 0.95`
  - smallest non-noise cluster fraction `>= 0.02`
  - noise fraction `<= 0.35`
- HDBSCAN is explicitly treated as a robustness-only method in the final-selection layer, matching the methodological note in [`PLAN.md`](/Users/ibon-personal/Desktop/INFOR/iteration1/docs/PLAN.md).
- A small interpretability bonus is applied to candidates in the preferred `k` range `3..6` so the final choice is not driven by a single metric alone.
- On the current benchmark outputs, the selection layer processed `72` candidates and marked `21` as eligible final-model candidates.
- The current recommended final candidate is:
  - `pca_scores__kmeans__k-4`
- Why this candidate was selected:
  - `silhouette_score = 0.3710`
  - `calinski_harabasz_score = 879.24`
  - `davies_bouldin_score = 1.0815`
  - `repeat_mean_ari = 1.0`
  - `bootstrap_mean_ari = 0.9929`
  - smallest cluster fraction `= 0.1236`
  - cluster fractions approximately `0.520`, `0.214`, `0.124`, `0.142`
- The main alternative kept on the shortlist is:
  - `pca_scores__fuzzy__k-4`
- A new agreement export now quantifies how close the recommended model is to the strongest alternatives:
  - `kmeans k=4` vs `kmeans k=5`: ARI `0.9229`
  - `kmeans k=4` vs `fuzzy k=4`: ARI `0.8661`
  - `kmeans k=4` vs `kmeans k=3`: ARI `0.7602`
- This improves the final selection argument because it shows the chosen solution is close to the strongest nearby alternatives, but still meaningfully different from the coarser `k=2` structure.
- HDBSCAN remained excluded from the final recommendation because it behaved as a strong robustness check but assigned about `60.7%` of samples to noise in the current run.

### Phase 10

- A dedicated explainability step now consumes the selected candidate assignment file and the reduced feature matrix.
- The implemented outputs are:
  - cluster counts
  - cluster descriptions in plain morphological language
  - cluster-profile tables using means and medians
  - a standardized cluster heatmap
  - a PCA scatter plot colored by cluster
  - PCA cluster position summaries
  - representative examples chosen as nearest-to-centroid rows in the actual clustering space
  - borderline examples with the weakest silhouette values inside each cluster
  - discriminative-feature ranking
  - pairwise cluster-difference tables
  - silhouette diagnostics per cluster
  - boxplots for the most discriminative features
  - surrogate-model explanations using random forest and multinomial-style logistic classification
- Important implementation note:
  - the current cluster profiles are computed from the saved Phase 6 feature matrix because the broader raw feature table is no longer persisted on disk
- Important implementation note:
  - representative examples are always exported as `image_id` rows and metadata
  - real image contact sheets are supported when an image-path manifest is available
- A MongoDB-backed manifest exporter was added so the image references can be pulled directly from:
  - database `tfg`
  - collection `records`
  - fields `_id` and `Imagen de entrada`
- The manifest was exported to:
  - `output/dataset/image_manifest.csv`
- The explainability step was rerun with that manifest, and it now produces real image panels for:
  - representative examples per cluster
  - borderline examples per cluster
- On the current selected `pca_scores__kmeans__k-4` solution, the strongest discriminative saved features are:
  - `aspect_ratio_median`
  - `area_median`
  - `mean_pixel_intensity`
  - `circularity_iqr`
  - `area_iqr`
  - `eccentricity_iqr`
  - `orientation_entropy`
  - `circular_variance`
  - `feret_p90`
  - `feret_iqr`
- The surrogate explainability step achieved:
  - random-forest balanced accuracy `0.9710 ± 0.0060`
  - logistic balanced accuracy `0.9908 ± 0.0032`
- This suggests that the discovered clusters are highly reproducible from the saved morphological feature set and therefore interpretable in feature space.
- The explainability layer now also compares the selected solution against the strongest non-selected alternative:
  - `pca_scores__fuzzy__k-4`
  - overlap agreement with the final selected solution: ARI `0.8661`, NMI `0.8270`
- The new silhouette summary shows the cluster-quality gradient inside the selected solution:
  - cluster `1` mean silhouette `0.4873`
  - cluster `2` mean silhouette `0.3243`
  - cluster `3` mean silhouette `0.2317`
  - cluster `4` mean silhouette `0.1357`
- This makes cluster `4` the weakest but still usable part of the final solution, which is useful to state explicitly in the results chapter.

### Phase 11

- A new taxonomy layer now converts cluster profiles into cautious source-category suggestions.
- This layer is intentionally heuristic and does not claim chemical identification.
- Implemented taxonomy categories:
  - `combustion_related`
  - `traffic_related`
  - `road_dust_or_resuspension`
  - `construction_or_mineral_dust`
  - `biological_or_organic`
  - `fibrous_material`
  - `industrial_particulate`
  - `mixed_or_unknown`
- The current run on the selected `kmeans k=4` solution suggests:
  - cluster `1`: `fibrous_material` with moderate confidence
  - cluster `2`: `combustion_related` with high confidence
  - cluster `3`: `fibrous_material` with high confidence
  - cluster `4`: `mixed_or_unknown` with high confidence
- The taxonomy evidence strings were improved so they now explain the direction of the supporting morphology, for example:
  - `lower aspect_ratio_median`
  - `higher orientation_entropy`
  - `lower circularity_median`
- These outputs are stored as score tables plus a heatmap so the taxonomy remains auditable and cautious.

### Phase 12

- A new contextual association step now relates the selected cluster solution to the project-native contextual variables already available in the reduced dataset.
- The implemented numeric context analysis currently uses:
  - `latitude`
  - `longitude`
  - `official_station_distance_km`
  - `record_pm10`
  - `record_pm25`
  - `official_pm10`
  - `official_pm25`
  - `official_pm25_to_pm10_ratio`
  - `official_pm10_minus_record_pm10`
  - `official_pm25_minus_record_pm25`
  - `abs_pm10_gap`
  - `abs_pm25_gap`
  - `official_pm_total`
  - `record_pm_total`
  - `capture_year`
  - `capture_month`
  - `capture_dayofyear`
  - `capture_weekday`
- The implemented categorical context analysis currently uses:
  - `official_station_id`
  - `capture_season`
  - `station_distance_band`
  - `official_pm25_band`
  - `official_pm10_band`
- Statistical tests now include:
  - Kruskal-Wallis plus Benjamini-Hochberg correction for numeric variables
  - chi-square plus Benjamini-Hochberg correction for categorical variables
- A categorical-enrichment layer was added on top of the chi-square tests using Pearson residuals, with heatmaps for:
  - `official_station_id`
  - `capture_season`
- On the current selected `kmeans k=4` solution, the strongest numeric associations were:
  - `capture_year`
  - `capture_dayofyear`
  - `abs_pm10_gap`
  - `official_station_distance_km`
  - `official_pm25`
  - `capture_month`
- The strongest categorical associations were:
  - `official_station_id`
  - `official_pm25_band`
  - `capture_season`
  - `station_distance_band`
- A predictive context layer was also added to estimate how much cluster membership is recoverable from context alone:
  - random-forest balanced accuracy `0.6491 ± 0.0262`
  - logistic balanced accuracy `0.5424 ± 0.0301`
- This supports a cautious interpretation that the clusters are associated with environmental context, but context alone does not fully explain the morphology clusters.

## Files Changed

### Added

- [`analysis/postprocess_common.py`](/Users/ibon-personal/Desktop/INFOR/iteration1/analysis/postprocess_common.py)
  - Shared readers, joins, plotting helpers, and statistics utilities for phases 9 to 12.
- [`analysis/image_manifest_from_mongo.py`](/Users/ibon-personal/Desktop/INFOR/iteration1/analysis/image_manifest_from_mongo.py)
  - Exports `image_id -> image_path` references from MongoDB for image-panel generation.
- [`analysis/selection/run.py`](/Users/ibon-personal/Desktop/INFOR/iteration1/analysis/selection/run.py)
  - Aggregates benchmark results and recommends the final clustering candidate.
- [`analysis/explainability/run.py`](/Users/ibon-personal/Desktop/INFOR/iteration1/analysis/explainability/run.py)
  - Produces cluster profiles, representative examples, PCA-colored plots, boxplots, and surrogate explanations.
- [`analysis/taxonomy/run.py`](/Users/ibon-personal/Desktop/INFOR/iteration1/analysis/taxonomy/run.py)
  - Produces cautious morphology-to-source taxonomy suggestions.
- [`analysis/context/run.py`](/Users/ibon-personal/Desktop/INFOR/iteration1/analysis/context/run.py)
  - Runs context-association tests and context-based predictive analyses.

### Updated

- [`analysis-service/src/dataset_features.py`](/Users/ibon-personal/Desktop/INFOR/analysis-service/src/dataset_features.py)
  - Clips `circularity` to the valid theoretical range before aggregation.
- [`scripts/dataset/build_dataset.py`](/Users/ibon-personal/Desktop/INFOR/scripts/dataset/build_dataset.py)
  - Uses a robust-scaling fallback when IQR scaling would produce unstable extremes.
- [`analysis/README.md`](/Users/ibon-personal/Desktop/INFOR/iteration1/analysis/README.md)
  - Documents the full downstream workflow from PCA through selection, explainability, taxonomy, and context analysis.
- [`EXECUTION.md`](/Users/ibon-personal/Desktop/INFOR/iteration1/docs/EXECUTION.md)
  - Updated to cover phases 9 to 12 and the current results.

## Downstream Output Files Now Produced

### Phase 7

- `output/analysis/pca/pca_report.json`
- `output/analysis/pca/pca_variance.csv`
- `output/analysis/pca/pca_scores_retained.csv`
- `output/analysis/pca/pca_projection_2d.csv`
- `output/analysis/pca/pca_loadings.csv`
- `output/analysis/pca/pca_scree_plot.png`
- `output/analysis/pca/pca_projection_2d.png`
- `output/analysis/pca/summary.json`

### Phase 8

Each clustering folder writes files such as:

- `benchmark_results.csv`
- `assignments/*.csv`
- `summary.json`

### Phase 9

- `output/analysis/selection/all_candidates.csv`
- `output/analysis/selection/eligible_candidates.csv`
- `output/analysis/selection/shortlist.csv`
- `output/analysis/selection/recommended_candidate_agreement.csv`
- `output/analysis/selection/robustness_only_candidates.csv`
- `output/analysis/selection/selection_tradeoff_plot.png`
- `output/analysis/selection/summary.json`

### Phase 10

- `output/analysis/explainability/cluster_counts.csv`
- `output/analysis/explainability/cluster_descriptions.csv`
- `output/analysis/explainability/cluster_pca_positions.csv`
- `output/analysis/explainability/cluster_profile_mean.csv`
- `output/analysis/explainability/cluster_profile_median.csv`
- `output/analysis/explainability/cluster_profile_standardized.csv`
- `output/analysis/explainability/cluster_silhouette_summary.csv`
- `output/analysis/explainability/silhouette_samples.csv`
- `output/analysis/explainability/feature_discrimination.csv`
- `output/analysis/explainability/pairwise_feature_differences.csv`
- `output/analysis/explainability/representative_examples.csv`
- `output/analysis/explainability/borderline_examples.csv`
- `output/analysis/explainability/alternative_candidate_agreement.csv`
- `output/analysis/explainability/representative_examples_cluster_1.png`
- `output/analysis/explainability/representative_examples_cluster_2.png`
- `output/analysis/explainability/representative_examples_cluster_3.png`
- `output/analysis/explainability/representative_examples_cluster_4.png`
- `output/analysis/explainability/borderline_examples_cluster_1.png`
- `output/analysis/explainability/borderline_examples_cluster_2.png`
- `output/analysis/explainability/borderline_examples_cluster_3.png`
- `output/analysis/explainability/borderline_examples_cluster_4.png`
- `output/analysis/explainability/cluster_profile_heatmap.png`
- `output/analysis/explainability/pca_colored_by_cluster.png`
- `output/analysis/explainability/silhouette_profile.png`
- `output/analysis/explainability/top_feature_boxplots.png`
- `output/analysis/explainability/surrogate_feature_importance.csv`
- `output/analysis/explainability/surrogate_feature_importance.png`
- `output/analysis/explainability/summary.json`

### Phase 11

- `output/analysis/taxonomy/taxonomy_scores.csv`
- `output/analysis/taxonomy/taxonomy_suggestions.csv`
- `output/analysis/taxonomy/taxonomy_score_heatmap.png`
- `output/analysis/taxonomy/summary.json`

### Phase 12

- `output/analysis/context/numeric_context_summary.csv`
- `output/analysis/context/numeric_context_tests.csv`
- `output/analysis/context/categorical_context_summary.csv`
- `output/analysis/context/categorical_context_tests.csv`
- `output/analysis/context/categorical_context_enrichment.csv`
- `output/analysis/context/context_model_feature_importance.csv`
- `output/analysis/context/context_model_feature_importance.png`
- `output/analysis/context/numeric_context_heatmap.png`
- `output/analysis/context/numeric_context_boxplots.png`
- `output/analysis/context/official_station_enrichment_heatmap.png`
- `output/analysis/context/capture_season_enrichment_heatmap.png`
- `output/analysis/context/summary.json`

## Verification

Completed:

- `python3 -m compileall analysis-service/src`
- `python3 -m compileall analysis`
- `python3 -m compileall scripts/dataset`
- `.venv/bin/python analysis/pca/run.py --help`
- `.venv/bin/python analysis/kmeans/run.py --help`
- `.venv/bin/python analysis/ward/run.py --help`
- `.venv/bin/python analysis/gmm/run.py --help`
- `.venv/bin/python analysis/fuzzy/run.py --help`
- `.venv/bin/python analysis/hdbscan/run.py --help`
- `.venv/bin/python analysis/selection/run.py`
- `.venv/bin/python analysis/image_manifest_from_mongo.py`
- `.venv/bin/python analysis/explainability/run.py`
- `.venv/bin/python analysis/taxonomy/run.py`
- `.venv/bin/python analysis/context/run.py`
- reran the later-phase scripts after adding stronger comparison, silhouette, description, and contextual-enrichment outputs
- reran explainability with the MongoDB-backed image manifest to generate real cluster image panels

Observed during verification:

- The explainability Kruskal-Wallis step originally emitted a SciPy tie warning for near-constant feature comparisons; the discrimination code was then hardened to skip degenerate tests.
- The contextual logistic-regression path initially showed convergence pressure on unscaled mixed context features; this was fixed by scaling the vectorized context design matrix before the final rerun.

## Remaining Work After Phase 12

- export or retain a raw feature table if you want cluster-profile values in raw physical or pre-scaled units instead of the reduced Phase 6 matrix
- provide an optional `image_id -> image_path` manifest if you want real representative image contact sheets instead of representative IDs only
- add Google Air Quality API and Places API enrichment if you want the broader contextual extension described in Phase 12
- complete the Phase 13 experiment write-up, final thesis figures, and chapter integration
- write the limitations explicitly in the thesis:
  - morphology is not chemistry
  - the taxonomy is heuristic
  - context associations are not proof of composition

## Change Log

### 2026-04-08

- stabilized circularity and scaling after the first PCA collapse
- reran PCA and confirmed a healthy 7-component retained representation
- completed the full per-method clustering benchmark on the retained dataset
- added a formal final-model selection layer and selected `pca_scores__kmeans__k-4`
- added explainability outputs for the selected candidate
- added a cautious source-taxonomy suggestion layer
- added project-native contextual association analysis
- updated the downstream documentation to reflect phases 7 to 12

### 2026-04-09

- strengthened the final-selection layer with agreement comparisons against the strongest shortlisted alternatives
- added cluster descriptions, silhouette diagnostics, pairwise cluster-difference tables, and borderline examples to explainability
- improved the taxonomy evidence strings so they describe directionality instead of only raw contribution signs
- extended the contextual analysis with PM gap variables, temporal derivatives, distance and pollution bands, and categorical-enrichment heatmaps
- added a MongoDB-backed image-manifest exporter and generated real representative and borderline contact sheets from the stored `Imagen de entrada` references
- refreshed the downstream documentation and execution log to describe the improved outputs
