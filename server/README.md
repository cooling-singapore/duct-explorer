# Duct-Servers

## Overview
Duct-servers provide a dashboard and explorer service, which are dependent on saas-middleware services. This documentation guides you through the setup, testing, and administration of these services.

## Prerequisites
Ensure that the saas-middleware services are operational before initiating duct-servers.

## Setup Instructions

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

# Deployment

## GitHub Actions
- Builds and pushes dockerfiles/services/Dockerfile to GCP artifact registry.
- Uses k8s kustomize to deploy templates under k8s using base/overlays.

## Testing Procedures
### Testing in GCP Environment
Use the following commands for testing in a GCP environment:

```shell
gcloud auth gke
kubectl get pods
kubectl logs
kubectl get svc
kubectl delete pod # Use if deployment is not working
```

### Testing Kustomize Locally
To verify if kustomize is working correctly in a local environment:

```shell
cd /k8s/overlays/dashboard
kustomize edit set image IMAGE_PLACEHOLDER=123-docker.pkg.dev/test/sample/dashboard:test
kustomize build
```

### Administration of Explorer and Dashboard Pods
For file transfer and interactive access to the pods:

```shell
kubectl cp myfile.txt tmp-pod:/mnt/myfile.txt
kubectl exec -it tmp-pod -- sh
```

### Running Duct-Servers Locally with Docker-Compose
Starting Services
To run the services locally:

```bash
docker-compose up --build
```

To troubleshoot single dockerfile
```bash
cd dockerfiles/app
DOCKER_BUILDKIT=0 docker build -t duct-servers:latest .
```

### Interactive Shell Access
For interactive shell access to a service:

```bash
docker-compose exec -it ${service-name} /bin/bash
```

