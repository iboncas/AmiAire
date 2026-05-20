# Final Discussion

## Purpose

This document summarizes the final interpretation of the two clustering iterations and explains how the results should be discussed in the absence of ground-truth source labels.

The main conclusion is that the clusters should be interpreted as **stable data-driven particle phenotypes**, not as confirmed source categories. The taxonomy layer provides cautious source hypotheses based mainly on morphology, while the context module provides external environmental associations that help interpret where and when those phenotypes appear.

## Final Models

| Item | Iteration 1 | Iteration 2 |
| --- | --- | --- |
| Role | Morphology and intensity baseline | Enriched morphology, color, temporal, and spatial-context model |
| Final candidate | `pca_scores__kmeans__k-4` | `pca_scores__kmeans__k-3` |
| Rows used | `2565` | `2578` |
| Selected features before PCA | `22` | `46` numeric PCA inputs |
| PCA components retained | `7` | `17` |
| Candidate count | `72` | `72` |
| Eligible final candidates | `21` | `7` |
| Silhouette score | `0.3710` | `0.2382` |
| Calinski-Harabasz score | `879.24` | `378.40` |
| Davies-Bouldin score | `1.0815` | `1.8862` |
| Repeat ARI | `1.0000` | `0.9991` |
| Bootstrap ARI | `0.9929` | `0.9886` |
| Smallest cluster fraction | `0.1236` | `0.1424` |

Iteration 1 gives a cleaner morphology-driven separation, with stronger internal clustering metrics. Iteration 2 gives a richer but less sharply separated structure, because it adds color, temporal, and spatial-context variables. Therefore, iteration 2 should not be presented as simply "better" than iteration 1. It is better understood as a more context-aware model that trades some geometric separation for broader interpretability.

## Cluster Interpretations

### Iteration 1

| Cluster | Fraction | Direct profile | Taxonomy suggestion | Confidence |
| --- | ---: | --- | --- | --- |
| `1` | `52.0%` | Heterogeneous circularity, less circular particles | `fibrous_synthetic_materials` | moderate |
| `2` | `21.4%` | Smaller particle bodies, shorter upper-tail extent, compact non-elongated shapes | `combustion_related` | high |
| `3` | `12.4%` | Very elongated particles, less circular particles, darker deposits | `fibrous_synthetic_materials` | high |
| `4` | `14.2%` | Larger bodies, round compact particles, heterogeneous solidity, broad orientation spread | `mixed_unknown` | high |

Iteration 1 is useful as the baseline because the source hypotheses are driven mainly by morphology and intensity. In this run, the taxonomy layer separates a combustion-like compact/smaller-particle group from fibrous-like elongated groups and a larger mixed/unknown group.

### Iteration 2

| Cluster | Fraction | Direct profile | Taxonomy suggestion | Confidence |
| --- | ---: | --- | --- | --- |
| `1` | `68.8%` | Heterogeneous circularity, less circular particles | `fibrous_synthetic_materials` | moderate |
| `2` | `14.2%` | Very elongated tail cases, heterogeneous circularity, less circular particles, darker deposits | `fibrous_synthetic_materials` | high |
| `3` | `17.0%` | Larger particle bodies, round compact particles, high orientation dispersion | `mixed_unknown` | moderate |

Iteration 2 reduces the final structure from four clusters to three. The previous combustion-like group from iteration 1 is no longer retained as a separate final cluster in the enriched solution. This does not mean that combustion-related particles are absent. It means that once color, temporal, and spatial-context variables are included, the most stable final partition groups the data differently.

## How The Taxonomy Is Done

The taxonomy is not a supervised classifier and it is not trained from confirmed labels. It is a heuristic interpretation layer applied after clustering.

The process is:

1. Compute the standardized profile of each cluster.
2. Compare that profile with predefined morphology-based signatures.
3. Score each possible category by multiplying the cluster z-scores by category-specific weights.
4. Select the strongest category only when the score and score gap are large enough.
5. Treat the result as a source hypothesis, not as source confirmation.

For example, a fibrous-like label is mainly supported by higher aspect ratio, higher eccentricity, longer Feret extent, and lower circularity. A combustion-like label is mainly supported by smaller and more compact particle profiles. A mixed/unknown label is used when heterogeneity is high or when no single source-like morphology dominates clearly.

