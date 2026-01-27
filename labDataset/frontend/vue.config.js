// vue.config.js
const path = require("path")

module.exports = {
    transpileDependencies: ['vue-router', 'vuex'],

    // 配置 Vue build 输出到 Django 的 templates/static
    outputDir: path.resolve(__dirname, "../static/labDataset"),
    indexPath: path.resolve(__dirname, "../templates/labDataset/index.html"),
    publicPath: "/static/labDataset/",
    devServer: {
      proxy: {
        "/api": {
          target: "http://127.0.0.1:8000",
          changeOrigin: true,
        },
      },
    },

    configureWebpack: {
      module: {
        rules: [
          {
            test: /\.csv$/,
            use: [
              {
                loader: 'csv-loader',
                options: {
                  dynamicTyping: true,
                  header: true,
                  skipEmptyLines: true
                }
              }
            ]
          }
        ]
      }
    },
}
