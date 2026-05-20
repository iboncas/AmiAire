# Iteration 3b Explanation

## Purpose

`iteration3b` is the renamed version of the previous `iteration3`.

It is the accepted no-grid rerun that evolves from `iteration2`, not from `iteration1`.

The workflow is:

1. detect likely grid vs no-grid ROIs from `data/combined.json`
2. manually review a sample where needed
3. apply the final no-grid decision back onto the richer `iteration2` dataset
4. rerun PCA, clustering, selection, explainability, taxonomy, and context on that filtered `iteration2` feature space

So `iteration3b` is:

- a no-grid subset definition
- applied to the `iteration2` enriched dataset
- followed by the standard downstream rerun

## Main Paths

- Grid-prediction dataset: `iteration3b/output/dataset`
- Manual review CSV: `iteration3b/output/grid_review/grid_review_simple.csv`
- Filtered iteration2 dataset: `iteration3b/output/no_grid_from_iteration2`
- Accepted downstream analysis root: `iteration3b/output/analysis_iter2_nogrid`

## Core Scripts

- [build_dataset_from_combined.py](./build_dataset_from_combined.py)
- [build_grid_review.py](./build_grid_review.py)
- [label_grid_review_interactive.py](./label_grid_review_interactive.py)
- [filter_iteration2_by_no_grid.py](./filter_iteration2_by_no_grid.py)

## Commands

Build grid predictions:

```bash
python3 iteration3b/build_dataset_from_combined.py \
  --input-json data/combined.json \
  --output-dir iteration3b/output/dataset
```

Create the review CSV:

```bash
python3 iteration3b/build_grid_review.py \
  --input-csv iteration3b/output/dataset/image_features_enriched.csv \
  --output-dir iteration3b/output/grid_review \
  --mode sample
```

Label the review set:

```bash
python3 iteration3b/label_grid_review_interactive.py \
  --input-csv iteration3b/output/grid_review/grid_review_simple.csv \
  --combined-json data/combined.json
```

Filter the iteration2 dataset:

```bash
python3 iteration3b/filter_iteration2_by_no_grid.py \
  --iteration2-dataset-dir iteration2/output/dataset \
  --grid-review-csv iteration3b/output/grid_review/grid_review_simple.csv \
  --grid-predictions-csv iteration3b/output/dataset/image_features_enriched.csv \
  --output-dir iteration3b/output/no_grid_from_iteration2
```

Run PCA:

```bash
python3 iteration1/analysis/pca/run.py \
  --input-csv iteration3b/output/no_grid_from_iteration2/image_features_final.csv \
  --output-dir iteration3b/output/analysis_iter2_nogrid/pca
```

Run K-means benchmark:

```bash
python3 iteration1/analysis/kmeans/run.py \
  --selected-input-csv iteration3b/output/no_grid_from_iteration2/image_features_final.csv \
  --pca-input-csv iteration3b/output/analysis_iter2_nogrid/pca/pca_scores_retained.csv \
  --output-dir iteration3b/output/analysis_iter2_nogrid/kmeans \
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
  --analysis-root iteration3b/output/analysis_iter2_nogrid \
  --output-dir iteration3b/output/analysis_iter2_nogrid/selection

python3 iteration1/analysis/explainability/run.py \
  --analysis-root iteration3b/output/analysis_iter2_nogrid \
  --feature-csv iteration3b/output/no_grid_from_iteration2/image_features_final.csv \
  --pca-scores-csv iteration3b/output/analysis_iter2_nogrid/pca/pca_scores_retained.csv \
  --pca-projection-csv iteration3b/output/analysis_iter2_nogrid/pca/pca_projection_2d.csv \
  --selection-summary-json iteration3b/output/analysis_iter2_nogrid/selection/summary.json \
  --output-dir iteration3b/output/analysis_iter2_nogrid/explainability

python3 iteration1/analysis/taxonomy/run.py \
  --explainability-dir iteration3b/output/analysis_iter2_nogrid/explainability \
  --output-dir iteration3b/output/analysis_iter2_nogrid/taxonomy

python3 iteration1/analysis/context/run.py \
  --analysis-root iteration3b/output/analysis_iter2_nogrid \
  --feature-csv iteration3b/output/no_grid_from_iteration2/image_features_final.csv \
  --selection-summary-json iteration3b/output/analysis_iter2_nogrid/selection/summary.json \
  --output-dir iteration3b/output/analysis_iter2_nogrid/context
```
