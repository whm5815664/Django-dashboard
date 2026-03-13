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

    <!-- 数据集列表 -->
    <div class="list-wrap">
      <div class="list-head">
          <div class="count">共有 {{ filteredDatasets.length }} 个数据集</div>
      </div>

      <div class="list-card" v-for="ds in filteredDatasets" :key="ds.id">
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
    <!-- to do: 文件上传功能暂定, 待最终部署到服务器换掉数据地址 -->
    <el-dialog v-model="dialogVisible" width="500px" @close="closeDialog">
      <div class="upload-container">
        <div class="upload-content">

          <el-form :model="form" label-width="90px" class="dataset-form">
            <el-form-item label="Name" required>
              <el-input v-model="form.name" placeholder="请输入数据集名称"/>
            </el-form-item>

            <el-form-item label="creator" required>
              <el-input v-model="form.creator" placeholder="请输入数据集创建人"/>
            </el-form-item>

            <el-form-item label="description" required>
              <el-input v-model="form.description" 
                        type="textarea" 
                        :rows="3"
                        placeholder="请输入数据集相关描述信息"/>
            </el-form-item>

            <el-form-item label="storage_url" required>
              <el-input v-model="form.storage_url" placeholder="请输入数据集所在地址"/>
            </el-form-item>

            <el-form-item label="tags" required>
              <el-select
                v-model="form.tags"
                multiple
                filterable
                allow-create
                default-first-option
                placeholder="选择已有标签，或输入新标签回车创建"
                style="width: 100%;"
              >
                <el-option v-for="t in tagOptions" :key="t.value" :label="t.label" :value="t.value"/>
              </el-select>

              <div style="margin-top: 6px; font-size: 12px; color: #888;">
                提示：可输入新标签并回车；多个标签会用英文逗号保存
              </div>
            </el-form-item>
          </el-form>

          <p class="upload-title">拖拽或选择文件到此处上传</p>
          <p class="upload-description">建议将大文件夹压缩为 zip 文件以加快上传速度</p>
          <!-- 文件选择框 --> <!-- auto-upload 禁止自动上传，用户点击上传按钮后手动触发 -->
          <el-upload 
            class="upload-demo" 
            drag
            multiple
            name="file"
            :file-list="fileList"
            :on-preview="handlePreview"
            :on-remove="handleRemove"  
            :before-upload="beforeUpload"
            :auto-upload="false" 
            :directory="true"
            :webkitdirectory="true"
            @change="handleChange"
          >
            <el-icon class="el-icon--upload"><upload-filled /></el-icon>
            <div>将文件拖拽到此处或者 <em>点击上传</em></div>
          </el-upload>
        </div>
      </div>

      <template #footer>
        <div class="dialog-footer">
          <el-button @click="closeDialog">取消</el-button>
          <el-button type="primary" @click="uploadDataset">上传</el-button>
        </div> 
      </template>
    </el-dialog>


  </div>
</template>
  
<script>
import {Search, UploadFilled} from '@element-plus/icons-vue'
import { createDataset } from '../models/dataset'
import { parseTags } from '../utils/tags'
import { formatTime } from '../utils/time'

