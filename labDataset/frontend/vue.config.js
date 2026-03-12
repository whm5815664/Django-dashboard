// vue.config.js
const path = require("path")

module.exports = {
    transpileDependencies: ['vue-router', 'vuex'],

    // 配置 Vue build 输出到 Django 的 templates/static
    outputDir: path.resolve(__dirname, "../static/labDataset"),
    indexPath: path.resolve(__dirname, "../templates/labDataset/index.html"),
    publicPath: "/static/labDataset/",

    // 开发期访问：http://localhost:8081/
    // API 请求：/api/xxx/ → 被代理到 Django 8000
    // 生产整合再用 /static/labDataset/（build 后交给 Django 托管）
    devServer: {
      port: 8081,
      proxy: {
        "/labdataset": {
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
