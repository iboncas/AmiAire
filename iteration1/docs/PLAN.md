# AI Thesis Plan: Clustering and Explainability for DIY Air Quality Sensor Images

## 1. Thesis Objective

Build an unsupervised AI pipeline that:

1. Extracts quantitative morphological descriptors from images of DIY air quality sensors.
2. Groups images into reproducible clusters based on particle morphology and image structure.
3. Explains the clusters with interpretable image features.
4. Relates the clusters to likely contaminant or emission-source categories using external contextual data.

This should be framed as:

> "Morphological clustering and explainability of DIY air quality sensor images, with contextual association to likely pollutant-source categories."

That wording is important. From images alone, you should not claim direct chemical identification of contaminants. You can claim association, consistency, or likely source categories.

## 2. What You Should and Should Not Claim

### What you can claim

- Images of sensor deposits contain measurable morphological patterns.
- Those patterns can be summarized into robust descriptors.
- Unsupervised learning can reveal recurring morphological groups.
- Those groups can be explained through feature profiles and representative images.
- Those groups can be associated with likely pollutant contexts using external environmental and location data.

### What you should not claim

- "This cluster is definitely NO2" or "this image proves a specific contaminant."
- "P-values selected the best features for clustering."
- "PCA proves the existence of contaminants."

## 3. Corrections to Your Initial Idea

Your idea is good, but three points need to be corrected so the methodology is academically stronger:

1. Do not use forward selection or backward elimination with p-values for unsupervised clustering.
   Those methods are designed for supervised inferential models, not for clustering without labels.
2. Do not jump from clusters directly to contaminants.
   Use the safer concept of "likely source categories" or "contextual contaminant association."
3. Do not start with too many redundant statistical summaries.
   Build a broad feature pool first, then reduce redundancy systematically before PCA.

## 4. Final Research Questions

Use these research questions in the thesis:

### RQ1

Can images of DIY air quality sensors be represented by morphological and intensity-based descriptors that are stable enough for unsupervised clustering?

### RQ2

Do these descriptors reveal recurrent and interpretable image groups?

### RQ3

Which image features explain the differences between the discovered clusters?

### RQ4

Are the discovered clusters associated with likely pollutant or emission-source contexts derived from environmental and geographic data?

## 5. Working Hypotheses

### H1

The images contain enough morphological structure to produce non-random clusters.

### H2

A reduced feature space built from particle morphology, density, coverage, intensity, and orientation descriptors will produce more stable clusters than raw high-dimensional summaries.

### H3

Some clusters will be associated with contextual signatures such as high PM10, high PM2.5, traffic-heavy surroundings, construction-related surroundings, or other source proxies.

## 6. Deliverables You Must Produce

By the end of the thesis, you should have all of these:

1. A reproducible image-processing pipeline.
2. A particle-level dataset.
3. An image-level feature dataset for clustering.
4. A cleaned and reduced feature matrix.
5. A clustering comparison study across several methods.
6. A final selected clustering solution.
7. An explainability analysis for the final clusters.
8. A contextual contaminant-source association analysis.
9. A complete set of figures and tables for the thesis.

## 7. Use the Existing Repository as the Baseline

Your repository already gives you a useful baseline:

- [`analysis-service/src/roi_extraction.py`](/Users/ibon-personal/Desktop/INFOR/analysis-service/src/roi_extraction.py) already extracts a region of interest from the sensor image.
- [`analysis-service/src/pipeline.py`](/Users/ibon-personal/Desktop/INFOR/analysis-service/src/pipeline.py) already performs grayscale conversion, background correction, contrast enhancement, Sauvola thresholding, and particle analysis.
- The current pipeline already returns:
  - number of contours
  - area percentage
  - total particle area

This means your AI work should start by extending the current image-analysis pipeline, not by starting from zero.

## 8. Exact Execution Plan

Follow the phases below in this order.

## Phase 1. Define the Dataset and the Unit of Analysis

### Goal

Decide exactly what one observation is.

### Decision

Use one processed sensor image ROI as the main observation for clustering.

