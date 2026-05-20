# Google Places Enrichment

This note explains how to add Google Places context to iteration 2 without changing the previous iteration.

## Goal

Enrich each unique sensor location with nearby-place context inside a `500m` radius, save the results, and then join the derived variables into the iteration-2 dataset.

The key design rule is:

- query only unique sensor locations
- cache the responses
- never query the same location twice unless you intentionally refresh the cache

## Why This Is Feasible

If you only query unique sensor coordinates, the total number of requests is usually much smaller than the number of images.

That means the workflow is practical if:

- the number of distinct sensor locations is below the free monthly quota you plan to use
- you persist the responses locally
- you avoid unnecessary re-runs

## Recommended Architecture

Use a separate enrichment script, for example:

- `iteration2/google_places_enrichment.py`

Do not put Google Places logic inside the image-analysis service.

The clean pipeline is:

1. Build or load the iteration-2 dataset with sensor coordinates.
2. Extract unique locations.
3. Query Google Places once per unique location.
4. Save the raw responses to a cache file.
5. Convert raw responses into a small set of air-quality proxy variables.
6. Join those variables back into `iteration2/build_dataset.py`.

## Input

The enrichment script only needs:

- `sensor_id`
- `latitude`
- `longitude`

Best source:

- `iteration2/output/dataset/images_metadata.csv`

Or directly from the sensors endpoint before dataset export.

## Query Strategy

Use `Nearby Search Pro` with:

- radius: `500`
- one request per unique location

Only keep categories relevant to air quality interpretation.

Recommended groups:

- `transit`
- `park`
- `gas_station`
- `parking`
- `industrial`
- `construction`
- `major_road_proxy`

## What To Save

Save two layers:

### 1. Raw cache

Example:

- `iteration2/output/dataset/places_cache.json`

Each entry should contain:

- `sensor_id`
- `latitude`
- `longitude`
- `queried_at`
- `radius_m`
- raw Google response

### 2. Derived table

Example:

- `iteration2/output/dataset/places_features.csv`

Each row should contain:

- `sensor_id`
- `places_total_within_500m`
- `places_transit_within_500m`
- `places_park_within_500m`
- `places_gas_station_within_500m`
- `places_parking_within_500m`
- `places_industrial_within_500m`
- `places_construction_within_500m`
- `places_major_road_proxy_within_500m`
- `dominant_place_category`
- `place_diversity_entropy`
- `green_vs_traffic_ratio_500m`
- `places_missing_flag`

## Suggested Mapping Logic

Google place types are noisy, so use deterministic grouping rules.

Example grouping:

- `transit`: `transit_station`, `bus_station`, `subway_station`, `train_station`
- `park`: `park`
- `gas_station`: `gas_station`
- `parking`: `parking`
- `industrial`: warehouse, storage, logistics-style proxies if available in returned types
- `construction`: hardware, building-material, contractor-style proxies if available
- `major_road_proxy`: use route-related or traffic-heavy proxies if your result types support them

If a place matches multiple groups, either:

- count it in the most specific group only, or
- document the overlap rule clearly and keep it consistent

## Pagination

Nearby Search can return paginated results.

For your thesis use case, a practical choice is:

- only request the first page unless you have a strong reason to exhaust all pages

Why:

- fewer billable calls
- simpler caching
- more stable behavior

If you do paginate, record it clearly because extra pages may mean extra requests.

## Joining Back Into The Dataset

After generating `places_features.csv`, join it into:

- `iteration2/build_dataset.py`

Recommended join key:

- `sensor_id`

Fallback:

- rounded `(latitude, longitude)` pair

The final enriched dataset can then contain:

- morphology features
- color features
- temporal features
- Places-derived spatial features

## Minimal Implementation Plan

1. Read unique sensor locations from the iteration-2 dataset.
2. Skip all rows already present in `places_cache.json`.
3. Query Google Places for uncached locations only.
4. Save raw responses immediately after each successful request.
5. Build `places_features.csv` from the cache.
6. Update `iteration2/build_dataset.py` to merge `places_features.csv`.

## Practical Safeguards

- add a small sleep between requests
- log successes and failures per sensor
- save incrementally after every request or small batch
- include a `places_missing_flag`
- include a `query_status` column such as `ok`, `failed`, `no_results`

## Example File Layout

- `iteration2/PLACES.md`
- `iteration2/google_places_enrichment.py`
- `iteration2/output/dataset/places_cache.json`
- `iteration2/output/dataset/places_features.csv`

## Recommended Environment Variables

Use an API key from environment variables, not hardcoded values.

Example:

- `GOOGLE_MAPS_API_KEY`

## Example Workflow

```bash
python3 iteration2/build_dataset.py --output-dir iteration2/output/dataset
python3 iteration2/google_places_enrichment.py
python3 iteration2/build_dataset.py --output-dir iteration2/output/dataset
```

The second dataset build would be the one that merges the saved Places-derived features.

## Summary

Yes, this is a practical setup.

The right way to do it is:

- query unique sensor locations only
- cache raw responses
- derive compact air-quality proxy variables
- join them back into the iteration-2 dataset as a separate enrichment layer