export default {
name: 'DatasetList',
components: {Search,UploadFilled},
data() {
  return {
    searchQuery: '',  // 搜索字段
    dialogVisible: false, //上传弹窗控制显示
    fileList: [], // 上传文件
    form:{  // 数据集上传表单
      name:'',
      creator:'',
      description:'',
      storage_url:'',
      tags: []
    },
    activeTag: "all", // 当前选中标签
    tags: [{label:"全部数据集", value: "all"}], // 标签
    tagOptions: [], // 上传标签的选择下拉列表
    categories: [
      { id: 'all', name: '全部' },
      { id: 'image', name: '图像' },
      { id: 'text', name: '文本' },
      { id: 'mixed', name: '混合' }
    ],
    datasets: [],
    // datasets: [
    //   {
    //   id: 1,
    //   name: '心脏MRI图像数据集',
    //   description: '包含100例患者的心脏MRI扫描图像，用于心室分割研究。',
    //   cover: 'https://via.placeholder.com/300x200?text=MRI',
    //   tags: ['JPG', '医学影像', 'MRI'],
    //   updateTime: '2024-05-20',
    //   fileCount: 1200,
    //   category: 'image'
    //   },
    //   {
    //   id: 2,
    //   name: '肝脏MRI图像数据集',
    //   description: '包含100例患者的xxx。',
    //   cover: 'https://via.placeholder.com/300x200?text=MRI',
    //   tags: ['JPG', '医学影像', 'MRI'],
    //   updateTime: '2024-05-20',
    //   fileCount: 1200,
    //   category: 'image'
    //   },
    //   {
    //   id: 3,
    //   name: '肝脏MRI图像数据集',
    //   description: '包含100例患者的xxx。',
    //   cover: 'https://via.placeholder.com/300x200?text=MRI',
    //   tags: ['JPG', '医学影像', 'MRI'],
    //   updateTime: '2024-05-20',
    //   fileCount: 1200,
    //   category: 'image'
    //   },
    //   {
    //   id: 4,
    //   name: '肝脏MRI图像数据集',
    //   description: '包含100例患者的xxx。',
    //   cover: 'https://via.placeholder.com/300x200?text=MRI',
    //   tags: ['JPG', '医学影像', 'MRI'],
    //   updateTime: '2024-05-20',
    //   fileCount: 1200,
    //   category: 'image'
    //   },
    // ]
  }
},
computed: {
  // 数据集过滤: 完善Tag和搜索框的筛选功能
  filteredDatasets() {
    let filtered = this.datasets;

    // 根据搜索框过滤
    const q = (this.searchQuery || "").trim();
    if (q) {
        filtered = filtered.filter(ds => 
          (ds.name || "").includes(q) ||
          (ds.description || "").includes(q) ||
          (ds.creator || "").includes(q)
        );
    }

    // 根据Tag过滤
    if (this.activeTag !== 'all' && this.activeTag) {
        filtered = filtered.filter(ds => {
          // 判断某dataset是否包含activeTag
          const tags = parseTags(ds.data_format).map(t => t.value);
          return tags.includes(this.activeTag);
        })
    }
    return filtered;
  }
},
mounted() {
  // 当detail点击标签返回到list页面时
  const tag = this.$route.query.tag
  if (tag) this.activeTag = tag

  this.getDatasets(); // 组件挂载时获取数据集列表信息
  this.getTags();
},
watch: {
  // 监听路由query的变化
  "$route.query.tag": {
    immediate: true,  // 第一次进list即生效
    handler(tag) {
      this.activeTag = tag || ""
    }
  }
},
methods: {
  formatTime,
  openCreateDialog(){
    this.dialogVisible = true;
  },
  closeDialog(){
    this.dialogVisible = false;
    // 关闭时清空表单
    this.form = {name:'',creator:'',description:'',storage_url:'',tags:[]};
    this.fileList = [];
  },
  handlePreview(file) {
    console.log('预览文件:', file);
  },
  // 移除此前上传文件
  handleRemove(file, fileList) {
    console.log('移除文件:', file);
    this.fileList = fileList.slice();
  },
  beforeUpload(file) {
    console.log("准备上传文件:",file);
    return true;  // 接受文件
  },
  // 上传数据集:处理fileList
  handleChange(file, fileList){
    // 更新 filelist
    this.fileList = fileList.slice();
    console.log("上传的所有文件:", fileList);

    this.fileList.forEach(f => console.log("文件名:", f.name, "相对路径:", f.webkitRelativePath || f.name));

  },
  // 跳转到对应详情页
  goToDetail(id) {
    this.$router.push({ name: 'DatasetDetail', params: { id:id } })
  },
  // 作者 · 更新时间
  metaLine(ds) {
    const owner = ds.creator || '创建人'
    const time = this.formatTime(ds.created_at) || '创建时间'
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
  },


  /**
   * To do: Apifox测试完全部数据接口之后，要将上面的数组全部置空，替换为下列API
   */
  // 获取全部数据集
  async getDatasets(){
    try{
      const res = await this.$api.get('datasets/');
      const results = res.data.results || []; // 处理数组
      this.datasets = results.map(item => ({
        ...createDataset(),
        ...item
      }))
    }catch(error){
      console.error("获取实验室数据集失败",error);
      this.datasets = [];
    }
  },
  // 获取数据集标签
  async getTags(){
    try{
      const res = await this.$api.get('tags/');
      const results = res.data.results || []; 
      // 1、list页更新tags
      this.tags = [
        { label:"全部数据集", value: "all" },
        ...results.map(t => ({
          label: t.name,
          value: t.name,
        }))
      ];

      // 2、更新上传表单下拉列表tags
      this.tagOptions = results.map( t=> ({
        label: t.name,
        value: t.name,
      }))

    }catch(error){
      console.error("获取tags失败",error);
      this.tags = [{label:"全部数据集", value: "all"}];
    }
  },
  // 提交按钮: 新数据集信息 
  async uploadDataset() {
    try{
      // 清洗本次上传tags：空格、重复
      const cleanedTags = Array.from(new Set(
        (this.form.tags || []).map(s => String(s).trim()).filter(Boolean)
      ))
      // 新增的tags
      const existingSet = new Set((this.tagOptions || []).map(t => t.value));
      const newTags = cleanedTags.filter(t => !existingSet.has(t));
      // 新增 => Tag表
      if(newTags.length>0){
        await this.$api.post("tags/", {names: newTags});
        await this.getTags(); // 写入后刷新 标签和下拉列表
      }

      const dsInfo = {
        name: this.form.name,
        description: this.form.description,
        creator: this.form.creator,
        storage_url: this.form.storage_url,
        data_format: cleanedTags.join(","),
      };

      // to do: 文件上传功能完成后，待整合
      // 实现文件上传功能
      let formData = new FormData();

      // 字段名:"file"
      this.fileList.forEach(f => formData.append("file", f.raw, f.webkitRelativePath || f.name));

      formData.append("name", dsInfo.name);
      formData.append("description", dsInfo.description);
      formData.append("creator", dsInfo.creator);
      formData.append("storage_url", dsInfo.storage_url);
      formData.append("data_format", dsInfo.data_format);
      
      // 调用后端接口进行上传
      await this.$api.post("datasets/", formData);
      this.$message.success("所有文件上传成功！");

      this.$message.success("数据集信息上传成功!");
      this.closeDialog(); // 关闭弹窗
      this.getDatasets(); // 刷新
      this.getTags();
    }catch(error){
      console.error("上传失败:", error?.response?.data || error);
      this.$message.error(error?.response?.data?.msg || "上传失败");
    }  
  },

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