That means:

- One row in the final clustering table = one image ROI.
- Each row will be built from aggregated particle descriptors extracted from that ROI.

Also create a second table at particle level:

- One row in the particle table = one segmented particle inside one ROI.

### Output of Phase 1

Create these tables:

#### Table A: `images_metadata`

Mandatory columns:

- `image_id`
- `sensor_id`
- `capture_datetime`
- `collection_datetime`
- `latitude`
- `longitude`
- `image_path` or storage URL
- `roi_detected`
- `roi_width_px`
- `roi_height_px`
- `segmentation_method`
- `analysis_success`
- `manual_qc_flag`

Optional columns if available:

- `device_type`
- `sensor_exposure_time`
- `paper_type`
- `camera_type`
- `magnification`
- `weather_context`
- `official_station_id`

#### Table B: `particles`

Mandatory columns:

- `image_id`
- `particle_id`
- `area_px`
- `perimeter_px`
- `equivalent_diameter_px`
- `major_axis_length_px`
- `minor_axis_length_px`
- `aspect_ratio`
- `solidity`
- `eccentricity`
- `feret_diameter_max_px`
- `orientation_rad`
- `circularity`
- `mean_intensity`
- `std_intensity`
- `min_intensity`
- `max_intensity`
- `centroid_x`
- `centroid_y`

#### Table C: `image_features`

This is the table used for clustering.

It must contain:

- metadata columns
- global image descriptors
- aggregated particle descriptors
- contextual environmental variables

### Data sufficiency targets

You now have approximately 2,500 images, which is more than enough for a strong clustering study.

Use that scale as an advantage, but do not develop the pipeline blindly on all images from the start.

Recommended interpretation of this dataset size:

- minimum acceptable retained dataset after QC: more than 1,000 good ROIs
- strong retained dataset after QC: 1,500 to 2,000 good ROIs
- excellent retained dataset after QC: more than 2,000 good ROIs

Also try to avoid final clusters with fewer than about 2 percent of the retained dataset unless they are explicitly treated as rare or noise patterns.

With 2,500 images, a sensible working strategy is:

1. use a pilot subset of about 300 to 500 images to tune preprocessing, segmentation, and feature engineering
2. freeze the pipeline
3. run the final analysis on the full retained dataset

## Phase 2. Standardize Image Acquisition and Quality Control

### Goal

Reduce noise caused by inconsistent image capture instead of actual morphology.

### Rules you should enforce

1. Use the same image resolution or rescale every ROI to a common size.
2. Keep illumination as consistent as possible.
3. Keep the same imaging protocol across samples whenever possible.
4. If scale calibration is unavailable, explicitly state that the analysis uses pixel-based morphology, not physical units.
5. Exclude images with severe blur, failed ROI extraction, or obviously broken segmentation.

### Manual quality-control protocol

Do not manually inspect all 2,500 images in detail. Instead, perform structured manual QC on a stratified subset.

Review at least 200 to 300 images manually and assign:

- `good`
- `acceptable`
- `bad`

Only `good` and `acceptable` images should enter the main clustering pipeline.

Use ImageJ or Napari for:

- visual inspection
- quick measurement checks
- manual annotation of a validation subset

Make the QC subset diverse. It should include:

- images from different dates or campaigns
- images with low, medium, and high visible particle load
- easy images and difficult images
- a sample of failed or borderline cases

For segmentation validation, manually annotate at least 50 to 100 images with particle masks or trusted reference regions.

## Phase 3. Build the Segmentation and Feature-Extraction Pipeline

### Goal

Extend the current pipeline so it produces particle-level and image-level features.

### Recommended approach

Start with the current classical computer-vision pipeline:

1. ROI extraction
2. grayscale conversion
3. background correction
4. contrast normalization
5. adaptive thresholding
6. connected-component or region-based particle extraction
7. particle filtering using morphology constraints

### Important implementation note

Do not only keep the current aggregate outputs. You must also export the per-particle measurements used to build the image-level statistics.

