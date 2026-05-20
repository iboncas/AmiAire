# Implementation Summary

This project now has a complete analysis pipeline from feature extraction to clustering, explainability, taxonomy, and contextual association.

## Core Results

| Item | Value |
| --- | --- |
| Images used | `2565` |
| Selected features before PCA | `22` |
| PCA retained components | `7` |
| Variance threshold | `0.85` |
| Final selected model | `pca_scores__kmeans__k-4` |
| Benchmarked candidates | `72` |
| Eligible final candidates | `21` |

## Variables Used for Clustering Before PCA

These were the `22` quantitative variables kept in the final feature matrix before dimensionality reduction:

| Variable group | Variables |
| --- | --- |
| Global image descriptors | `num_particles`, `mean_pixel_intensity`, `orientation_entropy`, `circular_variance` |
| Area descriptors | `area_median`, `area_iqr` |
| Solidity descriptors | `solidity_median`, `solidity_iqr`, `solidity_p90` |
| Aspect-ratio descriptors | `aspect_ratio_median`, `aspect_ratio_iqr`, `aspect_ratio_p90` |
| Feret descriptors | `feret_iqr`, `feret_p90` |
| Eccentricity descriptors | `eccentricity_iqr`, `eccentricity_p90` |
| Circularity descriptors | `circularity_median`, `circularity_iqr`, `circularity_p90` |
| Particle-intensity descriptors | `mean_intensity_median`, `mean_intensity_iqr`, `mean_intensity_p90` |

## Final Model Metrics

| Metric | Value |
| --- | --- |
| Silhouette score | `0.3710` |
| Calinski-Harabasz score | `879.24` |
| Davies-Bouldin score | `1.0815` |
| Repeat ARI | `1.0000` |
| Bootstrap ARI | `0.9929` |

![Selection tradeoff plot](output/analysis/selection/selection_tradeoff_plot.png)

This figure shows why the `k=4` K-means solution was retained: it combines strong clustering quality with very high stability.

## Cluster Summary

| Cluster | Count | Fraction | Mean silhouette | Main interpretation |
| --- | --- | --- | --- | --- |
| `1` | `1335` | `0.5205` | `0.4873` | Less circular, heterogeneous particles |
| `2` | `550` | `0.2144` | `0.3243` | Smaller and more compact particles |
| `3` | `317` | `0.1236` | `0.2317` | More elongated and darker deposits |
| `4` | `363` | `0.1415` | `0.1357` | Larger particles with broad orientation spread |

| Top discriminative features |
| --- |
| `aspect_ratio_median`, `area_median`, `mean_pixel_intensity`, `circularity_iqr`, `area_iqr` |

![Cluster profile heatmap](output/analysis/explainability/cluster_profile_heatmap.png)

This heatmap summarizes the main differences between clusters across the most relevant morphology features.

## What the Terms Mean

| Term | Meaning |
| --- | --- |
| Benchmarked candidates | All clustering solutions tested during model comparison. A candidate is one concrete combination of method, feature space, and cluster setting, for example `pca_scores__kmeans__k-4`. |
| Eligible final candidates | The subset of benchmarked candidates that passed the minimum quality and stability rules for final consideration. In this project that included thresholds on repeat ARI, bootstrap ARI, minimum cluster size, and maximum noise fraction. |
| Surrogate models | Supervised models trained after clustering to predict the discovered cluster labels from the saved features. They do not create the clusters; they check whether the clusters can be recovered and explained from the available variables. |

## Interpretation Layers

| Area | Main result |
| --- | --- |
| Taxonomy | Cluster `2` is most consistent with `combustion_related`; clusters `1` and `3` align more with `fibrous_material`; cluster `4` remains `mixed_or_unknown`. |
| Explainability | Surrogate models recover cluster membership well: random forest `0.9710 ± 0.0060`, logistic `0.9908 ± 0.0032`. |
| Context | Context-only prediction is weaker: random forest `0.6491 ± 0.0262`, logistic `0.5424 ± 0.0301`. |

Surrogate models are useful because they answer a practical question: if the clusters are real structure in feature space, can another model learn those labels from the measured variables? Here the answer is yes for morphology features, since both surrogate models reached very high balanced accuracy. That supports interpretability. It is a check on recoverability, not proof that the clusters are the only possible grouping.

These results support a cautious conclusion: the clusters are morphologically meaningful, interpretable, and associated with environmental context, but not fully explained by context alone.
