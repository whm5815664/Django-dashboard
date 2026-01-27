<template>
    <!-- 数据集预览信息 -->
    <div class="dataset">
        <!-- 文件树 + 预览 -->

        <!-- 左侧预览区 -->
        <div class="preview-panel">
            <h3>文件预览</h3>

            <div class="preview-content">
                <!-- 图片预览 -->
                <div v-if="previewType === 'image'">
                    <img :src="previewData" class="image-preview" />
                </div>

                <!-- Json预览 -->
                <div v-if="previewType === 'json'">
                    <pre>{{ jsonData }}</pre>
                </div>

                <!-- CSV预览 -->
                <div v-if="previewType === 'csv'">
                    <table v-if="csvData.length > 0">
                        <thead>
                        <tr>
                            <th v-for="(header, index) in csvData[0]" :key="index">{{ header }}</th>
                        </tr>
                        </thead>

                        <tbody>
                        <tr v-for="(row, rowIndex) in csvData.slice(1)" :key="rowIndex">
                            <td v-for="(cell, cellIndex) in row" :key="cellIndex">{{ cell }}</td>
                        </tr>
                        </tbody>
                    </table>
                    <p v-if="csvData.length === 0">CSV 文件暂无预览数据</p>
                </div> 
                
                <!-- 其他类型的文件预览 -->
                <div v-if="previewType === 'other'">
                    <p>无法预览该文件类型</p>
                </div>
            </div>
        </div>

        <!-- 右侧文件树 -->
        <div class="file-tree-panel">
            <h3>文件目录</h3>
            <div>
            <el-tree :data="fileTreeData" :props="fileTreeProps" @node-click="handleFileClick"></el-tree>
            </div>
        </div>

    </div>
</template>
    
<script>
export default {
name: 'DatasetSample',
data() {
    return{
        // 文件树数据
        fileTreeData:[],
        // 文件树节点的属性   props和fileData结构匹配
        fileTreeProps: {
            children: 'children',
            label: 'label'
        },
        // 当前预览data
        previewData: null,
        previewType: '',
        csvData:[],
        jsonData:null
    }
},
mounted() {
    console.log('触发文件数据获取前xxxxxxxxxxxxxxxxxxxxxxxxxxx');
    this.loadFileTree();
    console.log('成功获取文件数据xxxxxxxxxxxxxxxxxxxxxxxxxxx');
    console.log('数据fileTreeData: ',this.fileTreeData); // 检查是否成功加载文件
},
methods: {
    // 1、获取文件树数据
    loadFileTree(){
        // to do:后端api调用 axios.get('')
        const context = require.context('../assets/data/', true, /.*\.(csv|json|png|jpg|jpeg)$/);
        console.log('找到文件列表前xxxxxxxxxxxxxxxxxxx');
        const files = context.keys();
        console.log('找到文件列表',files);

        this.fileTreeData = this.transformToFileTree(context.keys(), context);
        // 保证数据加载后再渲染
        this.$nextTick( () => {
            console.log('文件数据更新完成:',this.fileTreeData);
        })
    },
    // 2、文件转换为树结构
    transformToFileTree(files, context){
        // to do 后端api调用 axios.get('')
        console.log('开始转换文件树...');
        const tree = [];
        files.forEach((file,index) => {
            console.log(`\n--- 处理第${index + 1}个文件 ---`);
            console.log('原始file路径:', file);

            // ./images/spectra.png
            const path = file.replace('./', '').split('/');
            console.log('分割后path:', path);

            const fileName = path.pop();
            const fileType = fileName.split('.').pop();
            console.log(`文件名：${fileName}, 文件类型: ${fileType}`);

            let currentDir = tree;
            path.forEach((folder, folderIndex) => {
                console.log(`处理第 ${folderIndex+1} 层: ${folder}`)
                let folderNode = currentDir.find(node => node.label === folder);
                if (!folderNode) {
                    console.log(`新文件夹:${folder}`)
                    folderNode = { label: folder, children: [], type:'folder' };
                    currentDir.push(folderNode);
                }
                currentDir = folderNode.children;
            });

            currentDir.push({ label: fileName, type: fileType, previewUrl: context(file)});
        });

        console.log('文件树结果:', tree);
        return tree;
    },
    // 3、文件结点 点击加载
    handleFileClick(node){
        const fileType = node.type;
        const previewUrl = node.previewUrl;
        this.previewData = previewUrl; 

        // 判断文件类型是否为图片
        const imageTypes = ['png', 'jpg', 'jpeg', 'gif']; 
        const isImage = imageTypes.includes(fileType.toLowerCase()); 

        if (isImage) {
            this.previewType = 'image'; 
        } else {
            this.previewType = fileType;
        }


        if(fileType === 'csv'){
            this.loadCsvData(previewUrl);
        }else if (fileType === 'json'){
            this.loadJsonData(previewUrl);
        }else if(isImage){
            this.previewType = 'image';
        }else{
            this.previewType = 'other'
        }
    },
    // CSV
    loadCsvData(url){
        alert(url)
        // to do(后端访问调整逻辑 不能把数据全部存在前端js)  axios.get(url).then
        // axios.get(url).then(response => {
        //     this.csvData = this.parseCsv(response.data);
        // }).catch(error => {
        //     console.error('CSV文件加载失败:', error);
        // });
    },
    // CSV解析
    parseCsv(csvText){
        const rows = csvText.split('\n');
        return rows.map(row => row.split(','))
    },
    // Json
    loadJsonData(url){
        alert(url)
        // to do axios.get(url).then(response => {this.jsonData=response.data}).catch(error=>{console.log("JSON加载失败",error)});
        // axios.get(url).then(response => {
        //     this.jsonData = response.data;
        // }).catch(error => {
        //     console.error('JSON文件加载失败:', error);
        // });
    },




}
}
</script>

<style scoped>
.dataset {
  display: flex;
  justify-content: space-between;
  padding: 20px;
}

.preview-panel {
  width: 60%;
  padding-right: 20px;
}

.file-tree-panel {
  width: 35%;
}

.preview-panel h3, .file-tree-panel h3 {
  font-size: 20px;
  margin-bottom: 20px;
}

.preview-content {
  overflow-x: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
}

th, td {
  padding: 8px;
  border: 1px solid #ddd;
  text-align: left;
}

th {
  background-color: #f4f4f4;
}

.image-preview {
  max-width: 100%;
  max-height: 400px;
}

pre {
  background-color: #f9f9f9;
  padding: 20px;
  border: 1px solid #ddd;
  white-space: pre-wrap;
  word-wrap: break-word;
}
</style>