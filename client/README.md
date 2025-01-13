# DUCT Explorer Client
The DUCT Explorer Client is the frontend of the Explorer and is a client/server
applications.

## Prerequisites
- Node
- Yarn
- DUCT Explorer Server instance installed (here it is assumed the server runs 
on `127.0.0.1:5021`).


## Install
Ensure `yarn` and `node` prerequisites are installed. Go to the `client` folder 
and install dependencies:
```shell
cd client
yarn install
```


## Usage
Before starting the client, update the `apiHost` variable in 
`apps/duct/src/environments/environment.dev.ts`. The IP/host and port should point
at the address at which the Explorer server is running. By default, this is
`127.0.0.1:5021`.

The client can be started as follows:
```shell
yarn nx run duct:serve:development
```

By default, the client server is running on `http://localhost:4200/`. After starting
the client, use the browser to navigate to `http://localhost:4200/`. You should see
the DUCT Explorer login screen. You may need to create a user account first. See
Explorer REST server documentation for this purpose.
