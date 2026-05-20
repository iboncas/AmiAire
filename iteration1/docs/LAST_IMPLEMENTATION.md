# LAST IMPLEMENTATION PLAN

Current planning date: `2026-04-20`

Status: planning only. This document does not execute any code changes or reruns.

## Goal

Update the current pipeline so that:

1. the initial clustering feature set includes at least one new intensity or color-related variable
2. final-model selection gives its interpretability bonus only to `k=6`
3. explainability uses the new source taxonomy:
   - `combustion`
   - `mechanical`
   - `biological`
   - `synthetic`
   - `industrial`
   - `mixed_unknown`
4. explainability/context is enriched with spatial and temporal variables
5. the web app can return source-probability outputs such as `x% combustion`, `y% synthetic`

## Confirmed Decisions

- `k=6` stays as a preference bonus only
  - it is not a hard exclusion rule
- prefer real RGB/HSV color features
  - fallback to `intensity_entropy` only if the color path is not technically viable
- Google Places is deferred until you have an API key
  - the plan should explain how to add it later, but not depend on it now
- the web source prediction should use all variables that materially help prediction
  - in practice this means morphology + color + temporal + project-native context, and later Google Places when available

## Important Methodological Rule

Keep the core clustering input morphology-driven.

Google Places variables and temporal variables should be added as explainability/context variables by default, not mixed into the clustering matrix, unless you explicitly want to change the thesis framing from:

> morphology clustering + contextual interpretation

to:

> morphology and context joint clustering

For the thesis, the first option is safer.

## Planned Changes

### 1. Add a new intensity variable to the initial feature set

Preferred change:

- add real color descriptors from the standardized ROI

Recommended first color set:

- `mean_hue`
- `std_hue`
- `mean_saturation`
- `std_saturation`
- `mean_value`
- `std_value`

Recommended robustness note:

- hue is circular, so the implementation should prefer either:
  - circular hue statistics, or
  - simple hue summaries only after verifying they behave stably on this dataset

Files to change:

- `analysis-service/src/dataset_features.py`
  - compute RGB/HSV-derived features inside `build_image_feature_record()`
  - add the empty placeholder in `build_empty_image_feature_record()`
  - expose it in `CORE_IMAGE_FEATURE_SET`
  - expose it in `EXTENDED_IMAGE_FEATURE_SET`
  - include it in `PHASE6_DEFAULT_FEATURE_SET` if it should reach clustering
- `analysis-service/src/pipeline.py`
  - pass the standardized color ROI into the feature builder, not only grayscale
- `scripts/dataset/build_dataset.py`
  - add the same color columns to `EXTENDED_FEATURE_SET_FALLBACK`
  - add the same color columns to `PHASE6_DEFAULT_FALLBACK`
  - ensure it passes through the numeric preprocessing path

Fallback only if color cannot be implemented cleanly:

- add `intensity_entropy` as a grayscale-safe substitute

Planned decision for this iteration:

- plan for RGB/HSV first
- keep `intensity_entropy` only as fallback

### 2. Replace the taxonomy and make the clustering preference exact `k=6`

#### 2.1. New taxonomy

Replace the current category set in `analysis/taxonomy/run.py` with:

- `combustion`
- `mechanical`
- `biological`
- `synthetic`
- `industrial`
- `mixed_unknown`

Planned mapping logic:

- `combustion`:
  compact, small, dark, high-count soot-like patterns
- `mechanical`:
  abrasion, road-dust, mineral, resuspension, and construction-like patterns
- `biological`:
  irregular organic-looking and seasonally associated patterns
- `synthetic`:
  fibrous, elongated, plastic/textile-like patterns
- `industrial`:
  heterogeneous engineered or process-related particulate patterns
- `mixed_unknown`:
  fallback when the score is weak or ambiguous

Files to change:

- `analysis/taxonomy/run.py`
  - replace `CATEGORY_WEIGHTS`
  - rename output labels
  - update the fallback category to `mixed_unknown`
  - keep the confidence logic, but apply it to the new labels

Outputs that will change:

- `output/analysis/taxonomy/taxonomy_scores.csv`
- `output/analysis/taxonomy/taxonomy_suggestions.csv`
- `output/analysis/taxonomy/summary.json`
- `output/analysis/taxonomy/taxonomy_score_heatmap.png`

#### 2.2. Selection bonus only for `k=6`

Current behavior:

- `analysis/selection/run.py` gives a small granularity bonus to the preferred range `3..6`

Planned change:

- keep the current bonus mechanism exactly as a soft preference
- change the default `--preferred-k-range` from `3,6` to `6,6`
- update the CLI help text and comments so they describe a preferred target count, not a hard rule

