# Base Data Package for DUCT v0.27

## Contents
The BDP for DUCT v0.27 contains the following datasets:
- `building-footprints`: Geometries defining building footprints (including height information). Source: OpenStreetMap
- `city-admin-zones`: Geometries defining the administrative zones of the city. Source: [Master Plan 2019 Subzone Boundary](https://beta.data.gov.sg/datasets/d_8594ae9ff96d0c708bc2af633048edfb/view).
- `vegetation`: Trees only. Source: [Trees.sg and National Parks Board](https://github.com/cheeaun/sgtreesdata)
- `land-use`: Geometries defining the land use. Source: [Master Plan 2019 Land Use Layer](https://beta.data.gov.sg/datasets/d_90d86daa5bfaa371668b84fa5f01424f/view)
- `lcz-baseline`: Local Climate Zone of Singapore (30m resolution). Source: Cooling Singapore.
- `sh-traffic-ev100` and `sh-traffic-baseline`: Traffic anthropogenic heat emission profiles (sensible) for Singapore with and without electric vehicles. Source: Cooling Singapore
- `sh-power-baseline` and `lh-power-baseline`: Power plant anthropogenic heat emission profiles (sensible+latent) for Singapore (assuming no electric vehicles). Source: Cooling Singapore
- `description`: description of the datasets (very similar to the description here but formatted to be used by the Explorer).

Only `building-footprints`, `lcz-baseline`, `sh-traffic-ev100`, `sh-traffic-baseline`, `sh-power-baseline`, `lh-power-baseline` and `description` are provided here in the repository. The remaining datasets should be obtained from their respective sources.

## Creating the Base Data Package

