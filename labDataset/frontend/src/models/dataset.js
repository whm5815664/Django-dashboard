// 前段契约:定义期望的数据结构   
// src/models/dataset.js
export function createDataset() {
    return {
      id: null,
      name: "",
      description: "",
      creator: "",       // 创建人
      cover: "",         // 封面URL（现在是空字符串也没问题）
      data_format: "",   // 例如：结构化数据、图像...
      file_count: 0,     // 文件数量
      size: 0,          
      storage_url: "",   // 服务器目录
      created_at: "",
      updated_at: "",
  
      // 给前端展示用的“别名字段”（不影响后端字段）
      // metaLine/statusLine 用起来更直观
      get author() {
        return this.creator
      },
      get url() {
        return this.storage_url
      }
    }
}
  