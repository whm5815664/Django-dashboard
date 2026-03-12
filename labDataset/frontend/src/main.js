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

// 配置 axios: api实例
const api = axios.create({
    baseURL:  "/labDataset/api/", 
    timeout: 15000,
    withCredentials:true,  // 带cookie + 自动加header
});
function getCookie(name) {
    const match = document.cookie.match(new RegExp("(^| )" + name + "=([^;]+)"));
    return match ? decodeURIComponent(match[2]) : null;
}
  
api.interceptors.request.use((config) => {
    const token = getCookie("csrftoken");
    if (token) {
      config.headers = config.headers || {};
      config.headers["X-CSRFToken"] = token;
    }
    return config;
});
app.config.globalProperties.$api = api; // 将axios挂载到vue实例


app.use(store).use(router).use(ElementPlus).mount("#app");
