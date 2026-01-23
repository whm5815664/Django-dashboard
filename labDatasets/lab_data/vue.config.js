// vue.config.js
module.exports = {
    transpileDependencies: ['vue-router', 'vuex'],
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
    }
}
