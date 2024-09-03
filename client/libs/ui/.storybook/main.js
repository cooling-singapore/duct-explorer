/* eslint-disable no-undef */
// Use the following syntax to add addons!
// rootMain.addons.push('');

rootMain.core = { builder: 'webpack5' };

module.exports = rootMain;
module.exports.addons = ['@storybook/addon-essentials'];
module.exports.stories = [
  '../src/lib/**/*.stories.mdx',
  '../src/lib/**/*.stories.@(js|jsx|ts|tsx)',
];
