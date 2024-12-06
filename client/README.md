# DUCT Explorer Frontend

## Prerequisites

- Node
- Yarn
- [NX CLI](https://nx.dev/latest/react/getting-started/nx-cli)

## Install dependencies

Run `yarn install`

## Development server

Run `yarn nx run duct:serve:development` for a dev server. Navigate to http://localhost:4200/. The app will automatically reload if you change any of the source files.

## Build

### Bundle

Run `yarn nx run duct:build` to build the project. The build artifacts will be stored in the `dist/` directory. Use the `--prod` flag for a production build.

### Docker image

Example usage:

```
docker build \
-t duct-explorer \
--build-arg TAG_NAME='duct-staging-0.0.1 \
--build-arg BUILD_CONFIG='development' \
```

#### Arguments

- `-t duct-explorer`: Assigns a name (duct-explorer) to the resulting Docker image.
- `--build-arg TAG_NAME='duct-staging-0.0.1'`: Passes the `TAG_NAME` argument to the build process, which specifies the tag or version for the build.
- `--build-arg BUILD_CONFIG='development'`: Passes the `BUILD_CONFIG` argument to define the configuration mode (e.g., development, staging, or production).

## Project Structure

```root
├── apps/
│   └── duct/             # The explorer react application. Refer the section below for details
├── libs/                 # Shared libraries
│   └── data/             # Contains shared type specifications and services
│   └── ui/               # Contains shared UI components
├── nx.json               # Nx workspace configuration
├── .dockerignore         # Ignore list for docker
├── package.json          # Dependencies and scripts
└── tsconfig.base.json    # Base TypeScript configuration
```

## Application Structure

```root
├── duct/                 # The explorer react application
|   ├── src/
|   |   ├── app/          # Contains react components organised by route
|   |   |   ├── context/  # Contains react context types used in the application
|   |   |   ├── utils/    # Contains utilities used in the application
|   |   |   └── app.tsx   # Defines the app shell and route configurations
|   |   ├── assets/       # Contains image assets used by the explorer
|   |   └── environments/ # Contains environment configurations for individual environments
├── project.json          # Project configuration settings like build and run targets
└── Dockerfile            # Commands to build a docker image
```

## Deploying the DUCT Explorer

### Set up environment variables

- Navigate to `apps/duct/src/environments` and define a new file and change the variables required for the new deployment. In most cases only the apiHost would have to be updated.
- Follow the existing file naming structure for consistency.

### Set up NX project configuration

- Navigate to the `project.json` file located in `apps/duct`.
- Add a new build configuration for the deployment in this path: targets > build > configurations
- The name you use for the configuration is what would be used to run the NX build command, therefore simply follow the existing naming structure for consistency.
- Update the `fileReplacements` property with the name of the environment file you created in the first step.
- Set up any other properties as needed.

### Set up Github Actions and cloud service provider

Set up GitHub Actions to build and deploy the DUCT Explorer docker image by creating a workflow file in `.github/workflows/` and configuring it based on your cloud provider (e.g., AWS, Azure, or GCP). Add necessary secrets like API keys or credentials in the repository's `Settings > Secrets and variables`. Refer to the official documentation for detailed setup steps for your provider (AWS, Azure, GCP).

### Trigger a Build

This step would differ depending on how the Github aciton has been configured. The following example assums the on tag event is used. 


Create a tag. The format of this tag must match the regular expression defined in the Github workflow:

```
git tag duct-staging-0.0.1
git push origin –tags
```

Once done, push the tag and monitor the progress in the Actions tab on Github