### If the classical segmentation is weak

Only introduce a segmentation model if the baseline fails on your validation subset.

Use this decision rule:

- If manual validation shows segmentation quality is acceptable, keep the classical pipeline.
- If segmentation quality is clearly insufficient, annotate a subset and test a segmentation model.

### Model fallback options

If you need a learned segmentation method, use one of these:

- U-Net
- Cellpose
- SAM-based assisted segmentation

Only mention SEM segmentation models if your image modality is actually comparable to SEM-like microscopy. Otherwise, describe them as possible future work or a fallback experiment.

## Phase 4. Define the Exact Feature Set

### 4.1 Core global image descriptors

These should always be included:

- `num_particles`
- `area_percentage`
- `particle_density`
- `mean_pixel_intensity`
- `std_pixel_intensity`
- `orientation_entropy`
- `circular_variance`

### Definitions

- `particle_density = num_particles / roi_area_px`
- `orientation_entropy` should be computed from a histogram of particle orientations, using a fixed number of bins such as 18.
- `circular_variance` should summarize the dispersion of particle orientations.

### 4.2 Particle attributes to measure

For each particle, measure at least:

- area
- solidity
- aspect ratio
- feret diameter
- equivalent diameter

You should also add:

- perimeter
- eccentricity
- circularity
- intensity features

That gives you a stronger morphological description than the original list alone.

### 4.3 Statistical summaries to compute at image level

For each particle attribute family, compute:

- median
- IQR
- p90

These three should be mandatory because they are robust and informative.

Then optionally compute:

- mean
- std
- p25
- p75

Do not start with too many percentiles. A good first pool is:

- median
- IQR
- p25
- p75
- p90
- mean
- std

### Recommended attribute families

Apply the summaries above to:

- area
- solidity
- aspect_ratio
- feret_diameter_max
- equivalent_diameter
- eccentricity
- circularity
- mean_intensity

### 4.4 Feature sets to compare

Build two feature sets:

#### Core feature set

Use:

- `num_particles`
- `area_percentage`
- `particle_density`
- `mean_pixel_intensity`
- `std_pixel_intensity`
- `orientation_entropy`
- `circular_variance`
- `area_median`
- `area_iqr`
- `area_p90`
- `solidity_median`
- `solidity_iqr`
- `aspect_ratio_median`
- `aspect_ratio_iqr`
- `feret_median`
- `feret_p90`
- `equivalent_diameter_median`
- `equivalent_diameter_p90`
- `circularity_median`
- `mean_intensity_median`

#### Extended feature set

Add the rest of the summary statistics and optional descriptors.

This comparison will make the thesis stronger because you can show whether the simpler, more robust set already works well.

## Phase 5. Clean the Data Before Clustering

### Goal

Create a defensible input matrix.

### Exact preprocessing steps

1. Remove images with failed ROI extraction.
2. Remove images with failed segmentation.
3. Keep a flag for zero-particle images instead of automatically deleting them.
4. Remove features with near-zero variance.
5. Winsorize extreme outliers if needed, for example at the 1st and 99th percentiles.
6. Apply `log1p` to strongly skewed count and size variables.
7. Standardize all clustering features with a robust scaler or z-score scaling.
8. Save the preprocessed matrix separately from the raw feature table.

## Phase 6. Reduce Redundancy and Select Variables Properly

### This is the correct replacement for p-value-based selection

Use the following selection strategy:

1. Domain filter:
   keep only features that have a clear morphological interpretation.
2. Variance filter:
   remove near-constant features.
3. Correlation filter:
   compute a Spearman correlation matrix on the candidate features.
4. Redundancy reduction:
   if two features have absolute correlation greater than or equal to 0.90, keep only one.
5. Family balance:
   avoid keeping too many summaries from the same attribute family.
6. PCA:
   apply PCA after feature filtering and scaling.

### Exact rule for redundancy inside each attribute family

For each of these families:

- area
- solidity
- aspect ratio
- feret diameter
- equivalent diameter
- circularity
- intensity

Keep at most:

- one central tendency measure
- one dispersion measure
- one upper-tail measure

A strong default is:

- central tendency: `median`
- dispersion: `IQR`
- upper tail: `p90`

That rule is simple, defensible, and much better than blindly keeping every statistic.

## Phase 7. Perform PCA Correctly

### Goal

Use PCA as a dimensionality-reduction and visualization tool, not as a magical black box.

### Exact procedure

1. Fit PCA on the standardized selected features.
2. Inspect the scree plot.
3. Retain the smallest number of principal components that explains at least 85 percent of the variance.
4. Also report the 2D PCA projection for visualization.
5. Interpret the loadings of the first principal components.

### Important note

You should cluster mainly on the retained PCA scores, but also compare against clustering on the selected standardized features directly. That comparison is useful in the thesis.

## Phase 8. Run a Proper Clustering Benchmark

Do not test only one algorithm. Use a benchmark.

### Algorithms to include

#### 1. K-means

Purpose:

- simple baseline
- easy to interpret

Settings:

- test `k = 2, 3, 4, 5, 6, 7, 8`
- use many random initializations, for example `n_init = 50` or more

#### 2. Agglomerative clustering with Ward linkage

Purpose:

- hierarchical structure
- good comparison against K-means

Settings:

- test `k = 2, 3, 4, 5, 6, 7, 8`

#### 3. Gaussian Mixture Models

Purpose:

- probabilistic clustering
- directly aligned with your professor's "probabilistic models" comment

Settings:

- test `k = 2, 3, 4, 5, 6, 7, 8`
- compare covariance types such as `full` and `diag`
- use BIC and AIC as additional criteria

#### 4. Fuzzy C-means

Purpose:

- fuzzy clustering
- directly aligned with your professor's "fuzzy models" comment

Settings:

- test `k = 2, 3, 4, 5, 6, 7, 8`
- use a fuzzifier around `m = 2.0`
- report fuzzy partition coefficient and partition entropy

#### 5. HDBSCAN

Purpose:

- robustness check
- ability to detect noise and non-spherical structure

Use HDBSCAN as a secondary robustness experiment, not necessarily as the main model.

## Phase 9. Select the Final Clustering Solution Rigorously

### Metrics to compute for every candidate solution

- Silhouette score
- Calinski-Harabasz index
- Davies-Bouldin index
- cluster size distribution
- visual separation in PCA space
- interpretability of cluster profiles

### Additional metrics by method

- GMM: BIC and AIC
- Fuzzy C-means: fuzzy partition coefficient and partition entropy

### Stability analysis

This is very important for a thesis.

For each candidate clustering solution:

1. Repeat the clustering 30 times with different random seeds.
2. Perform bootstrap resampling with 80 percent of the images.
3. Compute a stability score such as adjusted Rand index between repeated solutions.

With a dataset of about 2,500 images, also add one confirmation analysis:

4. develop the pipeline on the pilot subset, then confirm that the final chosen clustering behavior remains consistent on the full retained dataset

### Final model selection rule

Choose the final clustering solution only if it satisfies all of these:

1. good internal quality metrics
2. good stability
3. no tiny meaningless clusters, unless the method explicitly models noise
4. clusters are interpretable by morphology and representative images

Do not choose the final model using a single metric alone.

## Phase 10. Explain the Clusters Properly

This part is essential. Clustering without explanation is weak for a thesis.

### Required explainability outputs

For the final clustering solution, produce:

1. a cluster profile table with means or medians of the original features
2. a heatmap of standardized feature values by cluster
3. representative images for each cluster
4. cluster medoids or nearest-to-centroid examples
5. PCA plots colored by cluster
6. boxplots for the most discriminative features

### Recommended advanced explainability

Train a supervised surrogate model to predict cluster labels from the original features:

- Random Forest
- XGBoost
- multinomial logistic regression

Then use feature importance or SHAP values to explain which features drive each cluster.

This is a strong thesis contribution because it turns unsupervised clusters into interpretable decision patterns.

### Statistical comparison after clustering

