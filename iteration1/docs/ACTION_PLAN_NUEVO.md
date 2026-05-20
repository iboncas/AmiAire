# ACTION PLAN NUEVO

## Objective of This Document

This file explains, in simple and practical terms, what is still needed so the project can be presented as a complete degree thesis.

The project is already strong technically. The main missing parts are not "more AI", but:

1. validation of the image pipeline
2. stronger contextual interpretation
3. better reproducibility outputs
4. complete thesis writing, figures, and tables

This document turns the current project into a finish-the-thesis roadmap.

Current reference date: `2026-04-09`

## Current Project Status

At this point, the project already has:

- a dataset of `2565` retained image rows for analysis
- a reduced final feature matrix in `output/dataset/image_features_final.csv`
- PCA with `7` retained components for `85%` explained variance
- a clustering benchmark across K-means, Ward, GMM, fuzzy C-means, and HDBSCAN
- a selected final candidate: `pca_scores__kmeans__k-4`
- explainability outputs, representative images, cluster profiles, and surrogate explanations
- contextual analysis using project-native variables
- a cautious taxonomy layer for likely source categories

So the thesis is not "missing the core". The core exists.

What is still missing is the final academic layer that makes the work clearly thesis-ready and defensible.

## Main Idea

The thesis should be presented as:

> A reproducible pipeline that transforms DIY air-quality sensor images into morphological descriptors, discovers stable unsupervised clusters, explains those clusters, and relates them cautiously to environmental context and likely source scenarios.

This is the safe and strong framing.

Do not present it as:

> direct identification of pollutants from images

That would be too strong and hard to defend.

## What Still Needs To Be Done

There are four essential blocks:

1. manual QC and segmentation validation
2. stronger context analysis with control for year/station effects
3. saving the raw and intermediate datasets
4. finishing the thesis writing package: experiments, figures, tables, limitations

There is also one optional but useful extension:

5. Google Air Quality API and Google Places API as external contextual support

## Block 1. Manual QC and Segmentation Validation

## Why this is important

Right now, the pipeline is producing results, but the thesis still needs evidence that the image analysis is trustworthy.

A reviewer can ask:

- How do you know the ROI was correctly detected?
- How do you know the segmentation is reasonable?
- Are the clusters real morphology patterns, or just segmentation artifacts?

The best answer is a manual validation study.

## What "manual QC" means in easy words

It means a human checks a representative sample of images and decides whether the analysis result looks correct.

This is not about manually processing the whole dataset.
It is about validating a subset well.

## What to do

### Step 1. Build a QC subset

Select around `200` to `300` images.

This subset should include:

- different years
- different official stations or location areas
- low, medium, and high visible particle load
- easy images and difficult images
- some borderline or suspicious cases

### Step 2. Assign a QC label to each image

For each selected image, mark:

- `good`
- `acceptable`
- `bad`

Recommended interpretation:

- `good`: ROI and particles look correct, clearly usable
- `acceptable`: not perfect, but still usable
- `bad`: wrong ROI, blur, broken segmentation, unusable

### Step 3. Validate segmentation more directly

For a smaller subset of about `50` to `100` images:

- manually outline particles or trusted reference regions
- compare the algorithm output against the manual reference

Possible tools:

- ImageJ
- Napari
- a simple binary-mask annotation workflow

### Step 4. Report simple validation metrics

You do not need an excessively complex validation section.
Simple and clear is enough.

Good things to report:

- number and percentage of `good`, `acceptable`, `bad`
- examples of correct segmentation
- examples of incorrect segmentation
- optional overlap metrics if you create binary masks:
  - IoU
  - Dice score
- optional particle-count agreement for the manually checked subset

### Step 5. Use the QC result in the thesis

In the thesis, explicitly say:

- only `good` and `acceptable` images were retained for clustering
- `bad` images were excluded
- segmentation quality was assessed on a manually reviewed subset

## What files to create for this block

Recommended outputs:

- `output/qc/manual_qc_labels.csv`
- `output/qc/segmentation_validation.csv`
- `output/qc/qc_examples_good/`
- `output/qc/qc_examples_bad/`
- `output/qc/segmentation_validation_examples/`

Recommended columns for `manual_qc_labels.csv`:

- `image_id`
- `qc_label`
- `qc_notes`
- `reviewer`
- `review_date`

Recommended columns for `segmentation_validation.csv`:

- `image_id`
- `manual_particle_count`
- `pipeline_particle_count`
- `count_difference`
- `iou`
- `dice`
- `validation_notes`

## What to write in the thesis

Suggested meaning:

> A structured manual quality-control protocol was applied to a representative subset of the dataset. Images were labeled as good, acceptable, or bad according to ROI quality, blur, and segmentation usability. A smaller subset was manually annotated to validate segmentation quality more directly.

## Minimum acceptable outcome