Files to change:

- `analysis/selection/run.py`
- `analysis/README.md`
- `EXECUTION.md`
- `EXECUTION_CHANGES_SUMMARY.md`

Important consequence:

- the final selected candidate may stop being `pca_scores__kmeans__k-4`
- all downstream results that depend on the selected candidate must be regenerated after this change

### 3. Add spatial and temporal variables for explainability

Current state:

- `analysis/context/run.py` already derives:
  - `capture_year`
  - `capture_month`
  - `capture_dayofyear`
  - `capture_weekday`
  - `capture_season`
- Google Places enrichment does not exist yet
- the explainability layer does not currently export a cluster-vs-context profile table

Planned change:

- keep the existing time variables
- strengthen them with cyclic and duration features
- expose the temporal variables immediately
- define the Google Places integration as a later extension, not as a dependency for the next implementation pass
- expose the resulting variables in the context and explainability outputs

#### 3.1. Temporal variables to add

Add:

- `exposure_days`
  - derived from `collection_datetime - capture_datetime`
- `capture_month_sin`
- `capture_month_cos`
- `capture_dayofyear_sin`
- `capture_dayofyear_cos`

Why:

- `capture_season` is useful but coarse
- cyclic encodings capture seasonality better for plots and models
- `exposure_days` may matter because the amount and type of visible deposition can depend on exposure time

#### 3.2. Spatial variables from Google Places

Current decision:

- do not implement this yet
- prepare the integration design so it can be added later when the API key is available

Use grouped place families instead of raw Google categories.

Recommended grouped variables:

- `places_industrial_count_500m`
- `places_green_count_500m`
- `places_transport_count_500m`
- `places_commercial_count_500m`
- `places_construction_count_500m`
- `places_industrial_nearest_m`
- `places_green_nearest_m`
- `places_transport_nearest_m`

If needed, extend to `250m` and `1000m`, but do not start with too many redundant radii.

Recommended implementation shape:

- add a separate enrichment step with API caching instead of embedding Google calls directly into every analysis script

Suggested new script:

- `scripts/context/enrich_places.py`

Suggested behavior:

- read image or sensor locations from the dataset outputs
- query Google Places per unique location
- cache responses on disk
- write a merged contextual table for downstream analysis

How to implement it later:

1. create `scripts/context/enrich_places.py`
2. read unique `(latitude, longitude)` pairs from the dataset
3. query Google Places once per unique location and radius
4. map raw place types into grouped families:
   - transport
   - industrial
   - construction
   - green
   - commercial
5. persist a local cache so reruns do not re-query the same locations
6. write a merged CSV keyed by `image_id` or `sensor_id`
7. extend `analysis/context/run.py` and `analysis/explainability/run.py` to read those columns when present
8. keep the scripts tolerant to missing Places columns so the pipeline still works before the API is configured

Files to change:

- `scripts/dataset/build_dataset.py`
  - write the metadata/context outputs needed by the enrichment step
- `analysis/context/run.py`
  - read the enriched Google Places table
  - include the new spatial and temporal variables in summaries, tests, and plots
- `analysis/explainability/run.py`
  - add a cluster-vs-context profile export so these new variables appear in the explainability package
- `README.md`
- `backend/README.md`
  - document `GOOGLE_PLACES_API_KEY` and the caching workflow

Suggested new outputs:

- `output/dataset/context_enriched.csv`
- `output/analysis/context/google_places_summary.csv`
- `output/analysis/context/google_places_tests.csv`
- `output/analysis/context/google_places_heatmap.png`
- `output/analysis/explainability/cluster_context_profile.csv`
- `output/analysis/explainability/cluster_context_profile_heatmap.png`

### 4. Add source-probability prediction to the web app

Recommended approach:

1. export a deployable source-prediction artifact offline from the final selected clustering solution
2. run the same feature extraction online for a new sensor image
3. transform the new row with the same preprocessing and PCA pipeline
4. estimate cluster membership for the selected model
5. convert cluster membership into taxonomy probabilities
6. return those probabilities in the API and show them in the UI

This is preferable to inventing a separate fully supervised label model, because the current project already discovers the source structure through clustering plus taxonomy interpretation.

Prediction feature policy:

- use all variables that are available and defensible at inference time
- first deployment should include:
  - morphology features
  - RGB/HSV color features
  - temporal variables derived from the experiment dates
  - project-native context such as coordinates, nearest official-station variables, and existing PM context
- later deployment can add Google Places variables when the enrichment step exists and the key is configured

#### 4.1. Offline artifact export

Add a new export step after selection, explainability, and taxonomy.

Suggested new script:

- `analysis/source_prediction/export_model.py`

