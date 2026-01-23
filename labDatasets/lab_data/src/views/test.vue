<template>
  <div class="dataset-detail">
    <!-- 顶部数据集信息 -->
    <div class="dataset-header">
      <h2>心脏MRI数据集</h2>
      <button>下载全部</button>
    </div>
    
    <!-- 主内容区：文件树 + 预览 -->
    <div class="content-area">
      <!-- 左侧文件树 -->
      <div class="file-tree-panel">
        <div class="tree-header">文件结构</div>
        <ul class="file-tree">
          <li @click="selectFile('images/')" :class="{active: selectedPath==='images/'}">
            📁 images/
          </li>
          <li @click="selectFile('images/sample1.jpg')" 
              :class="{active: selectedPath==='images/sample1.jpg'}">
            &nbsp;&nbsp;📄 sample1.jpg
          </li>
          <li @click="selectFile('data/data.csv')" 
              :class="{active: selectedPath==='data/data.csv'}">
            📁 data/
          </li>
          <li @click="selectFile('README.md')" 
              :class="{active: selectedPath==='README.md'}">
            📄 README.md
          </li>
        </ul>
      </div>
      
      <!-- 右侧预览区 -->
      <div class="preview-panel">
        <div v-if="selectedPath.endsWith('.jpg')" class="image-preview">
          <img src="https://example.com/sample.jpg" alt="预览">
          <div class="image-info">sample1.jpg - 2.3MB</div>
        </div>
        
        <div v-else-if="selectedPath.endsWith('.csv')" class="csv-preview">
          <table>
            <tr><th>ID</th><th>Name</th><th>Value</th></tr>
            <tr><td>1</td><td>Sample1</td><td>0.23</td></tr>
            <tr><td>2</td><td>Sample2</td><td>0.45</td></tr>
          </table>
        </div>
        
        <div v-else-if="selectedPath.endsWith('.md')" class="text-preview">
          <h3>数据集说明</h3>
          <p>这是一个心脏MRI数据集...</p>
        </div>
        
        <div v-else class="default-preview">
          <p>选择左侧文件查看预览</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  data() {
    return {
      selectedPath: 'README.md' // 默认选中README
    }
  },
  methods: {
    selectFile(path) {
      this.selectedPath = path
    }
  }
}
</script>