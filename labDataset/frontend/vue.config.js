// vue.config.js
const path = require("path")

module.exports = {
    transpileDependencies: ['vue-router', 'vuex'],

    // 配置Vue build: 输出到 Django 的 templates/static
    // 生产整合再: /static/labDataset/（build 后交给 Django 托管）
    outputDir: path.resolve(__dirname, "../static/labDataset"),
    indexPath: path.resolve(__dirname, "../templates/labDataset/index.html"),

    // 开发时的页面挂载点 和 生产build的页面挂载点要区分
    // 开发挂在 /labDataset/，生产资源走 /static/labDataset/
    // 开发期npm run serve访问：http://localhost:8081/
    publicPath: process.env.NODE_ENV === "production"
    ? "/static/labDataset/"
    : "/labDataset/",

    
    // API 请求：labDataset/api/xxx/ → 被代理到 Django 8000
    devServer: {
      port: 8081,
      proxy: {
        "/labDataset/api": {
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