This exporter should save:

- preprocessing artifact
  - selected feature order
  - missing-value handling
  - winsorization bounds
  - log-transform flags
  - scaling parameters
- PCA artifact
  - component matrix
  - centering information
- deployable cluster artifact
  - centroids or equivalent cluster prototypes in the selected space
- cluster-to-taxonomy probability matrix
  - one probability distribution per cluster over:
    - `combustion`
    - `mechanical`
    - `biological`
    - `synthetic`
    - `industrial`
    - `mixed_unknown`

Important deployment rule:

- if the final selected method is not directly deployable for new samples, export a nearest-centroid approximation in PCA space

That matters because the current selection layer can recommend methods such as Ward or HDBSCAN, which are not naturally online-predictive in the same way as K-means or GMM.

#### 4.2. Online inference in the analysis service

Files to change:

- `analysis-service/src/pipeline.py`
  - call the new source predictor after `build_image_feature_record()`
- `analysis-service/src/app.py`
  - include `source_prediction` in `/process-image`
- new file `analysis-service/src/source_predictor.py`
  - load the exported artifact once
  - transform the current image feature row
  - return:
    - `top_source`
    - `source_probabilities`
    - `cluster_membership`
    - optional confidence or entropy

#### 4.3. Backend and frontend integration

Current observation:

- `backend/src/routes/analysis.js` already accepts `metadata` and `contextualData`
- `frontend/src/services/api.ts` does not send those fields when calling `processAnalysisImage()`
- `frontend/src/components/pages/ParticleAnalysisPage.tsx` already has the dates and coordinates in state, but it only uses them when saving the experiment

Planned frontend/backend changes:

- `frontend/src/services/api.ts`
  - extend `processAnalysisImage()` so it can send:
    - `metadata`
    - `contextualData`
  - extend the `ProcessedAnalysis` type with `sourcePrediction`
- `frontend/src/components/pages/ParticleAnalysisPage.tsx`
  - send `startDate`, `endDate`, `latitude`, and `longitude` during image analysis, not only during final save
  - add a result card that shows:
    - top predicted source
    - ranked probabilities for all six categories
- `backend/src/routes/analysis.js`
  - pass through the new `source_prediction` payload from the analysis service

Suggested UI output:

- top line:
  - `Posible origen dominante: combustion (62%)`
- detail lines:
  - `combustion: 62%`
  - `industrial: 14%`
  - `mechanical: 11%`
  - `synthetic: 7%`
  - `biological: 4%`
  - `mixed_unknown: 2%`

## Additional Technical Change Needed for Deployment

The current dataset builder reports Phase 5 and Phase 6 decisions, but it does not persist a reusable transform artifact with the exact preprocessing parameters needed for online inference.

To support the web predictor, add one more output from `scripts/dataset/build_dataset.py`:

- `output/dataset/phase5_phase6_transform.json`

It should store:

- imputation values
- winsorization bounds
- log-transform flags
- scaling centers and scales
- final selected column order

Without this, the online service cannot reproduce the exact same feature transformation used during the offline clustering analysis.

## What Must Be Executed Again After Implementation

Assumption: use the same Python environment as the previous runs. The commands below use `.venv/bin/python` to match the current repository style.

### 1. Rebuild the dataset and feature matrix

```bash
.venv/bin/python scripts/dataset/build_dataset.py \
  --backend-url http://localhost:3001 \
  --output-dir output/dataset \
  --image-batch-size 50 \
  --analysis-concurrency 6
```

Later, when Google Places is available, run the enrichment step after the dataset build:

```bash
.venv/bin/python scripts/context/enrich_places.py \
  --input-csv output/dataset/image_features_final.csv \
  --output-dir output/dataset
```

### 2. Recompute PCA

```bash
.venv/bin/python analysis/pca/run.py \
  --input-csv output/dataset/image_features_final.csv \
  --output-dir output/analysis/pca
```

### 3. Rerun the clustering benchmarks

```bash
.venv/bin/python analysis/kmeans/run.py \
  --selected-input-csv output/dataset/image_features_final.csv \
  --pca-input-csv output/analysis/pca/pca_scores_retained.csv \
  --output-dir output/analysis/kmeans \
  --random-seed 7 \
  --stability-repeats 30 \
  --bootstrap-repeats 30 \
  --bootstrap-fraction 0.8 \
  --kmeans-n-init 50 \
  --feature-spaces selected_features,pca_scores
```