Even if you do not have time for perfect mask annotation, at least do:

- the `200` to `300` image QC subset
- clear `good/acceptable/bad` labels
- a small segmentation comparison subset with examples

That already makes the thesis much stronger.

## Block 2. Rework the Context Analysis

## Why this is important

Right now, the context analysis shows associations, which is good.
But some of the strongest current signals are things like:

- `capture_year`
- `official_station_id`

This means a reviewer may say:

> Maybe the clusters are partly tracking collection campaign, time, or location, not just particle morphology.

That does not destroy the thesis, but it must be handled carefully.

## Main rule

Present context as:

- association
- enrichment
- plausibility support

Do not present context as:

- proof of composition
- direct source attribution
- real chemical validation

## What "control or stratify by year/station" means

It means you should check whether the cluster-context relationships still appear when you reduce the effect of time and place.

In simple words:

- if Cluster 2 is common in one year only, that may be a campaign effect
- if Cluster 3 is common near one station only, that may be a location effect

So you should repeat the analysis in a more careful way.

## What to do

### Step 1. Keep the current global context analysis

The current analysis is still useful.
Keep it as the first layer.

This layer answers:

- which context variables differ across clusters overall?

### Step 2. Add year-stratified analysis

Repeat key context comparisons within each `capture_year`.

For example:

- compare cluster vs `official_pm25` inside 2024 only
- compare cluster vs `official_pm25` inside 2025 only

If the same trend appears in multiple years, your argument becomes stronger.

### Step 3. Add station-aware analysis

Possible options:

- analyze the strongest stations separately
- group stations by zone or distance band
- include station identity as a control variable in a predictive model

You do not need a very advanced causal model.
A careful stratified analysis is already enough for a degree thesis.

### Step 4. Summarize the result in cautious language

Good interpretation:

> The morphology clusters show statistically significant association with several contextual variables, and some of these relationships remain visible after stratifying by capture year and station context.

Bad interpretation:

> The clusters prove the actual pollutant source.

## Extra useful analyses

If time allows, add:

- cluster vs context plots split by year
- top associations repeated after excluding dominant stations
- a table showing whether each main association remains, weakens, or disappears after stratification

## What files to create for this block

Recommended outputs:

- `output/analysis/context/context_by_year_summary.csv`
- `output/analysis/context/context_by_station_summary.csv`
- `output/analysis/context/context_stability_by_stratification.csv`
- `output/analysis/context/context_by_year_heatmap.png`
- `output/analysis/context/context_by_station_heatmap.png`

## What to write in the thesis

Suggested meaning:

> Because capture year and station identity were themselves associated with cluster membership, the contextual analysis was extended with stratified evaluations to reduce confounding by campaign and location. This step does not provide causal proof, but it improves the robustness of the contextual interpretation.

## Block 3. Persist the Raw and Intermediate Data Products

## Why this is important

Right now, the project saves the final reduced matrix, which is useful.
But for a thesis, you should also save the intermediate data.

Why:

- reproducibility
- auditability
- easier writing of methods and appendices
- easier interpretation in raw units

If someone asks:

> Which features were removed?
> Which values were scaled?
> Can I inspect particle-level data?

you should be able to answer with saved files.

## What to save

You should persist these outputs:

### 1. `images_metadata.csv`

One row per image.

Should include:

- IDs
- dates
- latitude/longitude
- ROI flags
- QC flags
- failure reasons
- image path if available

### 2. `particles.csv`

One row per segmented particle.

Should include:

- particle geometry
- intensity features
- image ID
- particle ID

### 3. `image_features_raw.csv`

One row per image.
This should be the aggregated feature table before:

- winsorization
- log transforms
- scaling
- reduction

This file is extremely useful for interpretation.

### 4. `image_features_preprocessed.csv`

Optional but very helpful.

This would contain:

- the cleaned/scaled Phase 5 matrix before Phase 6 feature reduction

### 5. `phase5_phase6_report.json`

This should record:

- eligible row count
- removed low-variance features
- winsorized features
- log-transformed features
- scaling method per feature
- removed correlated features
- family-balance removals
- final selected columns

## Recommended output structure

Recommended dataset folder:

- `output/dataset/images_metadata.csv`
- `output/dataset/particles.csv`
- `output/dataset/image_features_raw.csv`
- `output/dataset/image_features_preprocessed.csv`
- `output/dataset/image_features_final.csv`
- `output/dataset/phase5_phase6_report.json`
- `output/dataset/image_manifest.csv`

## Code work needed

The natural place to do this is in:

- `scripts/dataset/build_dataset.py`

This script already accumulates:

- image metadata rows
- particle rows
- image feature rows

So the main missing step is simply to write them to disk as CSV and JSON outputs.

## What to write in the thesis

Suggested meaning:

