# DUCT Explorer Frontend

## Running the application locally

### Prerequisites

- Node
- Yarn
- [NX CLI](https://nx.dev/latest/react/getting-started/nx-cli)

### Install dependencies

Run `yarn install`

### Start development server

- Update environment variables. In most cases only the `apiHost` would have to be updated. Please refer the `Set up environment variables` section below
- Run `yarn nx run duct:serve:development` for a dev server. Navigate to http://localhost:4200/. The app will automatically reload if you change any of the source files.
- Refer [NX run documentation](https://nx.dev/nx-api/nx/documents/run) to learn more about the run command


## Defining a new environment (optional)

### Set up environment variables

- Navigate to `apps/duct/src/environments` and define a new file and change the variables required for the new environment.
- Refer to `environment.ts` for an example

### Set up NX project configuration

- Navigate to the `project.json` file located in `apps/duct`.
- Add a new build configuration for the deployment in this path: targets > build > configurations
- The name you use for the configuration is what would be used to run the NX build command.
- Update the `fileReplacements` property with the name of the environment file you created in the first step.
- Set up any other properties as needed.


## Build

### Bundling the application

Run `yarn nx run duct:build:development` to build the project. The build artifacts will be stored in the `dist/` directory.

### Create a Docker image

Example usage:

```
docker build \
-t duct-explorer \
--build-arg TAG_NAME='duct-dev-0.0.1 \
--build-arg BUILD_CONFIG='development' \
```

#### Arguments

- `-t duct-explorer`: Assigns a name (duct-explorer) to the resulting Docker image.
- `--build-arg TAG_NAME='duct-dev-0.0.1'`: Passes the `TAG_NAME` argument to the build process, which specifies the tag or version for the build.
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
|   |   └── environments/ # Contains environment configurations for any custom environments
├── project.json          # Project configuration settings like build and run targets
└── Dockerfile            # Commands to build a docker image
```

## Recommended Code Refinements

- The map layer components in `apps\duct\src\app\utils\ui\map-layers` to be converted to hooks which return an instace of the layer type.
- Docker file needs to be updated to use the serve package so it no longer depends on nginx and use a multi-stage build.