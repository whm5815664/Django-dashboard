import { createApp } from "vue";
import App from "./App.vue";
import router from "./router";
import store from "./store";

// 导入 Element Plus 和 axios
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import axios from "axios";

// 使用 createApp 创建应用
const app = createApp(App);  

// 配置 axios 
const api = axios.create({
    baseURL:  "/labdataset/api", 
    timeout: 15000,
});
app.config.globalProperties.$api = api; // 将axios挂载到vue实例


app.use(store).use(router).use(ElementPlus).mount("#app");
