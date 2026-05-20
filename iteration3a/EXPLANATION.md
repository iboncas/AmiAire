# Iteration 3a Explanation

## Purpose

`iteration3a` is the no-grid rerun that evolves from `iteration1`.

The workflow is:

1. detect likely grid vs no-grid ROIs from `data/combined.json`
2. manually review a sample where needed
3. apply the final no-grid decision to `iteration1/output/dataset/image_features_final.csv`
4. rerun the usual downstream analysis on that filtered `iteration1` matrix

So `iteration3a` is:

- a no-grid subset definition
- applied to the `iteration1` final feature matrix
- followed by the standard `iteration1/analysis/*` rerun

## Main Paths

- Grid-prediction dataset: `iteration3a/output/dataset`
- Manual review CSV: `iteration3a/output/grid_review/grid_review_simple.csv`
- Filtered iteration1 dataset: `iteration3a/output/no_grid_from_iteration1`
- Downstream analysis root: `iteration3a/output/analysis_iter1_nogrid`

## Core Scripts

- [build_dataset_from_combined.py](./build_dataset_from_combined.py)
- [build_grid_review.py](./build_grid_review.py)
- [label_grid_review_interactive.py](./label_grid_review_interactive.py)
- [filter_iteration1_by_no_grid.py](./filter_iteration1_by_no_grid.py)

## Commands

Build grid predictions:

```bash
python3 iteration3a/build_dataset_from_combined.py \
  --input-json data/combined.json \
  --output-dir iteration3a/output/dataset
```

Create the review CSV:

```bash
python3 iteration3a/build_grid_review.py \
  --input-csv iteration3a/output/dataset/image_features_enriched.csv \
  --output-dir iteration3a/output/grid_review \
  --mode sample
```

Label the review set:

```bash
python3 iteration3a/label_grid_review_interactive.py \
  --input-csv iteration3a/output/grid_review/grid_review_simple.csv \
  --combined-json data/combined.json
```

Filter the iteration1 dataset:

```bash
python3 iteration3a/filter_iteration1_by_no_grid.py \
  --iteration1-dataset-dir iteration1/output/dataset \
  --grid-review-csv iteration3a/output/grid_review/grid_review_simple.csv \
  --grid-predictions-csv iteration3a/output/dataset/image_features_enriched.csv \
  --output-dir iteration3a/output/no_grid_from_iteration1
```

Run PCA:

```bash
python3 iteration1/analysis/pca/run.py \
  --input-csv iteration3a/output/no_grid_from_iteration1/image_features_final.csv \
  --output-dir iteration3a/output/analysis_iter1_nogrid/pca
```

Run K-means benchmark:

```bash
python3 iteration1/analysis/kmeans/run.py \
  --selected-input-csv iteration3a/output/no_grid_from_iteration1/image_features_final.csv \
  --pca-input-csv iteration3a/output/analysis_iter1_nogrid/pca/pca_scores_retained.csv \
  --output-dir iteration3a/output/analysis_iter1_nogrid/kmeans \
  --random-seed 7 \
  --stability-repeats 30 \
  --bootstrap-repeats 30 \
  --bootstrap-fraction 0.8 \
  --kmeans-n-init 50 \
  --feature-spaces selected_features,pca_scores
```

The same pattern applies for:

- `iteration1/analysis/ward/run.py`
- `iteration1/analysis/gmm/run.py`
- `iteration1/analysis/fuzzy/run.py`
- `iteration1/analysis/hdbscan/run.py`

Then continue with:

```bash
python3 iteration1/analysis/selection/run.py \
  --analysis-root iteration3a/output/analysis_iter1_nogrid \
  --output-dir iteration3a/output/analysis_iter1_nogrid/selection

python3 iteration1/analysis/explainability/run.py \
  --analysis-root iteration3a/output/analysis_iter1_nogrid \
  --feature-csv iteration3a/output/no_grid_from_iteration1/image_features_final.csv \
  --pca-scores-csv iteration3a/output/analysis_iter1_nogrid/pca/pca_scores_retained.csv \
  --pca-projection-csv iteration3a/output/analysis_iter1_nogrid/pca/pca_projection_2d.csv \
  --selection-summary-json iteration3a/output/analysis_iter1_nogrid/selection/summary.json \
  --output-dir iteration3a/output/analysis_iter1_nogrid/explainability

python3 iteration1/analysis/taxonomy/run.py \
  --explainability-dir iteration3a/output/analysis_iter1_nogrid/explainability \
  --output-dir iteration3a/output/analysis_iter1_nogrid/taxonomy

python3 iteration1/analysis/context/run.py \
  --analysis-root iteration3a/output/analysis_iter1_nogrid \
  --feature-csv iteration3a/output/no_grid_from_iteration1/image_features_final.csv \
  --selection-summary-json iteration3a/output/analysis_iter1_nogrid/selection/summary.json \
  --output-dir iteration3a/output/analysis_iter1_nogrid/context
```