> To ensure reproducibility, the pipeline persisted not only the final reduced clustering matrix, but also the intermediate metadata, particle-level measurements, raw image-level feature table, and the complete preprocessing/reduction report used to obtain the final matrix.

## Block 4. Finish the Experiment Write-Up, Figures, Tables, and Limitations

## Why this is important

A thesis is not only code and outputs.
It is also a structured argument.

The thesis should make it easy for the reader to understand:

1. what problem was studied
2. what data was used
3. how the pipeline works
4. how the clustering was selected
5. how the clusters were interpreted
6. what the method can and cannot claim

## Phase 13 experiment write-up

You should explicitly document the experiment matrix, even if most experiments already exist in code.

The thesis should clearly state that you ran:

### E1. Segmentation baseline validation

- manual QC subset
- segmentation validation subset

### E2. Feature-set comparison

- core feature set
- extended feature set

### E3. Redundancy reduction comparison

- selected features without PCA
- selected features with PCA

### E4. Clustering benchmark

- K-means
- Ward
- GMM
- fuzzy C-means
- HDBSCAN

### E5. Explainability analysis

- cluster profiles
- representative images
- surrogate explainability

### E6. Contextual association analysis

- official station variables
- temporal context
- optional Google-based contextual variables

## Mandatory figures

These should appear in the thesis document itself.

### Essential figures

1. end-to-end methodology diagram
2. ROI extraction examples
3. segmentation examples
4. correlation heatmap of candidate features
5. PCA scree plot
6. PCA scatter colored by cluster
7. benchmark comparison figure across methods and `k`
8. representative images per cluster
9. cluster profile heatmap
10. contextual association plots

### Very useful extra figures

11. examples of failed or borderline segmentation
12. silhouette profile by cluster
13. context association after stratifying by year

## Mandatory tables

1. dataset summary table
2. feature dictionary table
3. segmentation validation summary table
4. clustering benchmark results table
5. final cluster description table
6. contextual association summary table

## Limitations chapter

This chapter is essential.
It does not weaken the thesis.
It strengthens it.

You should explicitly say:

- image morphology is not direct chemistry
- pixel-based measurements may not be physically calibrated
- segmentation quality affects the downstream features and clusters
- unsupervised clustering reveals patterns, not ground-truth pollutant labels
- contextual variables support interpretation but do not prove composition
- taxonomy suggestions are heuristic

## Recommended wording for the limitations chapter

Suggested meaning:

> The thesis does not claim direct chemical identification of pollutants from images alone. Instead, it studies whether reproducible and interpretable morphology patterns can be extracted from sensor images and whether these patterns are associated with plausible environmental contexts.

## Google Air Quality API and Google Places API

## Where they fit in the thesis

Your teacher's idea makes sense if these APIs are used correctly.

They should be used as:

- external contextual support
- real-world plausibility checks
- source-environment proxies

They should not be used as:

- laboratory validation
- chemical ground truth

## Best use of Google Places API

This is the most realistic and useful Google extension for the current project.

## What it can provide

For each sensor location, you can query nearby place types and build environmental proxy variables.

Examples:

- number of major roads or transport-related places nearby
- number of industrial-type places nearby
- density of construction-related places
- nearby parks or green areas
- commercial density
- urban-service density

Then you can test whether some morphology clusters are more common in certain surrounding environments.

## Good interpretation

Examples of cautious wording:

- Cluster 4 is associated with surroundings suggestive of road-dust or urban activity.
- Cluster 2 appears more often in locations with denser traffic-related place context.

This is defensible because you are talking about context and plausibility, not chemical proof.

## Best use of Google Air Quality API

This API can provide air-quality context for a location and time window.

However, there is an important practical limitation:

- as verified on `2026-04-09`, the Google Air Quality API history endpoint supports historical hourly data only up to `30` days back

This means:

- it is not suitable for reconstructing old captures from many months ago
- it is not enough by itself for the full historical dataset if your images are older than that window

So for this thesis, the best strategy is:

### For the full historical dataset

Use:

- official station data as the main historical external context

This remains the primary context source.

### For a small new validation subset

If possible, collect a recent mini-dataset now and enrich it with:

- Google Air Quality API
- Google Places API

This can become a small real-world extension experiment.

## Strong practical recommendation

Use the following hierarchy:

### Main context layer for the thesis

- official station variables
- project-native temporal context

### Strong optional extension

- Google Places API for land-use/source proxies across all locations

### Small prospective validation extension

- Google Air Quality API on a new recent subset only

This is the most realistic and academically safe approach.

## What variables to derive from Google Places

For each image or sensor location, calculate variables such as:

- count of selected place types within `250 m`
- count within `500 m`
- count within `1000 m`
- distance to nearest selected place type
- traffic-related place density
- industrial-related place density
- green-area density
- commercial/urban density

