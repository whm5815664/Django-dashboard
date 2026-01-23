<template>
  <!-- 数据集总览页面 -->
  <div class="container">
    <!-- 总标题描述+新增按钮+图片 -->
    <div class="title">
      <div class="title-left">
          <div class="title-dataset">实验室数据集</div>
          <div class="title-desc">查询、使用和上传数据集</div>
          <div class="new-btn">
              <el-button type="primary" class="btn-dark" @click="openCreateDialog">+ 上传数据集</el-button>
          </div>
      </div>

      <div class="title-right">
          <img class="title-img" src="../assets/images/spectra-cover.png" />
      </div>
    </div>

    <!-- 搜索 -->
    <div class="search-bar">
      <el-input v-model="searchQuery" placeholder="Search" class="search-input" size="large">
          <template #prefix>
              <el-icon><Search /></el-icon>
          </template>
      </el-input>
    </div>

    <!-- Tag 筛选 -->
    <div class="tag-row">
      <button v-for="t in tags" :key="t.value" class="tag-btn" :class="{active:activeTag === t.value}" @click="activeTag=t.value">
          {{ t.label }}
      </button>
    </div>

    <!-- 数据集List -->
    <div class="list-wrap">
      <div class="list-head">
          <div class="count">共有 {{ datasets.length }} 个数据集</div>
      </div>

      <div class="list-card" v-for="ds in datasets" :key="ds.id">
          <div class="card-left">
              <img src="../assets/images/spectra-cover.png"/>
          </div>

          <div class="card-mid">
              <div class="ds-title-row"><div class="ds-title" :title="ds.name">{{ ds.name }}</div></div>
              <div class="ds-meta" :title="metaLine(ds)"> {{ metaLine(ds) }}</div>
              <div class="ds-status" :title="statusLine(ds)"> {{ statusLine(ds) }}</div>
          </div>
          <div class="list-right">
              <el-button class="detail-btn" @click="goToDetail(ds.id)">查看详情</el-button>
          </div>
      </div>
    </div>

    <!-- 上传 弹窗 -->
    <el-dialog v-model="dialogVisible" width="500px" @close="closeDialog">
      <div class="upload-container">
        <div class="upload-content">
          <p class="upload-title">拖拽文件到此处上传</p>
          <p class="upload-description">建议将大文件夹压缩为 zip 文件以加快上传速度</p>
          <el-upload class="upload-demo"
            action="/upload"  
            drag
            list-type="picture-card"
            :on-preview="handlePreview"
            :on-remove="handleRemove"
            :before-upload="beforeUpload"
            :file-list="fileList"
          >
            <el-icon class="el-icon--upload"><upload-filled /></el-icon>
          </el-upload>
        </div>
      </div>

      <template #footer>
        <div class="dialog-footer">
          <el-button @click="closeDialog">取消</el-button>
          <el-button type="primary" @click="uploadFiles">上传</el-button>
        </div> 
      </template>
    </el-dialog>


  </div>
</template>
  
<script>
import {Search, UploadFilled} from '@element-plus/icons-vue'

export default {
name: 'DatasetList',
components: {Search,UploadFilled},
data() {
  return {
    searchQuery: '',
    activeCategory: 'all',
    dialogVisible: false, //上传弹窗控制显示
    fileList: [],
    tags: [
      { label: '全部数据集', value: 'all'},
      { label: '计算机视觉', value: 'cs' },
      { label: '近红外光谱', value: 'nir' },
      { label: '柑橘', value: 'citrus' },
      { label: 'Classification', value: 'cls' },
      { label: 'Computer Vision', value: 'cv' },
      { label: 'NLP', value: 'nlp' },
      { label: 'Data Visualization', value: 'viz' },
      { label: 'Pre-Trained Model', value: 'ptm' }
    ],
    categories: [
      { id: 'all', name: '全部' },
      { id: 'image', name: '图像' },
      { id: 'text', name: '文本' },
      { id: 'mixed', name: '混合' }
    ],
    datasets: [
      {
      id: 1,
      name: '心脏MRI图像数据集',
      description: '包含100例患者的心脏MRI扫描图像，用于心室分割研究。',
      cover: 'https://via.placeholder.com/300x200?text=MRI',
      tags: ['JPG', '医学影像', 'MRI'],
      updateTime: '2024-05-20',
      fileCount: 1200,
      category: 'image'
      },
      {
      id: 2,
      name: '肝脏MRI图像数据集',
      description: '包含100例患者的xxx。',
      cover: 'https://via.placeholder.com/300x200?text=MRI',
      tags: ['JPG', '医学影像', 'MRI'],
      updateTime: '2024-05-20',
      fileCount: 1200,
      category: 'image'
      },
      {
      id: 3,
      name: '肝脏MRI图像数据集',
      description: '包含100例患者的xxx。',
      cover: 'https://via.placeholder.com/300x200?text=MRI',
      tags: ['JPG', '医学影像', 'MRI'],
      updateTime: '2024-05-20',
      fileCount: 1200,
      category: 'image'
      },
      {
      id: 4,
      name: '肝脏MRI图像数据集',
      description: '包含100例患者的xxx。',
      cover: 'https://via.placeholder.com/300x200?text=MRI',
      tags: ['JPG', '医学影像', 'MRI'],
      updateTime: '2024-05-20',
      fileCount: 1200,
      category: 'image'
      },
    ]
  }
},
computed: {
  // to do：完善Tag、筛选按钮和搜索框的筛选功能
  filteredDatasets() {
    let filtered = this.datasets
    // 根据搜索框过滤
    if (this.searchQuery) {
        filtered = filtered.filter(dataset => 
        dataset.name.includes(this.searchQuery) || 
        dataset.description.includes(this.searchQuery)
        )
    }
    // 根据分类过滤
    if (this.activeCategory !== 'all') {
        filtered = filtered.filter(dataset => dataset.category === this.activeCategory)
    }
    return filtered
  }
},
methods: {
  openCreateDialog(){
    this.dialogVisible = true;
  },
  closeDialog(){
    this.dialogVisible = false;
  },
  handlePreview(file) {
    console.log('Previewing', file);
  },
  handleRemove(file, fileList) {
    console.log('Removed file', file);
    this.fileList = fileList;
  },
  beforeUpload(file) {
    const isCSV = file.type === 'text/csv';
    if (!isCSV) {
      this.$message.error('只能上传CSV文件!');
    }
    return isCSV;
  },
  uploadFiles() {
    // 执行上传文件的逻辑
    this.$message.success('上传成功');
    this.closeDialog(); // 上传成功后关闭弹窗
  },
  goToDetail(id) {
    alert('跳转到该数据集的详情页')
    this.$router.push({ name: 'DatasetDetail', params: { id } })
  },
  metaLine(ds) {
    // 作者 · 更新时间
    const owner = ds.owner || '创建人'
    const time = ds.updateTime || '创建时间'
    return `${owner} · ${time}`
  },
  statusLine(ds) {
    // 统计行
    const parts = []
    if (ds.usability != null) parts.push(`Usability ${ds.usability}`)
    if (ds.fileCount != null) parts.push(`${ds.fileCount} File (CSV)`)
    if (ds.size) parts.push(ds.size)
    if (ds.downloads != null) parts.push(`${ds.downloads} downloads`)
    if (ds.notebooks != null) parts.push(`${ds.notebooks} notebooks`)
    return parts.length ? parts.join(' · ') : '共 xx 个文件（CSV）'  
  }

}
}
</script>
  
