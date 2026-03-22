import geopandas as gpd

# Load shapefile (point to the .shp file)
gdf = gpd.read_file("ES_Estaciones_2001_2024.shp")

# Convert to WGS84 (lat/lon) if needed
gdf = gdf.to_crs(epsg=4326)

# Extract coordinates
gdf["longitude"] = gdf.geometry.x
gdf["latitude"] = gdf.geometry.y

# Save to CSV
gdf[["name", "longitude", "latitude"]].to_csv("stations_coordinates.csv", index=False)