```bash
.venv/bin/python analysis/ward/run.py \
  --selected-input-csv output/dataset/image_features_final.csv \
  --pca-input-csv output/analysis/pca/pca_scores_retained.csv \
  --output-dir output/analysis/ward \
  --random-seed 7 \
  --stability-repeats 30 \
  --bootstrap-repeats 30 \
  --bootstrap-fraction 0.8 \
  --feature-spaces selected_features,pca_scores
```

```bash
.venv/bin/python analysis/gmm/run.py \
  --selected-input-csv output/dataset/image_features_final.csv \
  --pca-input-csv output/analysis/pca/pca_scores_retained.csv \
  --output-dir output/analysis/gmm \
  --random-seed 7 \
  --stability-repeats 30 \
  --bootstrap-repeats 30 \
  --bootstrap-fraction 0.8 \
  --feature-spaces selected_features,pca_scores
```

```bash
.venv/bin/python analysis/fuzzy/run.py \
  --selected-input-csv output/dataset/image_features_final.csv \
  --pca-input-csv output/analysis/pca/pca_scores_retained.csv \
  --output-dir output/analysis/fuzzy \
  --random-seed 7 \
  --stability-repeats 30 \
  --bootstrap-repeats 30 \
  --bootstrap-fraction 0.8 \
  --feature-spaces selected_features,pca_scores
```

```bash
.venv/bin/python analysis/hdbscan/run.py \
  --selected-input-csv output/dataset/image_features_final.csv \
  --pca-input-csv output/analysis/pca/pca_scores_retained.csv \
  --output-dir output/analysis/hdbscan \
  --random-seed 7 \
  --stability-repeats 30 \
  --bootstrap-repeats 30 \
  --bootstrap-fraction 0.8 \
  --feature-spaces selected_features,pca_scores
```

### 4. Rerun final selection with the new exact `k=6` preference

```bash
.venv/bin/python analysis/selection/run.py \
  --analysis-root output/analysis \
  --output-dir output/analysis/selection \
  --preferred-k-range 6,6
```

### 5. Regenerate explainability

```bash
.venv/bin/python analysis/explainability/run.py \
  --analysis-root output/analysis \
  --feature-csv output/dataset/image_features_final.csv \
  --pca-scores-csv output/analysis/pca/pca_scores_retained.csv \
  --pca-projection-csv output/analysis/pca/pca_projection_2d.csv \
  --selection-summary-json output/analysis/selection/summary.json \
  --output-dir output/analysis/explainability
```

Optional, if you want real image panels again:

```bash
.venv/bin/python analysis/image_manifest_from_mongo.py
```

Then rerun explainability with:

```bash
.venv/bin/python analysis/explainability/run.py \
  --image-paths-csv output/dataset/image_manifest.csv
```

### 6. Regenerate taxonomy with the new six-category schema

```bash
.venv/bin/python analysis/taxonomy/run.py \
  --explainability-dir output/analysis/explainability \
  --output-dir output/analysis/taxonomy
```

### 7. Regenerate context analysis

```bash
.venv/bin/python analysis/context/run.py \
  --analysis-root output/analysis \
  --feature-csv output/dataset/image_features_final.csv \
  --selection-summary-json output/analysis/selection/summary.json \
  --output-dir output/analysis/context
```

### 8. Export the new web-facing source model

Planned new command:

```bash
.venv/bin/python analysis/source_prediction/export_model.py \
  --feature-csv output/dataset/image_features_final.csv \
  --pca-dir output/analysis/pca \
  --selection-summary-json output/analysis/selection/summary.json \
  --taxonomy-dir output/analysis/taxonomy \
  --output-dir output/analysis/source_prediction
```

### 9. Restart the application

If using Docker:

```bash
docker compose up -d --build
```

If running manually, restart:

- analysis service
- backend
- frontend

## Files Most Likely to Change

- `analysis-service/src/dataset_features.py`
- `analysis-service/src/pipeline.py`
- `analysis-service/src/app.py`
- `analysis-service/src/source_predictor.py` new
- `scripts/dataset/build_dataset.py`
- `scripts/context/enrich_places.py` new
- `analysis/selection/run.py`
- `analysis/explainability/run.py`
- `analysis/taxonomy/run.py`
- `analysis/context/run.py`
- `analysis/source_prediction/export_model.py` new
- `backend/src/routes/analysis.js`
- `frontend/src/services/api.ts`
- `frontend/src/components/pages/ParticleAnalysisPage.tsx`
- `analysis/README.md`
- `EXECUTION.md`
- `EXECUTION_CHANGES_SUMMARY.md`
- `README.md`
- `backend/README.md`

## Remaining Note

The only unresolved implementation detail is the exact final color feature set.

Planned default:

- start with RGB/HSV summaries
- keep `intensity_entropy` as the fallback if hue-based variables prove unstable or too costly to integrate cleanly