At this stage, p-values are acceptable for post hoc comparisons between discovered clusters.

Use:

- Kruskal-Wallis for non-normal feature distributions
- ANOVA only if assumptions are satisfied
- multiple-comparison correction such as Benjamini-Hochberg

This is where inferential statistics belongs, not in the feature-selection step for clustering.

## Phase 11. Build a Taxonomy of Likely Contaminant or Source Categories

This is where you connect morphology to environmental meaning.

### Use a taxonomy, not direct chemical labels

Create a source-category taxonomy such as:

- combustion-related
- traffic-related
- road dust or resuspension
- construction or mineral dust
- biological material
- fibrous material
- industrial particulate
- mixed or unknown

These are safer and more defensible than claiming exact contaminants from morphology alone.

## Phase 12. Relate Clusters to External Environmental Context

This is the part where you connect clusters to possible contaminants or source environments.

### 12.1 Use your own project data first

Your repository already contains official-station related data and air-quality context scripts. Use those as the primary external reference whenever possible.

### 12.2 Use Google APIs as contextual enrichment, not ground-truth chemistry

If you use Google services, use them in this exact way:

#### Google Maps Platform Air Quality API

Use it to retrieve, for the sensor location and the sampling date:

- hourly air-quality context
- PM2.5 context
- PM10 context
- AQI context
- other pollutant context if available

Use it only as contextual information around the place and time of sampling.

Important limitation:

- the current Google Maps Platform Air Quality API supports hourly history only for a limited recent window of up to 30 days, so if your samples are older than that window, use your official-station data as the main historical reference and keep the Air Quality API only for recent samples or live demonstrations.

When you write the thesis, use the official product name `Google Maps Platform Air Quality API`, not just "Google Air."

#### Google Maps Platform Places API (New)

Use Nearby Search or Text Search to retrieve contextual place types around the sensor location, for example:

- transport hubs
- gas stations
- industrial areas
- construction-related places
- parks or green areas
- ports or marine contexts

Do not use Places API to estimate road geometry or exact road distance. For that, use a road-network or GIS source if you include road-proximity variables.

Do not use the legacy Places API. If you use Google Places, use Places API (New).

### 12.3 Context variables to engineer

For each image or sensor location, create variables such as:

- nearest major road distance if you have a road-network source
- number of traffic-related places within 250 m, 500 m, and 1 km
- number of construction-related places within 500 m and 1 km
- number of industrial-related places within 1 km
- nearby green-area indicator
- official-station PM2.5
- official-station PM10
- Air Quality API AQI
- Air Quality API pollutant context

### 12.4 Statistical association analysis

Then test whether clusters differ in contextual variables.

Use:

- Kruskal-Wallis for continuous contextual variables
- chi-square tests for categorical variables
- multinomial logistic regression or tree-based models to predict cluster membership from contextual variables

Interpret the results as:

- association
- enrichment
- consistency

Never interpret them as direct proof of contaminant composition.

## Phase 13. Exact Experiment Matrix You Should Run

Run at least these experiments:

### E1. Segmentation baseline validation

- classical pipeline only
- run first on the pilot subset, then confirm on the full retained dataset

### E2. Feature-set comparison

- core feature set
- extended feature set
- compare first on the pilot subset to save time, then rerun the selected setup on the full retained dataset

### E3. Redundancy reduction comparison

- selected features without PCA
- selected features with PCA

### E4. Clustering benchmark

- K-means
- Ward hierarchical
- GMM
- Fuzzy C-means
- HDBSCAN

For the full dataset, save cluster assignments, cluster sizes, and representative images for every tested final candidate model.

### E5. Explainability analysis

- cluster profiles
- medoid images
- surrogate model explainability

### E6. Contextual association analysis

- clusters versus official station variables
- clusters versus Air Quality API variables
- clusters versus Google Places context variables

### E7. Optional segmentation-model experiment

- only if classical segmentation quality is insufficient

## Phase 14. Evaluation Criteria for the Whole Thesis

Your AI part will be strong if, by the end, you can show:

