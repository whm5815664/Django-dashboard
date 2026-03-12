<template>
  <div>
    <div id="nav">
      <router-link to="/">DatasetList</router-link> |
      <router-link to="/detail">DatasetDetail</router-link>
    </div>
    <router-view />
  </div>

</template>

<script>


export default {
  mounted(){
    this.getToken();
  },
  methods: {
    async getToken(){
      try{
        await this.$api.get("csrf/");
      }catch(error){
        console.log("获取CSRF token失败", error);
      }  
    }
  }
}
</script>


<style lang="scss">
#app {
  font-family: Avenir, Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-align: center;
  color: #2c3e50;
}

#nav {
  padding: 30px;

  a {
    font-weight: bold;
    color: #2c3e50;

    &.router-link-exact-active {
      color: #42b983;
    }
  }
}
</style>
