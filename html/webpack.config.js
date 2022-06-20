const path = require('path');
const fs = require('fs');
const yaml = require('yaml');
const webpack = require('webpack');
const config = yaml.parse(fs.readFileSync("../../config.yaml", "utf-8"));

module.exports = {
  entry: './src/index.ts',
  devtool: 'inline-source-map',
  module: {
    rules: [
      {
        test: /\.tsx?$/,
        use: 'ts-loader',
        exclude: /node_modules/,
      },
      {
        test: /\.css$/i,
        use: ['style-loader', 'css-loader'],
      },
    ],
  },
  resolve: {
    extensions: ['.tsx', '.ts', '.js'],
  },
  output: {
    filename: 'bundle.js',
    path: path.resolve(__dirname, 'dist'),
  },
  plugins: [
    new webpack.DefinePlugin({
      "process.env": {
        "WEBSOCKETURL": JSON.stringify(config["websocket-host"])
      }
    }),
  ],
};