Color, PM values, season, station, and Places variables should not be interpreted as direct source identifiers. They can support or contextualize a hypothesis, but they do not prove it. For example, a darker cluster is not automatically combustion-related; darkness only describes the optical appearance of the deposit. The source interpretation still depends primarily on the morphology profile and would require expert labeling or chemical analysis for confirmation.

## Validation Without Ground Truth

Because there are no manually labeled or chemically confirmed source labels, the project cannot report supervised accuracy. The validation is instead based on complementary unsupervised and external checks.

| Validation type | What it checks | Interpretation |
| --- | --- | --- |
| Internal metrics | Compactness and separation of clusters | Useful for comparing candidates, but not proof of real sources |
| Repeat-fit stability | Whether the same algorithm returns similar clusters across runs | High ARI suggests the result is not driven by random initialization |
| Bootstrap stability | Whether clusters survive data perturbation | High ARI suggests robustness to sampling variation |
| Cluster profiles | Whether clusters have coherent feature signatures | Supports interpretability |
| Representative examples | Whether real images match the numerical profile | Closest practical substitute for expert visual validation |
| Alternative-solution agreement | Whether nearby models give similar partitions | Helps show whether the selected structure is isolated or part of a stable family |
| Context associations | Whether clusters relate to season, PM, station, or spatial context | Provides external plausibility, not ground truth |

The nearest approximation to ground truth in this project is therefore a combination of expert visual review, representative-image inspection, contextual association, and consistency with known morphology-source expectations. This is weaker than chemical confirmation, but still useful for an exploratory clustering study.

## Role Of The Context Module

The context module answers a different question from the clustering and taxonomy modules.

| Module | Main question |
| --- | --- |
| Clustering | What groups exist in the image-derived feature space? |
| Explainability | Which measured variables define those groups? |
| Taxonomy | Which source hypotheses are morphologically compatible with those groups? |
| Context | Where, when, and under which environmental conditions do those groups appear? |

The context module gives extra information by testing whether cluster membership is associated with external variables such as official station, season, PM10, PM2.5, station distance, and location-related context.

In iteration 2, the strongest categorical context association is `official_station_id`, with Cramer's V around `0.504`. The context-only prediction models reach balanced accuracy around `0.651` for random forest and `0.608` for logistic regression. This means context explains a meaningful part of the clustering structure, but not all of it.

This is useful in two ways. First, it supports environmental interpretation because the clusters are not completely disconnected from external conditions. Second, it warns about possible confounding: some structure may reflect where and when samples were collected, not only particle morphology.

## Recommended Final Narrative

The final writeup should present iteration 1 and iteration 2 as complementary rather than competing.

Iteration 1 establishes a robust morphology-based baseline. It finds four stable clusters with stronger internal separation, including fibrous-like groups, one combustion-like group, and one mixed/unknown group.

Iteration 2 extends the feature space with color, temporal, and spatial-context variables. It finds a stable three-cluster solution. This enriched solution has lower internal separation than iteration 1, but it captures additional color and contextual structure. In particular, color variables contribute to the darker and more elongated cluster, while station and seasonal context provide external interpretive information.

The safest final conclusion is:

> The clustering identifies stable and interpretable particle phenotypes. The taxonomy layer suggests possible source-related interpretations based on morphology, while contextual variables provide external plausibility and reveal environmental associations. However, because no ground-truth source labels or chemical validation are available, the clusters should be treated as exploratory morphological-contextual groups rather than definitive source categories.

## Limitations

- There is no chemical confirmation or expert-labeled ground truth.
- Taxonomy labels are heuristic source hypotheses, not confirmed identities.
- Context variables may capture sampling design, station effects, geography, or seasonality rather than source mechanisms alone.
- Color can describe deposit appearance, but it cannot identify sources by itself.
- Iteration 2 has lower internal cluster separation than iteration 1, even though it remains stable.
- Google Places features are useful for interpretation but are indirect proxies and may be noisy.
- The final clusters may represent continuous variation summarized into discrete groups.

## Recommended Final Checks

Before finalizing the thesis discussion, the remaining checks should be:

1. Inspect representative and borderline images for each final cluster.
2. Confirm that the visual examples match the numerical cluster profiles.
3. Keep iteration 1 as the morphology-only baseline and iteration 2 as the enriched context-aware model.
4. Avoid writing that any cluster is definitively fibrous, combustion-related, or mechanical.
5. Use language such as "compatible with", "suggestive of", "fibrous-like", "combustion-like", and "source hypothesis".

