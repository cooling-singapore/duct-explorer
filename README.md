# DUCT Explorer
This repository is part of the Cooling Singapore 2.0 project which ended in August 2024. 
The repository is deprecated and will no longer be maintained. For further information please contact 
*contact-dtlab@sec.ethz.ch.*

## Directory Structure
DUCT Explorer is organised into two main components, reflecting its directory structure:
- `server`: contains the Python code and related resources for the DUCT Explorer REST Server.
- `client`: contains the JavaScript code and related resources for the DUCT Explorer Client.

In addition to `server` and `client`, there is an additional folder:
- `bdp`: contains data for a Base Data Package (BDP) of Singapore. Refer to the documentation in `server` for instructions how to manage BDPs.

## Overview
From a high-level point of view the DUCT Explorer is based on the following stack:
- SaaS node instance (see [SaaS Middleware](https://github.com/cooling-singapore/saas-middleware) 
  for details). A SaaS node is part of the backend and is responsible for simulation execution and
  management of data objects.
- Explorer REST server (found in `server`). An instance of the REST server is part of the
  backend and provides a REST API that can be utilised by the Explorer client. The Explorer  
  REST server interacts with the SaaS node instance to trigger simulations upon demand.
- Explorer client (found in `client`). A client/server web-application, representing
  the frontend, i.e., the browser-based DUCT Explorer application.


## Install
In order to install the DUCT Explorer, the following needs to be installed and 
started.
- [SaaS Middleware](https://github.com/cooling-singapore/saas-middleware). At least
  one instance of a SaaS node needs to be setup in order for the Explorer to work.
  Ideally, this is a full node, i.e., a SaaS node that provides RTI (runtime
  infrastructure) and DOR (data object repository) services.
- [Explorer REST Server](server/README.md). The Explorer REST Server needs to be installed
  and started. It requires a SaaS node instance in order to work. The `explorer` CLI
  should be used to create user accounts and to create a BDP as well.
- [Explorer Client](client/README.md). The Explorer Client needs to be installed and
  started. It requires an Explorer REST Server in order to function.

For detailed install and usage instructions, refer to the relevant sections in the
[server](server/README.md) and [client](client/README.md) documentation.

## Setup System Services
The following describes an example setup for a Ubuntu 22.04 environment. Note that
this example is for general guidance only and not suitable for production 
environments. It is assumed that a Ubuntu 22.04 is used and a storage partition is 
available and mounted to `/mnt/storage/`. Furthermore, this example setup uses a
single SaaS full node (with both, storage and execution, capabilities). A more 
sophisticated setup may have multiple nodes and distinguish between execution and 
storage nodes.

### Create service file for SaaS Middleware node at 
`/etc/systemd/system/saas_node.service` with the following content:
```
[Unit]
Description=saas_node
After=network.target

[Service]
Type=simple
User=ubuntu
Restart=always
RestartSec=5
Environment="VENV_PATH=/mnt/storage/venv-saas"
Environment="KEYSTORE=/mnt/storage/.keystore/"
Environment="KEYSTORE_ID=apo9c5mpj6y5muycm8c1uashzehf55jx9ortn26v9aabmmefljxvycicix4la70g"
Environment="PASSWORD_FILE=/mnt/storage/password.saas_node"
Environment="LOG_PATH=/mnt/storage/log.0"
Environment="DATASTORE=/mnt/storage/.datastore-saas"
Environment="REST_ADDRESS=10.8.0.1:5001"
Environment="P2P_ADDRESS=10.8.0.1:4001"
Environment="BOOT_ADDRESS=10.8.0.1:4001"
ExecStart=/bin/bash -c 'source ${VENV_PATH}/bin/activate && saas-node --keystore ${KEYSTORE} --keystore-id ${KEYSTORE_ID} --password $(cat ${PASSWORD_FILE}) --log-path ${LOG_PATH} run --datastore ${DATASTORE} --rest-address ${REST_ADDRESS} --p2p-address ${P2P_ADDRESS} --boot-node ${BOOT_ADDRESS} --type full'

[Install]
WantedBy=multi-user.target
```

### Create service file for Explorer server at 
`/etc/systemd/system/explorer_server.service` with the following content:
```
[Unit]
Description=explorer_server
After=network.target

[Service]
Type=simple
User=ubuntu
Restart=always
RestartSec=5
Environment="VENV_PATH=/mnt/storage/venv-explorer"
Environment="DATASTORE=/mnt/storage/.datastore-explorer"
Environment="KEYSTORE=/mnt/storage/.keystore"
Environment="KEYSTORE_ID=apo9c5mpj6y5muycm8c1uashzehf55jx9ortn26v9aabmmefljxvycicix4la70g"
Environment="PASSWORD_FILE=/mnt/storage/password.explorer_server"
Environment="LOG_PATH=/mnt/storage/log.explorer"
Environment="USERSTORE=/mnt/storage/.userstore"
Environment="BDP_PATH=/mnt/storage/.bdpstore"
Environment="SECRET=tTwOhaXu9MnkyDebb1rncyFw47mmdg1M"
Environment="SERVER_ADDRESS=10.8.0.1:5021"
Environment="NODE_ADDRESS=10.8.0.1:5001"
ExecStart=/bin/bash -c 'source ${VENV_PATH}/bin/activate && explorer --datastore ${DATASTORE} --keystore ${KEYSTORE} --keystore-id ${KEYSTORE_ID} --password $(cat ${PASSWORD_FILE}) --log-path ${LOG_PATH} --log-level INFO service --userstore ${USERSTORE} --bdp_directory ${BDP_PATH} --secret_key ${SECRET} --server_address ${SERVER_ADDRESS} --node_address ${NODE_ADDRESS}'

[Install]
WantedBy=multi-user.target
```

### Create service file for Explorer client at 
`/etc/systemd/system/explorer_client.service` with the following content:
```
[Unit]
Description=explorer_client
After=network.target

[Service]
Type=simple
User=ubuntu
Restart=always
RestartSec=5
Environment="WORKSPACE=/mnt/storage/duct-explorer/client"
Environment="CLIENT_ADDRESS=10.8.0.1"
ExecStart=/bin/bash -c 'cd ${WORKSPACE} && yarn nx serve --host=${CLIENT_ADDRESS}'

[Install]
WantedBy=multi-user.target
```

Ensure the environment variables are set appropriately. You will have to modify
the sample values according to your installation and environment.
- `VENV_PATH`: Path to Python virtual environment
- `KEYSTORE`: Path to the keystore containing identities recognised by the SaaS node
- `KEYSTORE_ID`: Identity of the keystore that the node will use
- `PASSWORD_FILE`: Path to the file where passwords is stored
- `LOG_PATH`: Path to the file where logs are stored
- `DATASTORE`: Path to the directory for storing all SaaS-related data
- `USERSTORE`: Path to the location where Explorer users are created
- `BDP_PATH`: Path to the location where BDPs are created
- `SECRET`: The secret key for JWT token generation

Reload systemd, enable and start the services:
```shell
sudo systemctl daemon-reload
sudo systemctl enable saas_node.service
sudo systemctl enable explorer_server.service
sudo systemctl enable explorer_client.service
sudo systemctl restart saas_node.service
sudo systemctl restart explorer_server.service
sudo systemctl restart explorer_client.service
```

Check the status of the services:
```shell
sudo systemctl status saas_node.service
sudo systemctl status explorer_server.service
sudo systemctl status explorer_client.service
```

Check the logs of the services:
```shell
sudo journalctl -u saas_node.service
sudo journalctl -u explorer_server.service
sudo journalctl -u explorer_client.service
```

## Deploy DUCT Federation of Models Processors
Analysis types will appear in the Explorer application only after deploying the required processors. Follow the steps below to deploy processors:

The Runtime Infrastructure (RTI) module executes jobs using deployed processors. These jobs consume input data (from a DOR as data objects or JSON) and produce output data (stored in a DOR). The processor descriptor specifies the required input and generated output.

To deploy a processor, add a Git Processor Pointer (GPP) to a DOR in the same domain. Use the CLI to specify the repository and commit ID (default: latest on Main/Master), search for processors, and select one interactively.

The following example shows how to interactively add a GPP:

```shell
saas-cli dor --address 127.0.0.1:5001 add-gpp 

? Select the keystore: foo bar/foo.bar@email.com/i6vmw1hffcsf5pg6dlc4ofxl1s95czqs6uuqg8mf9hz32qdei4b8gmwu4eivtm3t
? Enter password: ***
? Enter the URL of the Github repository: https://github.com/cooling-singapore/duct-fom
? Analyse repository at https://github.com/cooling-singapore/duct-fom to help with missing arguments? Yes
Cloning repository 'duct-fom' to '/home/ubuntu/.temp/duct-fom'...Done
Determining default commit id...Done: c28310bdf8079528fae824cca45fcb4e64a7dc55
? Enter commit id: c28310bdf8079528fae824cca45fcb4e64a7dc55
Checkout commit id c28310bdf8079528fae824cca45fcb4e64a7dc55...Done
Searching for processor descriptors...Done: found 9 descriptors.
Analysing descriptor file '/home/ubuntu/.temp/duct-fom/ucm-mva/proc_uwc/descriptor.json'...Done
Analysing descriptor file '/home/ubuntu/.temp/duct-fom/ucm-mva/proc_uvp/descriptor.json'...Done
Analysing descriptor file '/home/ubuntu/.temp/duct-fom/bem-cea/proc_bee/descriptor.json'...Done
Analysing descriptor file '/home/ubuntu/.temp/duct-fom/bem-cea/proc_gen/descriptor.json'...Done
Analysing descriptor file '/home/ubuntu/.temp/duct-fom/bem-cea/proc_dcn/descriptor.json'...Done
Analysing descriptor file '/home/ubuntu/.temp/duct-fom/ucm-palm/proc_prep/descriptor.json'...Done
Analysing descriptor file '/home/ubuntu/.temp/duct-fom/ucm-palm/proc_sim/descriptor.json'...Done
Analysing descriptor file '/home/ubuntu/.temp/duct-fom/ucm-wrf/proc_prep/descriptor.json'...Done
Analysing descriptor file '/home/ubuntu/.temp/duct-fom/ucm-wrf/proc_sim/descriptor.json'...Done
? Select a processor: 
  ucm-mva-uwc in ucm-mva/proc_uwc
  ucm-mva-uvp in ucm-mva/proc_uvp
  bem-cea-bee in bem-cea/proc_bee
  bem-cea-gen in bem-cea/proc_gen
  bem-cea-dcn in bem-cea/proc_dcn
  ucm-palm-prep in ucm-palm/proc_prep
  ucm-palm-sim in ucm-palm/proc_sim
  ucm-wrf-prep in ucm-wrf/proc_prep
  ucm-wrf-sim in ucm-wrf/proc_sim

```
From the list of available processors, select the one you want to deploy. Following example has selected the 'ucm-mva/proc_uwc'

```
? Select a processor: ucm-mva-uwc in ucm-mva/proc_uwc
Load processor descriptor at 'ucm-mva/proc_uwc'...Done
? Select the configuration profile: gce-ubuntu-22.04
GPP Data object added: {
    "obj_id": "c4fde0e2b87c7423cfff0479bbd72912ba8ab841c343a2fa152a02478e7cf6df",
    "c_hash": "c4fde0e2b87c7423cfff0479bbd72912ba8ab841c343a2fa152a02478e7cf6df",
    "data_type": "GitProcessorPointer",
    "data_format": "json",
    "created": {
        "timestamp": 1737692288480,
        "creators_iid": [
            "apo9c5mpj6y5muycm8c1uashzehf55jx9ortn26v9aabmmefljxvycicix4la70g"
        ]
    },
    "owner_iid": "apo9c5mpj6y5muycm8c1uashzehf55jx9ortn26v9aabmmefljxvycicix4la70g",
    "access_restricted": false,
    "access": [
        "apo9c5mpj6y5muycm8c1uashzehf55jx9ortn26v9aabmmefljxvycicix4la70g"
    ],
    "tags": {},
    "last_accessed": 1737692288480,
    "custodian": {
        "identity": {
            "id": "apo9c5mpj6y5muycm8c1uashzehf55jx9ortn26v9aabmmefljxvycicix4la70g",
            "name": "dtl user",
            "email": "dtl-user@duct.sg",
            "s_public_key": "MHYwEAYHKoZIzj0CAQYFK4EEACIDYgAEdOFLO7iQxIoZBWEt+zVPKm780vHI4QTayprbGYAkPMw5nEJt2GzkFCPD+ewqwTOn5pqR2hdaAN7BzWNWNh4BlDNWgR7SR0JpyZPzh+lNFNJUaeASx/fh+3CuSG3vN5Dd",
            "e_public_key": "MIICIjANBgkqhkiG9w0BAQEFAAOCAg8AMIICCgKCAgEArIt4l/yfzOMwevPMAKzkGK1mBpAbWmYB7i4+H+3tkNa1gTQL3eJ1mHIx89jUHsChiRlzJghnXszmF0Wm3iiLJWqimFQOnPXoKIhMjf1KSwkGnwU060wcTwxCqp71cJ4miAj2GRT63IF/B6Nj2zVtJ7iPLlGTMjvVBBiUOxWGhQzMlapplXSsAAabHvWFbmQ4LjJrh91H71rDW9btSoCGbFVqttskd/xISh4ivMUhIgjLu+LTxBdouj8VBKvBeS/xJq+PX+fID+Elhm/C2oa3HTMMlN2CpvWTAQKNM33kOGm10dO1DarmUuWOUjpIjtSMyYlzs5QnXYSL5RjQ4sGcdOWLded5VvapFj+NQ0CLUGYe+e2rivkRtj84o5kRV6aX7ZvQa5pM1ro324MubpYl9tUrWlhKqGoP13tWsfbMVbN4+rMjLdVm5gdY8/qa1VK5cAPfLrz4fVVmTwdMgIyUE6yLEvQ87wt2jdudniD5yLZ4VT6SJWzf/mk2wRciXhESPdFLrEgvDkftCOcHQt0iN3mBDGKZJEZiR1dKrqA+IZz2+9wTSrywRwCERJnc25Xx4SceQ4MlBi3Q7cSITHpNmUKAaNyDmmEwoSaCaebddDW9JtNdPkxT4HLRJT8dEurNK2S4zyw49EVBigrrNQiLMUZ3hMYvfQBhothS5ercoOcCAwEAAQ==",
            "nonce": 1,
            "signature": "3066023100ee759ae4e93d41b3bbcf48aef1133def2f0f801b15f2cda7f2302e40ecb15c8ec05f459ef83e6058dfad821c465457c6023100acdff6c62b0246f7925bd66df6101cb7273110028ed54834da7b9ddf681e082067a173f07d659eb35f6581a64994fa9c",
            "last_seen": null
        },
        "last_seen": 1737703040721,
        "dor_service": true,
        "rti_service": true,
        "p2p_address": [
            "10.8.0.1",
            4001
        ],
        "rest_address": [
            "10.8.0.1",
            5001
        ],
        "retain_job_history": false,
        "strict_deployment": true,
        "job_concurrency": true
    },
    "gpp": {
        "source": "https://github.com/cooling-singapore/duct-fom",
        "commit_id": "c28310bdf8079528fae824cca45fcb4e64a7dc55",
        "proc_path": "ucm-mva/proc_uwc",
        "proc_config": "gce-ubuntu-22.04",
        "proc_descriptor": {
            "name": "ucm-mva-uwc",
            "input": [
                {
                    "name": "parameters",
                    "data_type": "UCMMVA.UWCParameters",
                    "data_format": "json",
                    "data_schema": {
                        "type": "object",
                        "title": "UCM-MVA-UWC Parameters",
                        "properties": {
                            "bounding_box": {
                                "type": "object",
                                "title": "Bounds",
                                "description": "Default bounds is Singapore.",
                                "properties": {
                                    "west": {
                                        "type": "number",
                                        "title": "West (in degrees longitude)",
                                        "default": 103.55161
                                    },
                                    "east": {
                                        "type": "number",
                                        "title": "East (in degrees longitude)",
                                        "default": 104.14966
                                    },
                                    "north": {
                                        "type": "number",
                                        "title": "North (in degrees latitude)",
                                        "default": 1.53428
                                    },
                                    "south": {
                                        "type": "number",
                                        "title": "South (in degrees latitude)",
                                        "default": 1.19921
                                    }
                                },
                                "required": [
                                    "west",
                                    "east",
                                    "north",
                                    "south"
                                ]
                            },
                            "resolution": {
                                "type": "integer",
                                "title": "Resolution",
                                "default": 300
                            }
                        },
                        "required": [
                            "bounding_box",
                            "resolution"
                        ]
                    }
                },
                {
                    "name": "building-footprints",
                    "data_type": "DUCT.GeoVectorData",
                    "data_format": "geojson",
                    "data_schema": null
                },
                {
                    "name": "land-mask",
                    "data_type": "DUCT.GeoVectorData",
                    "data_format": "geojson",
                    "data_schema": null
                }
            ],
            "output": [
                {
                    "name": "wind-corridors-ns",
                    "data_type": "DUCT.GeoRasterData",
                    "data_format": "tiff",
                    "data_schema": null
                },
                {
                    "name": "wind-corridors-ew",
                    "data_type": "DUCT.GeoRasterData",
                    "data_format": "tiff",
                    "data_schema": null
                },
                {
                    "name": "wind-corridors-nwse",
                    "data_type": "DUCT.GeoRasterData",
                    "data_format": "tiff",
                    "data_schema": null
                },
                {
                    "name": "wind-corridors-nesw",
                    "data_type": "DUCT.GeoRasterData",
                    "data_format": "tiff",
                    "data_schema": null
                },
                {
                    "name": "building-footprints",
                    "data_type": "DUCT.GeoRasterData",
                    "data_format": "tiff",
                    "data_schema": null
                },
                {
                    "name": "land-mask",
                    "data_type": "DUCT.GeoRasterData",
                    "data_format": "tiff",
                    "data_schema": null
                }
            ],
            "configurations": [
                "gce-ubuntu-22.04"
            ]
        }
    }
}
```

Once the GPP is in a DOR, the RTI can deploy the processor locally or remotely, requiring an SSH profile for remote deployment.

Example:

```shell
saas-cli rti --address 127.0.0.1:5001 proc deploy
? Select the keystore: foo bar/foo.bar@email.com/i6vmw1hffcsf5pg6dlc4ofxl1s95czqs6uuqg8mf9hz32qdei4b8gmwu4eivtm3t
? Enter password: ***
? Select the processor you would like to deploy: c4fde0e2b87c7423cfff0479bbd72912ba8ab841c343a2fa152a02478e7cf6df [ucm-mva-uwc] gce-ubuntu-22.04:c28310bdf8079528f
ae824cca45fcb4e64a7dc55
? Use an SSH profile for deployment? No
Deploying processor c4fde0e2b87c7423cfff0479bbd72912ba8ab841c343a2fa152a02478e7cf6df...Done
```

To view the processor status:

```shell
saas-cli rti proc status
? Enter the nodes REST address: 127.0.0.1:5001
Found 3 processor(s) deployed at 127.0.0.1:5001:
262fc18eae6b07fbdd5d61c574f09b2f69496881559a8eba2ac850170c5a653c:example-processor [OPERATIONAL] pending=(none) active=(none)
c4fde0e2b87c7423cfff0479bbd72912ba8ab841c343a2fa152a02478e7cf6df:ucm-mva-uwc [OPERATIONAL] pending=(none) active=(none)
ae8b7451c3a12c0b839cdcd35891ea90b0dc8abe31093617cebb5e4d3613674b:ucm-mva-uvp [OPERATIONAL] pending=(none) active=(none)
```

For a list of all arguments, use:
```shell
saas-cli rti proc --help
```