<style scoped>
.container {
    padding:0 32px;  /* 左右边缘留白 */
}

/* 标题描述 */
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
.new-btn{
  display:flex;
  gap:12px;
  align-items:center;
}
.btn-dark {
  background:#111;
  border-color:#111;
  border-radius:999px;
  padding: 10px 16px;  
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

  

/* 搜索框 */
.search-bar {
    margin: 16px 0;
}
.search-input :deep(.el-input__wrapper) {
  border-radius: 999px;
  padding: 0 22px;
}

.search-input :deep(.el-input__inner) {
  height: 50px;          /* 输入框高度 */
  line-height: 50px;
  font-size: 16px;
}



/* Tag */
.tag-row{
  display:flex;
  flex-wrap:wrap;
  gap:10px;
  margin-bottom:18px;
}
.tag-btn{
  padding: 7px 12px;
  border:1px solid #ddd;
  border-radius:999px;
  background:#fff;
  cursor:pointer;
  font-size:13px;
}


/* 数据集卡片 */
.list-wrap{
  margin-top: 8px;
}
.list-head{
  display:flex;
  align-items:center;
  justify-content:space-between;
  margin-bottom:10px;
}
.count {
  color:#333;
  font-weight:600;
}
/* 单条卡片：一行布局，不换行 */
.list-card{
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:14px;
  padding: 14px 10px;
  border-bottom: 1px solid #eee;
}
/* 左侧封面 */
.card-left{
  flex: 0 0 auto;
  width: 96px;
  height: 64px;
  border-radius: 12px;
  overflow:hidden;
  background:#f6f6f6;
}
.card-left img{
  width:100%;
  height:100%;
  object-fit: cover;
}
/* 中间信息：纵向排列 flex+左对齐 */
.card-mid{
  flex: 1 1 auto;
  min-width: 0; 
  display: flex;
  flex-direction:column;
  align-items:flex-start;
}
.ds-title-row{
  display:flex;
  align-items:center;
  gap:10px;
  margin-bottom: 4px;
}
.ds-title{
  font-size: 18px;
  font-weight: 700;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.ds-meta{
  color:#333;
  font-size: 14px;
  margin-bottom: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.ds-status{
  color:#555;
  font-size: 13px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
/* 右侧固定区 */
.ds-right{
  flex: 0 0 auto;
  display:flex;
  align-items:flex-end;
  flex-direction: column;
  gap: 8px;
  min-width: 140px;
}
.detail-btn{
  border-radius: 999px;
  padding: 8px 14px;
}
/* 窄屏适配：保持同一行，不让图片/右侧掉下去 */
@media (max-width: 860px){
  .ds-cover{ width: 84px; height: 56px; }
  .ds-side{ min-width: 120px; }
  .ds-title{ font-size: 16px; }
}


/* 上传弹窗 */
.upload-container {
  display: flex;
  justify-content: center;
  align-items: center;
  flex-direction: column;
}


/* 标题样式 */
.dialog-header {
  display: flex;
  justify-content: center;
  align-items: center;
}

.upload-title {
  font-size: 20px;
  font-weight: bold;
}
.upload-description {
  color: #666;
  margin-bottom: 20px;
}
.upload-demo {
  padding: 40px;
  text-align: center;
  border: 2px dashed #ddd;
  background-color: #f9f9f9;

}
.dialog-footer {
  display: flex;
  justify-content: center;
  gap: 12px;
}
.dialog-footer :deep(.el-button) {
  width: 100px;
}
</style>