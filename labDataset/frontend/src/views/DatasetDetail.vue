<template>
  <!-- 数据集详情页面 -->
  <div class="container">

    <!-- 上传信息+下载按钮 -->
    <div class="header">
      <div class="header-left">
        <p>{{ dataset.uploader }}</p>
        <p>{{ dataset.creationDate }}</p>
      </div>
      <div class="header-right">
        <el-button type="primary" class="btn-dark" @click="downloadDataset">
          <el-icon><Download/></el-icon>
          <span class="btn-text">下载(ZIP)</span>
        </el-button>
      </div>
    </div>

    <!-- 数据集标题 -->
    <div class="title">
      <div class="title-left">
        <div class="title-dataset">{{ dataset.name }}</div>
        <div class="title-desc">该数据集包含 {{ dataset.size }} 数据</div>
      </div>
      <div class="title-right">
        <img class="title-img" src="../assets/images/spectra-cover.png" />
      </div>
    </div>

    <!-- 分割线 -->
    <hr class="divider">

    <!-- 数据集信息 -->
    <div class="usage">
      <!-- 使用说明 -->
      <div class="usage-left">
        <h2>使用说明</h2>
        <div class="usage-content">
          <p><strong>关于数据集</strong></p>
          <p>详细信息1</p>
          <p>详细信息2</p>
          <!-- to do:这里的内容应该是自定义上传,考虑做一个markdown的上传 or 纯文本(定死格式 按json信息) + 加载更多button -->
        </div>
      </div>

      <!-- 基本属性 -->
      <div class="usage-right">
        <div class="usage-title">
          <h3>基本信息</h3>
          <p>{{ dataset.usage }}</p>
        </div>

        <div class="usage-title">
          <h3>标签</h3>
          <div class="tag-row">
            <button v-for="t in dataset.tags" :key="t.value" class="tag-btn" :class="{active:activeTag === t.value}" @click="activeTag=t.value">
            {{ t.label }}
            </button>
          </div>
        </div>
      </div>

    </div>

   <!-- 数据样例和数据集文件夹 -->
   <DatasetSample />
   
    <!-- <div class="sample">
      <div class="sample-left">
        <h3>数据样例</h3>
        <div class="sample-content">
          <p>Json格式</p>
        </div>
      </div>

      <div class="sample-right">
        <h3>文件目录</h3>
        <div class="sample-right-tree">
          <el-tree :data="dataset.fileTreeData" :props="defaultProps"></el-tree>
        </div>
      </div>
    </div> -->

  </div>
</template>
  
<script>
import {Download} from '@element-plus/icons-vue';
import DatasetSample from '@/components/DatasetSample.vue';

export default {
name: 'DatasetDetail',
components:{ Download, DatasetSample},
data() {
  return {
    dataset: {
      name: '柑橘近红外光谱数据',
      uploader: 'Uploader',
      creationDate: '2026-01-13',
      updateDate: '2026-01-13', // 更新时间
      coverImage: 'https://via.placeholder.com/300x200?text=Heart+Disease',
      usage: 'This data is used for detecting citrus = using various features.',
      description: 'This dataset contains various features related to citrus.',
      size: '1.26GB',
      format: 'CSV',
      fileTreeData: [
        { label: 'level one 1',
          children: [
            { label: 'level two 1-1',
              children: [
                { label: 'level three 1-1-1' },
                { label: 'level three 1-1-2' }
              ]
            },
            {
              label: 'level two 1-2',
              children: [
                { label: 'level three 1-2-1' },
                { label: 'level three 1-2-2' }
              ]
            },
          ]
        },
        { label: 'level one 2',
          children: [
            { label: 'level two 2-1',
              children: [
                { label: 'level three 2-1-1' },
                { label: 'level three 2-1-2' }
              ]
            },
          ]
        }
      ],
      tags: [
        { label: '近红外光谱', value: 'nir' },
        { label: '柑橘', value: 'citrus' },
        { label: 'label', value: 'value'},
      ],
    },
    defaultCover: 'https://via.placeholder.com/300x200?text=Dataset+Image', // 默认图片 
    defaultProps: {
      children:'children',
      label:'label'
    }  
  }
},
computed: {
  // to do:这里要补充一个页面加载即有的逻辑 获取id返回这个dataset
},
methods: {
  downloadDataset(){
    alert('点击此处下载数据集')
    // to do:补偿下载的逻辑
  }
}
}
</script>
  
<style scoped>
.container {
  padding:0 32px;  /* 左右边缘留白 */
  /* 控制子元素的间距，但是这样也算写死*/
  /* display: flex;
  flex-direction: column;
  gap: 20px; */
}

