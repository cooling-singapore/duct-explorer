FROM node:20-alpine as build

# install dependencies and build app
WORKDIR /app
COPY package.json ./
COPY yarn.lock ./
RUN yarn install
COPY . .
ARG TAG_NAME
ENV NX_DUCT_VERSION=$TAG_NAME

ARG BUILD_CONFIG='production'

# build duct
RUN yarn nx run duct:build:$BUILD_CONFIG --parallel

# setup ngnix 
FROM nginx:1.21-alpine
WORKDIR /app/nginx
COPY duct.nginx.conf /etc/nginx/nginx.conf

# copy bundle and place in ngnix
COPY --from=build /app/dist/apps/duct /usr/share/nginx/html

EXPOSE 3021
CMD ["nginx", "-g", "daemon off;"]