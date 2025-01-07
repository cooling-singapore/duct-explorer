# DUCT Explorer
This repository is part of the Cooling Singapore 2.0 project which ended in August 2024. 
The repository is deprecated and will no longer be maintained. For further information please contact 
*contact-dtlab@sec.ethz.ch.*

## Directory Structure
DUCT Explorer is organized into two main components, reflecting its directory structure:

#### DUCT Explorer Server
Corresponds to the **server** folder, housing all backend services and configurations.

#### DUCT Explorer Client
Corresponds to the **client** folder, containing all frontend resources for interacting with the server.

## Overview
DUCT Explorer provides explorer services, which depend on SaaS Middleware services. This documentation will guide you through setting up the DUCT Explorer Server, along with testing and administering its components.

## Prerequisites
Ensure that the SaaS Middleware services are operational before initiating DUCT Explorer.
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
```shell
pip install .
```
## Usage
The DUCT Explorer can be used via a Command Line Interface (CLI) with this command once it is installed:
```shell
explorer
```

### Running Explorer
When initializing, the user must provide the following:

- Datastore path: Location where all data will be stored
- Keystore path: Location of the keystore
- Temporary Directory path: Directory used for storing intermediate files
- Keystore ID: Identity of the keystore that the node will utilize
- Userstore path: Location where user data will be stored
- BDP Directory: Directory containing the base data packages
- Secret Key: Key used to secure passwords

```shell
explorer --datastore $DATASTORE_PATH --keystore $KEYSTORE_PATH --temp-dir $TEMP_DIRECTORY_PATH --keystore-id '<put_id_here>' --password '<put_password_here>' --log-level INFO --log-path False service --userstore $USERSTORE_PATH --bdp_directory $BDP_PATH --secret_key '<put_secret_key_here>'
```

### Creating Explorer Users
To initialize and manage explorer users, use the following commands:

```shell
# Initialize explorer user
explorer user init --userstore ${USERSTORE}

# Create an explorer user
explorer  user create --userstore ${USERSTORE}

? Enter address of the SaaS node REST service: 127.0.0.1:5001
? Enter the login: foo.bar@email.com
? Enter the name: foo bar
? Enter the password [leave empty to generate]: ****
User account created: foo.bar@email.com
Publish identity vlaq9jk9ojioi69qk5edqdmdnvejmdqfpvb6e5812si1mahsggwbfh9i61ba4ywa of user foo.bar@email.com to node at 127.0.0.1:5001

The example above shows the identity created with ID `vlaq9jk9ojioi69qk5edqdmdnvejmdqfpvb6e5812si1mahsggwbfh9i61ba4ywa`.

# List explorer users
explorer user list --userstore ${USERSTORE}

# Remove an explorer user
explorer user remove --userstore ${USERSTORE} --login '<put_user_login_here>'
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