1. the image-processing pipeline is reproducible
2. the feature set is justified and not redundant
3. the clustering is benchmarked across several methods
4. the final clustering is stable
5. the clusters are visually and statistically interpretable
6. the contextual association analysis is careful and non-overclaimed

## Phase 15. Figures and Tables You Must Include in the Thesis

### Mandatory figures

1. end-to-end methodology diagram
2. ROI extraction and segmentation examples
3. correlation heatmap of candidate features
4. PCA scree plot
5. PCA scatter plot colored by clusters
6. silhouette or metric comparison across methods and `k`
7. representative images per cluster
8. cluster profile heatmap
9. contextual association plots

### Mandatory tables

1. dataset summary
2. feature dictionary
3. segmentation validation summary
4. clustering benchmark results
5. final cluster descriptions
6. contextual association results

## Phase 16. Recommended Thesis Chapter Structure

Use this structure:

1. Introduction
2. Background
3. System Overview
4. Image Processing and Dataset Construction
5. Feature Engineering and Dimensionality Reduction
6. Clustering Methodology
7. Cluster Explainability
8. Environmental Context and Source Association
9. Results
10. Limitations and Future Work
11. Conclusions

## Phase 17. Limitations You Should State Explicitly

Include these limitations clearly:

- image morphology is not direct chemical composition
- pixel-based measures may not be physically calibrated
- contextual APIs provide environmental context, not laboratory validation
- unsupervised clusters depend on image quality and segmentation quality
- cluster meaning can be partly ambiguous

Stating these limitations improves the thesis rather than weakening it.

## Phase 18. Exact Order of Work

If you want the best execution order, do this:

1. Draw a pilot subset of about 300 to 500 images that is diverse in date, location, and visible particle load.
2. Validate and document the current ROI and segmentation pipeline on that pilot subset.
3. Export per-particle features from the current analysis code.
4. Build `images_metadata`, `particles`, and `image_features`.
5. Run structured manual QC and segmentation validation on the pilot subset.
6. Define the core and extended feature sets.
7. Clean, transform, scale, and reduce redundancy.
8. Run PCA.
9. Benchmark K-means, Ward, GMM, Fuzzy C-means, and HDBSCAN on the pilot subset.
10. Freeze the preprocessing and modeling protocol.
11. Execute the final pipeline on the full retained dataset.
12. Select the final model using quality plus stability.
13. Build explainability outputs for the final clustering.
14. Engineer contextual variables from official data and Google APIs.
15. Run cluster-context association analysis.
16. Write the results with cautious interpretation.

## Phase 19. Recommended Implementation Structure in This Repository

To keep the work organized, use this project structure:

1. Extend [`analysis-service/src/pipeline.py`](/Users/ibon-personal/Desktop/INFOR/analysis-service/src/pipeline.py) only for baseline-compatible analysis outputs.
2. Create a dedicated feature-extraction module, for example `analysis-service/src/feature_extraction.py`.
3. Create a dataset-export script that writes:
   - `images_metadata.csv`
   - `particles.csv`
   - `image_features.csv`
4. Keep clustering and explainability experiments in a dedicated analysis folder such as `analysis/` or `notebooks/`.
5. Process the 2,500-image dataset in batches and save per-batch logs for failures, QC flags, and segmentation errors.
6. Save every final experiment configuration and random seed so the results are reproducible.

## Phase 20. Final Recommended Positioning of the Contribution

Your strongest thesis contribution is not just "I clustered images."

It should be:

1. a reproducible pipeline for converting DIY sensor images into structured morphological data
2. an unsupervised taxonomy of sensor-image patterns
3. an explainability layer that makes the clusters understandable
4. a contextual environmental association layer that links image morphology to likely pollutant-source scenarios

## Final Recommendation

If you want this thesis to be as complete as possible, structure the AI part around four pillars:

1. robust feature extraction
2. rigorous clustering benchmark
3. explainability
4. cautious environmental association

That is much stronger than doing only PCA plus K-means on a large set of raw summary statistics.
