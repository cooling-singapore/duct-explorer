FROM node:lts-alpine as build

# install dependancies and build app
WORKDIR /app
COPY package.json ./
COPY yarn.lock ./
RUN yarn install
COPY . .

# build storybook
RUN yarn nx run ui:build-storybook:ci

# setup ngnix 
FROM nginx:1.21-alpine
WORKDIR /app/nginx
COPY nginx.conf /etc/nginx/nginx.conf

# copy storybook bundle and place in ngnix
COPY --from=build /app/dist/storybook/ui /usr/share/nginx/html

EXPOSE 443
CMD ["nginx", "-g", "daemon off;"]