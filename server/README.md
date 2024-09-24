# Duct-Servers
This repository is part of the Cooling Singapore 2.0 project which ended in August 2024. 
The repository is deprecated and will no longer be maintained. For further information please contact 
*contact-dtlab@sec.ethz.ch.*

## Overview
Duct-servers provides explorer services, which are dependent on saas-middleware services. This documentation guides you through the setup, testing, and administration of these services.

## Prerequisites
Ensure that the saas-middleware services are operational before initiating duct-explorer.
- Python 3.10 (does not work with newer Python versions)
- Linux or MacOS Operating System (not tested with Windows)

## Setup Instructions
## Install

Clone the repository:
```shell
git clone https://github.com/cooling-singapore/duct-explorer
```

Create and activate the virtual environment:
```shell
python3.10 -m venv venv-explorer
source venv-explorer/bin/activate
```

Install the required python packages:

```shell
pip install -r requirements.txt
```


### First time setup
Upload bdp-files to /mnt/duct with explorer pod.
```shell
# Get running pod id of explorer
kubectl get pods

# Copy bdp-files to explorer pod
kubectl cp /path/to/bdp-files <explorer-pod>:/mnt/duct/bdp-files
```

Interactive shell with explorer pod
```shell
# SSH into explorer pod
kubectl exec -it <explorer pod> -- sh

# cd into bdp-files
cd bdp-files

# Execute command
explorer --keystore /mnt/duct/keystores --keystore-id cz45gfv9ja90ilcndo3sxo9dc3bnm69ge9piqclu5a2lwp6z47jpyakr2dmwshxj --password test duct bdp create --bdp_directory /mnt/duct/bdps building-footprints city-admin-zones land-mask land-use-zoning leaf-area-index vegetation-land-use lcz-map vegfra-map traffic_baseline_SH.geojson traffic_ev100_SH.geojson power_baseline_SH_20160201.geojson power_baseline_LH_20160201.geojson power_ev100_SH_20160201.geojson power_ev100_LH_20160201.geojson 
```

### Creating Explorer Users
To initialize and manage explorer users, use the following commands:

```shell
# Initialize explorer user
explorer user init --userstore ${USERSTORE}

# Create an explorer user
explorer --keystore ${ENV_HOME}/keystores --password `cat ${ENV_HOME}/password.apps` user create --userstore ${USERSTORE} --node_address `cat ${ENV_HOME}/node_address`

# List explorer users
explorer user list --userstore ${USERSTORE}

# Remove an explorer user
explorer user remove --userstore ${USERSTORE}
```

### Create Base Data Packages (BDPs)

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
