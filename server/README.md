# DUCT Explorer
This repository is part of the Cooling Singapore 2.0 project which ended in August 2024. 
The repository is deprecated and will no longer be maintained. For further information please contact 
*contact-dtlab@sec.ethz.ch.*

## Directory Structure
DUCT Explorer is organized into two main components, reflecting its directory structure:
- `server`: contains the Python code and related resources for the DUCT Explorer server.
- `client`: contains the JavaScript code and related resources for the DUCT Explorer frontend.

## Overview
DUCT Explorer provides explorer services, which depend on SaaS Middleware services. This documentation will guide you through setting up the DUCT Explorer Server, along with testing and administering its components.

## Prerequisites
- Python 3.10 (does not work with newer Python versions).
- Linux or MacOS Operating System (not tested with Windows).
- SaaS Middleware (see [https://github.com/cooling-singapore/saas-middleware](https://github.com/cooling-singapore/saas-middleware) for further information and installation guide).

## Install
Create and activate the virtual environment:
```shell
python3.10 -m venv venv-explorer
source venv-explorer/bin/activate
```

Clone the repository:
```shell
git clone https://github.com/cooling-singapore/duct-explorer
```

Install the Explorer server application and its dependencies:
```shell
pip install duct-explorer/server
```

## Usage
The Explorer server can be used via a Command Line Interface (CLI) with this command 
once it has been installed:
```shell
explorer
```

The `explorer` CLI tool supports commands to manage user accounts, to manage base data
packages, and to run an Explorer server instance. The following sections describe each
command in detail. 

The examples in the remainder of this section illustrate how to use the `explorer`
CLI interactively. Each command can be parameterised to be used in a non-interactive
manner. Use the `--help` flag to see the arguments for each command.

Note that the examples shown below assume that a SaaS Middleware node is running on 
`127.0.0.1:5001`.

### Managing User Accounts
User accounts consist of two parts: Explorer-specific information stored in the 
"user store" and a SaaS identity associated with the user which is published to the
SaaS backend used by the Explorer upon user account creation (see below). For 
convenience, it is recommended to set an environment variable:
```shell
export USERSTORE=$HOME/.userstore-27
```

#### Initialise User Store
Before creating and managing Explorer users, use the following command to initialise 
the user store:
```shell
explorer user init --userstore ${USERSTORE}
```


#### Create Users Accounts
User accounts can be created interactively by following the prompts using:
```shell
explorer user create --userstore ${USERSTORE}
```

The dialogue looks like this:
```
? Enter address of the SaaS node REST service: 127.0.0.1:5001
? Enter the login: foo.bar@email.com
? Enter the name: foo bar
? Enter the password [leave empty to generate]: ****
User account created: foo.bar@email.com
Publish identity 66q4ll4ng0epuqr5r7ycqx4anoyz3v1unvwysmn8q18ff82cp3zjbtlu4545jn5q of user foo.bar@email.com to node at 127.0.0.1:5001
```

Address of the SaaS node should point at your SaaS node instance. Login, name and 
password are that for the user account to be created. The identity of the user account
is automatically published to the SaaS node instance.

The example above shows the identity of the user account: `66q4ll4ng0epuqr5r7ycqx4anoyz3v1unvwysmn8q18ff82cp3zjbtlu4545jn5q`

#### List Users Accounts
The full list of users can be viewed using the following prompt:
```shell
explorer user list --userstore ${USERSTORE}
```

The command produces output that looks like this:
```
Found 1 users in database at /Users/foobar/.userstore-27:
LOGIN              NAME     DISABLED  KEYSTORE ID
-----              ----     --------  -----------
foo.bar@email.com  foo bar  No        66q4ll4ng0epuqr5r7ycqx4anoyz3v1unvwysmn8q18ff82cp3zjbtlu4545jn5q
```

The example above shows the user account and its identity that was created earlier.

#### Remove User Account
User accounts can be removed interactively by following the prompts using:
```shell
explorer user remove --userstore ${USERSTORE}
```

#### Updating User Accounts
User accounts can be updated interactively by following the prompts using:
```shell
explorer user update --userstore ${USERSTORE}
```

#### Enabling/Disabling User Accounts
User accounts can be enabled/disabled interactively by following the prompts using:
```shell
explorer user enable --userstore ${USERSTORE}
```
or 
```shell
explorer user disable --userstore ${USERSTORE}
```

Disabled user accounts will not be able to login to the Explorer application.


### Managing Base Data Packages (BDPs)
Base data packages consist of two parts: data objects stored in the SaaS backend
and some files stored in a "BDP store". For convenience, it is recommended to set 
an environment variable:
```shell
export BDPSTORE=$HOME/.bdpstore-27
```

Data objects are being uploaded to the SaaS backend on behalf of a valid identity
that is known to the SaaS backend. For convenience, it is recommended to set 
an environment variable to point at a key store with an identity known to the SaaS
backend:
```shell
export KEYSTORE=$HOME/.keystore-27
```

Note: the `KEYSTORE` should point at a valid key store location with identities that
are known to you SaaS node. For example, you may point at the same key store location
as used by the SaaS node itself. This is needed to create and remove BDPs as they need
to upload/delete objects from the SaaS backend.


#### Create Base Data Packages (BDPs)
The BDP for DUCT v0.27 contains the following datasets:
- `building-footprints.geojson`: Geometries defining building footprints (including height information). Source: OpenStreetMap. This file needs to be created by the user and should be a GeoJSON file containing the building geometries with height information obtained from the source.
- `city-admin-zones.geojson`: Geometries defining the administrative zones of the city. Source: [Master Plan 2019 Subzone Boundary](https://beta.data.gov.sg/datasets/d_8594ae9ff96d0c708bc2af633048edfb/view).
- `vegetation.tar.gz`: Trees only. Source: [Trees.sg and National Parks Board](https://github.com/cheeaun/sgtreesdata). This file should be the `data` folder that can be obtained from the source and all its contents archived as `tar.gz` file. 
- `land-use.geojson`: Geometries defining the land use. Source: [Master Plan 2019 Land Use Layer](https://beta.data.gov.sg/datasets/d_90d86daa5bfaa371668b84fa5f01424f/view). The GeoJSON file can be downloaded directly from the source and only needs to be renamed.
- `lcz-baseline.tiff`: Local Climate Zone of Singapore (30m resolution). Source: Cooling Singapore.
- `sh-traffic-ev100.json` and `sh-traffic-baseline.json`: Traffic anthropogenic heat emission profiles (sensible) for Singapore with and without electric vehicles. Source: Cooling Singapore
- `sh-power-baseline.json` and `lh-power-baseline.json`: Power plant anthropogenic heat emission profiles (sensible+latent) for Singapore (assuming no electric vehicles). Source: Cooling Singapore
- `description.md`: description of the datasets (very similar to the description here but formatted to be used by the Explorer).

Only `building-footprints.geojson`, `lcz-baseline.tiff`, `sh-traffic-ev100.json`, 
`sh-traffic-baseline.json`, `sh-power-baseline.json`, `lh-power-baseline.json` and 
`description.md` are provided here in this repository. The remaining datasets should 
be obtained from their respective sources. For the examples provided in this example, 
it is assumed the following files are also available:
- `city-admin-zones.geojson` 
- `land-use.geojson`
- `vegetation.tar.gz`

For this example, it is assumed all 10 files are located at `$HOME/Desktop/bdp-files`. 
To create a BDP, first navigate to the folder that contains the BDP files:
```shell
cd $HOME/Desktop/bdp-files
```

Then use the following command to build the BDP:
```shell
explorer --keystore ${KEYSTORE} bdp create --bdp_directory ${BDPSTORE} building-footprints.geojson city-admin-zones.geojson description.md land-use.geojson lcz-baseline.tiff lh-power-baseline.json sh-power-baseline.json sh-traffic-baseline.json sh-traffic-ev100.json vegetation.tar.gz  
```

The command will begin a dialogue to prompt the user to enter some information 
about the BDP. Use the following information:
- Name of city: Singapore
- Name of BDP: Public (v27) - or any other name...
- Bounding Box: 103.55161,1.53428,104.14966,1.19921
- Dimension: 211,130
- Timezone: Asia/Singapore

The dialogue will also ask the user to match the expected BDP items with the filenames
provided by the user and look like this:
```
? Select the keystore: test/test/jfvyt26w1jkqxj7e8h4867xujk5wmphvg3jeumiggy3l293m7m7h30tr7j1a7wal
? Enter password: ****
? Enter the target SaaS node's REST address [host:port]: 127.0.0.1:5001
? Enter the name of the city: Singapore
? Enter the name of the base data package: Public (v27)
? Enter the bounding box [west, north, east, south]: 103.55161,1.53428,104.14966,1.19921
? Enter the dimension [width, height]: 211,130
? Enter the timezone: Asia/Singapore
? Select the DUCT.GeoVectorData/geojson file to be used as 'city-admin-zones': city-admin-zones.geojson
? Select the DUCT.GeoVectorData/geojson file to be used as 'building-footprints': building-footprints.geojson
? Select the DUCT.GeoVectorData/geojson file to be used as 'land-use': land-use.geojson
? Select the DUCT.GeoVectorData/geojson file to be used as 'vegetation': vegetation.tar.gz
? Select the duct.lcz_map/tiff file to be used as 'lcz-baseline': lcz-baseline.tiff
? Select the duct.ah-profile/geojson file to be used as 'sh-traffic-baseline': sh-traffic-baseline.json
? Select the duct.ah-profile/geojson file to be used as 'sh-traffic-ev100': sh-traffic-ev100.json
? Select the duct.ah-profile/geojson file to be used as 'sh-power-baseline': sh-power-baseline.json
? Select the duct.ah-profile/geojson file to be used as 'lh-power-baseline': lh-power-baseline.json
? Select the *.BDPDescription/markdown file to be used as 'description': description.md
Feature IDs with duplicated geometries: 601443529, 962150397
Feature with ID 172518481 has invalid height value
Feature with ID 172518491 has invalid height value
Feature with ID 172518499 has invalid height value
Feature with ID 539766023 has invalid height value
Uploading files...done
Creating database...Loading city-admin-zones: 0 seconds
Loading building-footprints: 2 seconds
Loading vegetation: 5 seconds
Loading land-cover: 3 seconds
Loading land-use: 5 seconds
Loading import geometries as Default zone configuration: 121 seconds
done
Created building base data package 962fdc241c0540d90dd3bb3f9fa386dd6827a44cf426cccca4efc4276690f4d1: db=/Users/foobar/.bdpstore-27/962fdc241c0540d90dd3bb3f9fa386dd6827a44cf426cccca4efc4276690f4d1.db json=/Users/foobar/.bdpstore-27/962fdc241c0540d90dd3bb3f9fa386dd6827a44cf426cccca4efc4276690f4d1.json
```


#### List Base Data Packages
To see what BDPs are available, use the following command:
```shell
explorer bdp list --bdp_directory ${BDPSTORE}
```

The output looks like this:
```
Found 1 base data packages at /Users/foobar/.bdps-27:
BDP ID                                                            NAME          CITY       BOUNDING BOX                            DIMENSION  TIMEZONE
------                                                            ----          ----       ------------                            ---------  --------
962fdc241c0540d90dd3bb3f9fa386dd6827a44cf426cccca4efc4276690f4d1  Public (v27)  Singapore  103.55161, 1.53428, 104.14966, 1.19921  211, 130   Asia/Singapore
```

The example above shows the BDP that has been created earlier.

#### Remove Base Data Package (BDP)
A BDP can also be removed using the following command:
```shell
explorer --keystore ${KEYSTORE} bdp remove --bdp_directory ${BDP_DIRECTORY}
```



### Running an Explorer Server Instance
The Explorer server provides a REST API that is used by the Explorer frontend. The
REST interface uses a JWT authentication approach. For this purpose a secret needs
to be provided to the server, further referred to as `SECRET`.

The Explorer server communicates with the SaaS backend for the purpose of accessing 
data objects (via the SaaS DOR) and to manage simulation jobs (via the SaaS RTI). 
For this purpose the Explorer server requires a SaaS identity to identify itself 
to the SaaS backend.

The Explorer server stores project related data as well as cached data objects and
temporary files in a datastore. For convenience, it is recommended to set an 
environment variable:
```shell
export DATASTORE=$HOME/.datastore-explorer-27
```

If the `DATASTORE` directory does not exist yet, make sure to create it first:
```shell
mkdir $DATASTORE
```

To start a server instance, use the following command:
```shell
explorer --datastore ${DATASTORE} --keystore ${KEYSTORE} service --userstore ${USERSTORE} --bdp_directory ${BDPSTORE} --secret_key ${SECRET}
```

A dialogue confirms the addresses for the server as well as for the SaaS backend. 
It looks like this:
```
? Enter address for the server REST service: 127.0.0.1:5021
? Enter address of the SaaS node REST service: 127.0.0.1:5001
importing base data package 962fdc241c0540d90dd3bb3f9fa386dd6827a44cf426cccca4efc4276690f4d1
INFO:     Started server process [45185]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:5021 (Press CTRL+C to quit)
using new service user: service_explorer
Waiting to be terminated...
? Terminate the server? (y/N) 
```

The server instance will run indefinitely until interrupted via `CTRL-C` or by entering
'y' in the console.

Note that the first address (server REST service) is for the Explorer server. This is
the one that the Explorer frontend needs to connect to. The second address (SaaS node
REST service) is the address that the SaaS node is running on.

Also note that the Explorer server can also run non-interactively (for example as part
of a system service) by using corresponding command line arguments. Use 
`explorer service --help` for details.