You do not need dozens of place types in the final thesis.
It is better to group them into a few interpretable categories.

Example grouped categories:

- traffic and transport context
- industrial context
- construction/mineral dust context
- urban/commercial context
- green/biological context

## How to analyze Google Places variables

Treat them exactly like other context variables:

- compare them across clusters
- apply multiple-testing correction
- report effect sizes
- interpret as contextual association only

## What to say in the thesis about Google APIs

Suggested meaning:

> Google-derived contextual variables were used as external environmental proxies. These variables enrich the interpretation of the discovered morphology clusters, but they do not constitute laboratory validation or direct proof of pollutant composition.

## Recommended Final Thesis Structure

Use a chapter structure like this:

1. Introduction
2. Background and Related Work
3. System Overview and Data Sources
4. Image Processing and Dataset Construction
5. Feature Engineering and Preprocessing
6. Dimensionality Reduction and Clustering Benchmark
7. Final Cluster Selection and Explainability
8. Environmental Context and External Association Analysis
9. Results
10. Limitations and Future Work
11. Conclusions

## What Each Chapter Should Contain

## Chapter 4. Image Processing and Dataset Construction

Should include:

- data source description
- ROI extraction
- segmentation pipeline
- metadata structure
- particle table
- image feature table
- QC protocol

## Chapter 5. Feature Engineering and Preprocessing

Should include:

- global features
- aggregated particle features
- transformations
- winsorization
- robust scaling
- feature reduction rules

## Chapter 6. Dimensionality Reduction and Clustering Benchmark

Should include:

- PCA rationale
- retained component count
- benchmarked clustering methods
- stability metrics
- selection criteria

## Chapter 7. Final Cluster Selection and Explainability

Should include:

- chosen final candidate
- cluster sizes
- representative images
- cluster descriptions
- discriminative features
- surrogate recovery of clusters

## Chapter 8. Environmental Context and External Association Analysis

Should include:

- official station analysis
- temporal analysis
- year/station-aware stratified analysis
- optional Google Places / Google Air extension
- careful interpretation language

## Exact Order of Work From Now On

This is the recommended order to finish the thesis efficiently.

### Step 1

Persist all missing dataset outputs:

- `images_metadata.csv`
- `particles.csv`
- `image_features_raw.csv`
- `image_features_preprocessed.csv`
- `phase5_phase6_report.json`

### Step 2

Run the manual QC study:

- build the `200` to `300` image QC subset
- label `good/acceptable/bad`
- produce summary counts

### Step 3

Run the segmentation validation subset:

- annotate `50` to `100` images or trusted regions
- compare against the pipeline
- export summary metrics and examples

### Step 4

Rebuild the final dataset if QC exclusions change the retained rows.

### Step 5

Extend the context analysis:

- by year
- by station or grouped station context

### Step 6

If time allows, enrich locations with Google Places API.

### Step 7

If possible, add a recent mini-dataset for Google Air Quality API contextual support.

### Step 8

Assemble the final figures and tables.

### Step 9

Write the methods/results chapters using the saved outputs.

### Step 10

Write the limitations and conclusions last, after all figures and tables are fixed.

## Minimum Version Needed To Finish the Thesis Well

If time becomes tight, the minimum strong version is:

1. save the raw and intermediate outputs
2. complete manual QC and basic segmentation validation
3. add year/station-aware context analysis
4. write the experiment matrix clearly
5. include the mandatory figures/tables
6. write the limitations honestly

This is enough for a strong degree thesis.

Google Places can improve it.
Google Air Quality API is useful only if you add a recent extension subset.

## Stronger Version If Time Allows

If there is enough time, the stronger version is:

1. everything in the minimum version
2. Google Places enrichment for all sensor locations
3. a recent prospective subset with Google Air Quality API context
4. a clearer appendix with raw feature dictionary and preprocessing report

## Concrete Deliverables Checklist

The thesis can be considered finished when all of these exist:

- `output/dataset/images_metadata.csv`
- `output/dataset/particles.csv`
- `output/dataset/image_features_raw.csv`
- `output/dataset/image_features_preprocessed.csv`
- `output/dataset/image_features_final.csv`
- `output/dataset/phase5_phase6_report.json`
- `output/qc/manual_qc_labels.csv`
- `output/qc/segmentation_validation.csv`
- updated context outputs with year/station-aware analysis
- final figure set for the thesis
- final table set for the thesis
- written limitations chapter
- written methodology/results chapters that match the saved outputs

## Final Thesis Positioning

The best final positioning of the work is:

> This thesis does not claim laboratory identification of contaminants from images alone. Instead, it presents a reproducible morphology-analysis pipeline for DIY air-quality sensor images, demonstrates that stable and interpretable unsupervised clusters can be recovered from those images, and shows that the discovered clusters are meaningfully associated with external environmental context.

That is strong, honest, and thesis-level.

