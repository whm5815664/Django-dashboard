import { createRouter, createWebHistory } from "vue-router";
import DatasetList from "../views/DatasetList.vue";
import DatasetDetail from "../views/DatasetDetail.vue";

const routes = [
  {
    path: "/",
    name: "DatasetList",
    component: DatasetList,
  },
  {
    path: "/detail",
    name: "DatasetDetail",
    component: DatasetDetail,
    // component: () =>
    //   import(/* webpackChunkName: "about" */ "../views/About.vue"),
  },

  // 详情页:路由跳转
  {
    path: "/detail/:id",
    name: "DatasetDetail",
    component: DatasetDetail,
    props: true // 将params.id作为props传入
  }
];

const router = createRouter({
  // history: createWebHistory(process.env.BASE_URL),  // publicBase; vue config为了走静态资源多了static,所以路由要调整base
  history: createWebHistory("/labDataset/"),
  routes,
});

export default router;
