# Explorer Frontend

## Prerequisites

- Node
- Yarn
- [NX CLI](https://nx.dev/latest/react/getting-started/nx-cli)

## Install dependencies

Run `yarn install`

## Development server

Run `yarn nx run duct:serve:development` for a dev server. Navigate to http://localhost:4200/. The app will automatically reload if you change any of the source files.

## Build

Run `yarn nx run duct:build` to build the project. The build artifacts will be stored in the `dist/` directory. Use the `--prod` flag for a production build.

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
