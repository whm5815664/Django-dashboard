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
    // route level code-splitting
    // this generates a separate chunk (about.[hash].js) for this route
    // which is lazy-loaded when the route is visited.
    // component: () =>
    //   import(/* webpackChunkName: "about" */ "../views/About.vue"),
  },
];

const router = createRouter({
  history: createWebHistory(process.env.BASE_URL),
  routes,
});

export default router;
