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


## Install and Usage
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