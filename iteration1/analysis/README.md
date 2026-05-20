# Downstream Analysis

This folder contains the downstream thesis workflow that starts from:

- `iteration1/output/dataset/image_features_final.csv`

The current structure covers:

1. PCA in [`iteration1/analysis/pca/run.py`](/Users/ibon-personal/Desktop/INFOR/iteration1/analysis/pca/run.py)
2. Per-method clustering benchmarks:
   - [`iteration1/analysis/kmeans/run.py`](/Users/ibon-personal/Desktop/INFOR/iteration1/analysis/kmeans/run.py)
   - [`iteration1/analysis/ward/run.py`](/Users/ibon-personal/Desktop/INFOR/iteration1/analysis/ward/run.py)
   - [`iteration1/analysis/gmm/run.py`](/Users/ibon-personal/Desktop/INFOR/iteration1/analysis/gmm/run.py)
   - [`iteration1/analysis/fuzzy/run.py`](/Users/ibon-personal/Desktop/INFOR/iteration1/analysis/fuzzy/run.py)
   - [`iteration1/analysis/hdbscan/run.py`](/Users/ibon-personal/Desktop/INFOR/iteration1/analysis/hdbscan/run.py)
3. Final-candidate selection in [`iteration1/analysis/selection/run.py`](/Users/ibon-personal/Desktop/INFOR/iteration1/analysis/selection/run.py)
4. Cluster explainability in [`iteration1/analysis/explainability/run.py`](/Users/ibon-personal/Desktop/INFOR/iteration1/analysis/explainability/run.py)
5. Morphology-to-source taxonomy suggestions in [`iteration1/analysis/taxonomy/run.py`](/Users/ibon-personal/Desktop/INFOR/iteration1/analysis/taxonomy/run.py)
6. Contextual association analysis in [`iteration1/analysis/context/run.py`](/Users/ibon-personal/Desktop/INFOR/iteration1/analysis/context/run.py)
7. MongoDB image-manifest export in [`iteration1/analysis/image_manifest_from_mongo.py`](/Users/ibon-personal/Desktop/INFOR/iteration1/analysis/image_manifest_from_mongo.py)

## Install dependencies

Use the repo-level Python requirements:

```bash
pip install -r requirements.txt
```

That covers PCA, clustering, plotting, and the optional HDBSCAN robustness check used in the downstream analysis.

## PCA

Run PCA first:

```bash
python3 iteration1/analysis/pca/run.py \
  --input-csv iteration1/output/dataset/image_features_final.csv \
  --output-dir iteration1/output/analysis/pca
```

The main downstream artifact is:

- `iteration1/output/analysis/pca/pca_scores_retained.csv`

## Clustering Benchmarks

Each method has its own script and can benchmark:

- `selected_features`
- `pca_scores`
- or both

Example K-means benchmark:

```bash
python3 iteration1/analysis/kmeans/run.py \
  --selected-input-csv iteration1/output/dataset/image_features_final.csv \
  --pca-input-csv iteration1/output/analysis/pca/pca_scores_retained.csv \
  --output-dir iteration1/output/analysis/kmeans \
  --random-seed 7 \
  --stability-repeats 30 \
  --bootstrap-repeats 30 \
  --bootstrap-fraction 0.8 \
  --kmeans-n-init 50 \
  --feature-spaces selected_features,pca_scores
```

Run the equivalent command for Ward, GMM, fuzzy C-means, and HDBSCAN in their respective folders.

## Final Selection

After the benchmarks finish, choose the final clustering candidate with the selection script:

```bash
python3 iteration1/analysis/selection/run.py \
  --analysis-root iteration1/output/analysis \
  --output-dir iteration1/output/analysis/selection
```

This produces:

- `all_candidates.csv`
- `eligible_candidates.csv`
- `shortlist.csv`
- `recommended_candidate_agreement.csv`
- `summary.json`
- `selection_tradeoff_plot.png`

By default, HDBSCAN is treated as a robustness-only method, not the main final model.

## Explainability

Generate explainability outputs for the recommended final candidate:

```bash
python3 iteration1/analysis/explainability/run.py \
  --analysis-root iteration1/output/analysis \
  --feature-csv iteration1/output/dataset/image_features_final.csv \
  --pca-scores-csv iteration1/output/analysis/pca/pca_scores_retained.csv \
  --pca-projection-csv iteration1/output/analysis/pca/pca_projection_2d.csv \
  --selection-summary-json iteration1/output/analysis/selection/summary.json \
  --output-dir iteration1/output/analysis/explainability
```

If you want to override the selected candidate manually:

```bash
python3 iteration1/analysis/explainability/run.py \
  --candidate-id pca_scores__fuzzy__k-4
```

Optional representative-image export:

```bash
python3 iteration1/analysis/image_manifest_from_mongo.py
```

That exports:

- `iteration1/output/dataset/image_manifest.csv`

The exported manifest can then be passed into explainability:

```bash
python3 iteration1/analysis/explainability/run.py \
  --image-paths-csv iteration1/output/dataset/image_manifest.csv
```

The optional CSV must include at least:

- `image_id`
- `image_path`

Without that manifest, the script still writes representative example IDs and metadata.

Explainability outputs include:

- `cluster_counts.csv`
- `cluster_descriptions.csv`
- `cluster_profile_mean.csv`
- `cluster_profile_median.csv`
- `cluster_profile_standardized.csv`
- `cluster_pca_positions.csv`
- `cluster_silhouette_summary.csv`
- `feature_discrimination.csv`
- `pairwise_feature_differences.csv`
- `representative_examples.csv`
- `borderline_examples.csv`
- `alternative_candidate_agreement.csv`
- `silhouette_samples.csv`
- `representative_examples_cluster_*.png`
- `borderline_examples_cluster_*.png`
- `cluster_profile_heatmap.png`
- `pca_colored_by_cluster.png`
- `silhouette_profile.png`
- `top_feature_boxplots.png`
- `surrogate_feature_importance.csv`
- `surrogate_feature_importance.png`

## Taxonomy Suggestions

Build cautious source-category suggestions from the explainability outputs:

```bash
python3 iteration1/analysis/taxonomy/run.py \
  --explainability-dir iteration1/output/analysis/explainability \
  --output-dir iteration1/output/analysis/taxonomy
```

This writes:

- `taxonomy_scores.csv`
- `taxonomy_suggestions.csv`
- `taxonomy_score_heatmap.png`
- `summary.json`

These are heuristic morphology-based suggestions for thesis interpretation. They are not chemical-identification claims.

## Contextual Association

Relate the selected clusters to the available project context variables:

```bash
python3 iteration1/analysis/context/run.py \
  --analysis-root iteration1/output/analysis \
  --feature-csv iteration1/output/dataset/image_features_final.csv \
  --selection-summary-json iteration1/output/analysis/selection/summary.json \
  --output-dir iteration1/output/analysis/context
```

If your selected method includes noise labels and you want to exclude them from the statistical tests:

```bash
python3 iteration1/analysis/context/run.py --exclude-noise
```

Context outputs include:

- `numeric_context_summary.csv`
- `numeric_context_tests.csv`
- `categorical_context_summary.csv`
- `categorical_context_tests.csv`
- `categorical_context_enrichment.csv`
- `context_model_feature_importance.csv`
- `context_model_feature_importance.png`
- `numeric_context_heatmap.png`
- `numeric_context_boxplots.png`
- `official_station_enrichment_heatmap.png`
- `capture_season_enrichment_heatmap.png`
- `summary.json`

This step uses project-native context first, especially:

- official-station PM variables
- station distance
- location
- capture-time derived variables such as month and season
- image references can now be pulled directly from MongoDB `tfg.records` through the manifest exporter when you want cluster image panels

## Current Default End-to-End Order

1. `iteration1/analysis/pca/run.py`
2. `iteration1/analysis/kmeans/run.py`, `iteration1/analysis/ward/run.py`, `iteration1/analysis/gmm/run.py`, `iteration1/analysis/fuzzy/run.py`, `iteration1/analysis/hdbscan/run.py`
3. `iteration1/analysis/selection/run.py`
4. `iteration1/analysis/explainability/run.py`
5. `iteration1/analysis/taxonomy/run.py`
6. `iteration1/analysis/context/run.py`
