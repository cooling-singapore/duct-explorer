const TsconfigPathsPlugin = require('tsconfig-paths-webpack-plugin');
const rootWebpackConfig = require('../../../.storybook/webpack.config');

/**
 * Export a function. Accept the base config as the only param.
 *
 * @param {Parameters<typeof rootWebpackConfig>[0]} options
 */
module.exports = async ({ config, mode }) => {
  config = await rootWebpackConfig({ config, mode });

  const tsPaths = new TsconfigPathsPlugin({
    configFile: './tsconfig.base.json',
  });

  config.resolve.plugins
    ? config.resolve.plugins.push(tsPaths)
    : (config.resolve.plugins = [tsPaths]);

  // Found this here: https://github.com/nrwl/nx/issues/2859
  // And copied the part of the solution that made it work

  const svgRuleIndex = config.module.rules.findIndex((rule) => {
    const { test } = rule;

    return test.toString().startsWith('/\\.(svg|ico');
  });
  config.module.rules[svgRuleIndex].test =
    /\.(ico|jpg|jpeg|png|gif|eot|otf|webp|ttf|woff|woff2|cur|ani|pdf)(\?.*)?$/;

    config.module.rules.push(
        {
          test: /\.(png|jpe?g|gif|webp)$/,
          loader: 'url-loader',
          options: {
            limit: 10000, // 10kB
            name: '[name].[hash:7].[ext]',
          },
        },
        {
          test: /\.svg$/,
          oneOf: [
            // If coming from JS/TS file, then transform into React component using SVGR.
            {
            //   issuer: {
            //     test: /\.[jt]sx?$/,
            //   },
              use: [
                '@svgr/webpack?-svgo,+titleProp,+ref![path]',
                {
                  loader: 'url-loader',
                  options: {
                    limit: 10000, // 10kB
                    name: '[name].[hash:7].[ext]',
                  },
                },
              ],
            },
            // Fallback to plain URL loader.
            {
              use: [
                {
                  loader: 'url-loader',
                  options: {
                    limit: 10000, // 10kB
                    name: '[name].[hash:7].[ext]',
                  },
                },
              ],
            },
          ],
        },
      );

  return config;
};
