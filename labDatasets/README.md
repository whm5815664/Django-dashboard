# labDatasets - 实验室数据集管理应用

这是一个集成 Vue.js 前端应用的 Django 应用。

## 项目结构

```
labDatasets/
├── __init__.py          # Django 应用初始化文件
├── apps.py              # Django 应用配置
├── models.py            # 数据模型（待扩展）
├── views.py             # 视图函数
├── urls.py              # URL 路由配置
├── admin.py             # Django 管理后台配置
├── tests.py             # 测试文件
├── migrations/          # 数据库迁移文件
├── templates/           # Django 模板
│   └── labDatasets/
│       └── index.html   # Vue 应用入口页面
└── lab_data/            # Vue.js 前端项目
    ├── src/             # Vue 源代码
    ├── public/           # 公共资源
    └── package.json     # Node.js 依赖配置
```

## 使用说明

### 1. 开发模式（推荐）

在开发时，可以同时运行 Django 和 Vue 开发服务器：

**终端 1 - Django 服务器：**
```bash
python manage.py runserver
```

**终端 2 - Vue 开发服务器：**
```bash
cd labDatasets/lab_data
npm install  # 首次运行需要安装依赖
npm run serve
```

然后访问：`http://127.0.0.1:8000/labDatasets/`

### 2. 生产模式

在生产环境中，需要先构建 Vue 应用，然后将构建后的静态文件集成到 Django 中：

**步骤 1：构建 Vue 应用**
```bash
cd labDatasets/lab_data
npm install
npm run build
```

**步骤 2：复制构建文件到 Django 静态文件目录**

构建后的文件在 `labDatasets/lab_data/dist/` 目录下，需要：
1. 将 `dist/index.html` 的内容更新到 `labDatasets/templates/labDatasets/index.html`（或使用模板变量）
2. 将 `dist/` 目录下的所有静态文件（js、css、img 等）复制到 `labDatasets/static/labDatasets/` 目录

**步骤 3：收集静态文件**
```bash
python manage.py collectstatic
```

## URL 路由

- 主入口：`/labDatasets/`
- Vue Router 的所有路由都会通过 Django 视图转发，支持 Vue Router 的 history 模式

## 注意事项

1. Vue 应用使用 Vue Router 的 history 模式，需要 Django 后端支持所有路由的转发
2. 如果 Vue 应用需要调用 Django API，可以使用 Django REST Framework
3. 静态文件路径需要正确配置，确保 Vue 构建后的资源可以正确加载

