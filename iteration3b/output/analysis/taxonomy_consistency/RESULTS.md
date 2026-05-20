# TEMP Taxonomy Consistency Check

Iteration: `iteration3b`

This compares each image row's direct TEMP taxonomy result against the final cluster-level taxonomy label.

Important note:
This is **not** ground truth. Both sides come from the same heuristic taxonomy family, so this should be interpreted as an internal consistency audit.

## Overall

- Rows compared: `2082`
- Rows skipped: `0`
- Direct TEMP top-category agreement with cluster label: `54.2%`
- Mean TEMP percentage assigned to the cluster's chosen category: `40.20`
- Mean TEMP percentage of each row's own top category: `52.68`

## Cluster Summary

| Cluster | Cluster taxonomy | Agreement | Dominant TEMP category | Mean TEMP support for cluster label |
| --- | --- | ---: | --- | ---: |
| `1` | `combustion_related` | `97.5%` | `combustion_related` | `84.38` |
| `2` | `fibrous_synthetic_materials` | `38.8%` | `fibrous_synthetic_materials` | `25.47` |
| `3` | `mixed_unknown` | `65.2%` | `mixed_unknown` | `41.74` |
| `4` | `fibrous_synthetic_materials` | `35.8%` | `fibrous_synthetic_materials` | `29.41` |

## Files

- `row_level_comparison.csv`
- `cluster_summary.csv`
- `cluster_vs_temp_confusion.csv`
- `summary.json`
