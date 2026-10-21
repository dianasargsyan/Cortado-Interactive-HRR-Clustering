const webpack = require("webpack");
const path = require("path");
const MONACO_DIR = path.join(__dirname, "", "node_modules/monaco-editor");

/**
 * Using this custom webpack config to load the css files
 * in monaco editor library. More information here:
 * https://github.com/microsoft/monaco-editor/issues/886
 */

module.exports = {
  module: {
    rules: [
      {
        test: /\.css$/,
        include: MONACO_DIR,
        use: [
          "style-loader",
          {
            loader: "css-loader",
            options: {
              url: false,
            },
          },
        ],
      },
    ],
  },
};
