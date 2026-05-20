# TEMP Taxonomy Consistency Check

Iteration: `iteration2`

This compares each image row's direct TEMP taxonomy result against the final cluster-level taxonomy label.

Important note:
This is **not** ground truth. Both sides come from the same heuristic taxonomy family, so this should be interpreted as an internal consistency audit.

## Overall

- Rows compared: `2578`
- Rows skipped: `0`
- Direct TEMP top-category agreement with cluster label: `35.8%`
- Mean TEMP percentage assigned to the cluster's chosen category: `24.12`
- Mean TEMP percentage of each row's own top category: `52.76`

## Cluster Summary

| Cluster | Cluster taxonomy | Agreement | Dominant TEMP category | Mean TEMP support for cluster label |
| --- | --- | ---: | --- | ---: |
| `1` | `fibrous_synthetic_materials` | `28.5%` | `combustion_related` | `19.65` |
| `2` | `fibrous_synthetic_materials` | `49.3%` | `fibrous_synthetic_materials` | `32.22` |
| `3` | `mixed_unknown` | `54.1%` | `mixed_unknown` | `35.40` |

## Files

- `row_level_comparison.csv`
- `cluster_summary.csv`
- `cluster_vs_temp_confusion.csv`
- `summary.json`