/* Header描述 */
.header {
  display: flex;
  align-items: baseline;  /* left和right对齐，center是居中对齐！ */
  margin-bottom: 20px;
}
.header-left {
  display: flex;
  flex:1;
  align-items: center;
  gap: 16px;
}
.header-left p{
  font-size:14px;
  color:#555;
  margin:0;
  line-height: 1;
}
.header-right{
  display:flex;
  align-items: center;
}
.btn-dark {
  background:#111;
  border-color:#111;
  padding: 10px 16px;  
  margin-top:16px;
  color: white;
  border-radius: 999px;
  font-size: 16px;
  display: flex;
  align-items: center;
  transition: background-color 0.3s ease;
}
.btn-dark:hover {
  background-color: #333;
}
.btn-text {
  margin-left: 2px;
}
/* 让图标看起来更粗 SVG矢量图形，不是字体图标，所以font-weight属性对SVG无效*/
.btn-dark :deep(.el-icon) svg {
  filter: 
    drop-shadow(0.5px 0 0 currentColor)   /* 右左下上延伸0.5px阴影=视觉上变粗1px */
    drop-shadow(-0.5px 0 0 currentColor)
    drop-shadow(0 0.5px 0 currentColor) 
    drop-shadow(0 -0.5px 0 currentColor);
}


/* Title描述 */
.title {
  border:1px solid #eee;
  border-radius:18px;
  padding:24px;
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:18px;
  background:#fff;
  margin-bottom:18px;  
  flex-wrap: nowrap; /** 小屏不换行 */
}
/* 避免left和right的width之和溢出容器：确保右侧可以缩+左侧可以换行 */
.title-left {
  flex:1 1 auto; /* 可以缩*/
  min-width: 0; 
}
.title-dataset{ 
  display: flex;
  font-size:34px;
  font-weight:700;
  margin-bottom:15px; 
}
.title-desc{
  display: flex;
  color:#555;
  line-height:1.5;
  margin-bottom:25px;   
}
.title-right{
  flex: 0 1 auto;
  min-width: 0;
  display:flex;
  justify-content:flex-end;
}
.title-img{
  width: clamp(140px, 22vw, 300px); /* 最小140，随屏幕变化，最大300 */
  height: auto;
  max-width: 100%;
  object-fit: contain;
}

.divider {
  border: none;
  height: 1.2px;
  background-color: #eee;
  margin: 20px 0; /* 控制上下间距 */
}



 /* 详细说明 */
.usage {
  display:flex;
  justify-content:space-between;
}
/* 左侧 */
.usage-left {
  flex:0.78;
  padding-left: 16px;
  background: #f9f9f9;
  border-radius: 8px;
}
.usage-left h2{
  text-align: left;
  margin-bottom: 12px;
}
.usage-content p {
  text-align: left;
  font-size: 16px;
  color: #333;
}
/* 右侧：基本信息和标签 */
.usage-right {
  flex: 0.2;  /* 占比*/
  padding-left: 16px;
  background: #f9f9f9;
  border-radius: 8px;
}
.usage-title h3 {
  text-align: left;
  margin-bottom: 12px;
}
.usage-title p {
  text-align: left;
  font-size: 16px;
  color: #555;
}
.tag-row {
  display:flex;
  flex-wrap:wrap;
  gap:10px;
}
.tag-btn{
  padding: 7px 12px;
  border:1px solid #ddd;
  border-radius:999px;
  background:#fff;
  cursor:pointer;
  font-size:13px;
}


/* 数据样例和数据集文件夹 */
.sample {
  display: flex;
  justify-content: space-between;
  margin-top: 20px;
}
.sample-left {
  flex: 0.78;
  padding-left: 16px;
  background: #f9f9f9;
  border-radius: 8px;
}
.sample-left h3 {
  text-align: left;
}
.sample-content p {
  text-align: left;
  font-size:  16px;
  color: #333
}

.sample-right {
  flex: 0.2;
  padding-left: 16px;
  background: #f9f9f9;
  border-radius: 8px;
  overflow: hidden; /* 隐藏溢出的部分,否则滑动的时候div就左加 */
}
.sample-right h3 {
  text-align: left;
}
.sample-right-tree {
  overflow-x: auto;
  overflow-y: auto;
  max-width: 400px;
}
.sample-right :deep(.el-tree) {
  background-color: #f9f9f9;
  border-radius: 8px;   
}
::v-deep .el-tree > .el-tree-node {
  min-width:100%;
  display:inline-block;
}
::v-deep .el-tree-node__content {
  padding-right: 16px; /* 增加节点内容右侧的内边距 */
}

/* to do:文件夹前面应该有图标，文件用csv或img*/
</style>