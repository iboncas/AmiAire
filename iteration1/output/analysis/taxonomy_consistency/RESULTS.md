# TEMP Taxonomy Consistency Check

Iteration: `iteration1`

This compares each image row's direct TEMP taxonomy result against the final cluster-level taxonomy label.

Important note:
This is **not** ground truth. Both sides come from the same heuristic taxonomy family, so this should be interpreted as an internal consistency audit.

## Overall

- Rows compared: `2565`
- Rows skipped: `0`
- Direct TEMP top-category agreement with cluster label: `55.6%`
- Mean TEMP percentage assigned to the cluster's chosen category: `41.17`
- Mean TEMP percentage of each row's own top category: `53.80`

## Cluster Summary

| Cluster | Cluster taxonomy | Agreement | Dominant TEMP category | Mean TEMP support for cluster label |
| --- | --- | ---: | --- | ---: |
| `1` | `fibrous_synthetic_materials` | `36.8%` | `fibrous_synthetic_materials` | `24.50` |
| `2` | `combustion_related` | `96.0%` | `combustion_related` | `83.23` |
| `3` | `fibrous_synthetic_materials` | `53.3%` | `fibrous_synthetic_materials` | `34.63` |
| `4` | `mixed_unknown` | `65.8%` | `mixed_unknown` | `44.45` |

## Files

- `row_level_comparison.csv`
- `cluster_summary.csv`
- `cluster_vs_temp_confusion.csv`
- `summary.json`
