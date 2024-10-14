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


To create a BDP, use the following command:
$LOCATION_OF_BDP_FILES refers to a directory that contains all the relevant data object content files needed to create a BDP.

```shell
# Export relevant environment
export ENV_HOME=$DEV
export LOCATION_OF_BDP_FILES=$HOME/{BDPNAME}

# Activate virtual environment
source ${ENV_HOME}/venv-servers/bin/activate

cd $LOCATION_OF_BDP_FILES

# Create BDP
explorer --keystore ${ENV_HOME}/keystore --keystore-id `cat ${ENV_HOME}/keystore_id.explorer` --password `cat ${ENV_HOME}/password.apps` duct bdp create --bdp_directory ${ENV_HOME}/bdps city-admin-areas population-data network-data se-data scenario-data-from_scene
```
BDP information:

| City Name     | Package Name (Example) | Bounding Box                         | Dimensions | Timezone         | 
|:--------------|:-----------------------|:-------------------------------------|:-----------|:-----------------|
| Singapore     | Public (v24)           | 103.55161,1.53428,104.14966,1.19921  | 211,130    | Asia/Singapore   |

### Remove Base Data Package (BDP)
```shell
export ENV_HOME=$DEV
source ${ENV_HOME}/venv-servers/bin/activate

# Remove BDP
explorer --keystore ${ENV_HOME}/keystore --keystore-id `cat ${ENV_HOME}/keystore_id.explorer` --password `cat ${ENV_HOME}/password.apps` duct bdp remove --bdp_directory ${ENV_HOME}/bdps
```

