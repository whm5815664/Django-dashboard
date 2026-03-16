// dataset_list.js
document.addEventListener('DOMContentLoaded', function() {

    // ----------------------------
    // 全局变量替代 Vue data
    // ----------------------------
    let searchQuery = '';
    let dialogVisible = false;
    let fileList = [];
    let activeTag = 'all';
    let datasets = [];      // 如果 Django context 提供，可直接渲染
    let tags = [];          // 标签列表
    let tagOptions = [];    // 上传下拉标签

    // ----------------------------
    // DOM 元素
    // ----------------------------
    const searchInput = document.getElementById('searchInput');
    const openDialogBtn = document.getElementById('openCreateDialog');
    const closeDialogBtn = document.getElementById('closeDialog');
    const uploadDialog = document.getElementById('uploadDialog');
    const uploadForm = document.getElementById('uploadForm');
    const fileInput = document.getElementById('fileInput');

    // ----------------------------
    // 返回按钮
    // ----------------------------
    const backBtn = document.getElementById('backBtn');
    if (backBtn) {
        backBtn.addEventListener('click', function() {
            // 返回上一页 to do：合并后返回
            window.history.back();
        });
    }

    // ----------------------------
    // 弹窗事件
    // ----------------------------
    openDialogBtn.addEventListener('click', function() {
        console.log('点击上传按钮触发了吗');
        uploadDialog.style.display = 'flex';
    });
    closeDialogBtn.addEventListener('click', function() {
        uploadDialog.style.display = 'none';
        uploadForm.reset();
        fileList = [];
    });

    // ----------------------------
    // 搜索框过滤
    // ----------------------------
    searchInput.addEventListener('input', function() {
        const q = searchInput.value.toLowerCase();
        document.querySelectorAll('.list-card').forEach(card => {
            const name = card.querySelector('.ds-title').textContent.toLowerCase();
            const meta = card.querySelector('.ds-meta').textContent.toLowerCase();
            card.style.display = (name.includes(q) || meta.includes(q)) ? 'flex' : 'none';
        });
    });

    // ----------------------------
    // 标签点击筛选
    // ----------------------------
    document.querySelectorAll('.tag-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            activeTag = btn.dataset.tag;
            document.querySelectorAll('.tag-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            // 过滤列表
            document.querySelectorAll('.list-card').forEach(card => {
                const metaText = card.querySelector('.ds-meta').textContent;
                card.style.display = (activeTag === 'all' || metaText.includes(activeTag)) ? 'flex' : 'none';
            });
        });
    });

    // ----------------------------
    // 查看详情跳转
    // ----------------------------
    document.querySelectorAll('.detail-btn').forEach(btn => {
        console.log('detail btn url',btn.dataset.url);
        btn.addEventListener('click', function() {
            const url = btn.dataset.url
            if (url && url !== 'undefined') {
                window.location.href = url;
            } else {
                console.error('button dataset.url undefined', btn);
            }
        });
    });

    // ----------------------------
    // 文件选择更新 fileList
    // ----------------------------
    fileInput.addEventListener('change', function() {
        fileList = Array.from(fileInput.files);
        console.log("上传的所有文件:", fileList);
        fileList.forEach(f => console.log("文件名:", f.name, "相对路径:", f.webkitRelativePath || f.name));
    });

    // ----------------------------
    // 上传表单提交
    // ----------------------------
    uploadForm.addEventListener('submit', function(e) {
        e.preventDefault();

        const formData = new FormData(uploadForm);
        fileList.forEach(f => formData.append('file', f, f.webkitRelativePath || f.name));

        // 可选：清洗 tags
        const selectedTags = Array.from(uploadForm.elements['tags'].selectedOptions).map(opt => opt.value);
        formData.set('data_format', selectedTags.join(','));

        fetch('/datasets/upload/', {
            method: 'POST',
            body: formData
        })
        .then(res => res.json())
        .then(data => {
            alert("上传成功");
            uploadDialog.style.display = 'none';
            fileList = [];
            uploadForm.reset();
            location.reload();
        })
        .catch(err => {
            console.error(err);
            alert("上传失败");
        });
    });

    // ----------------------------
    // 工具方法: metaLine / statusLine
    // ----------------------------
    function metaLine(ds) {
        const owner = ds.creator || '创建人';
        const time = ds.created_at || '创建时间';
        return `${owner} · ${time}`;
    }

    function statusLine(ds) {
        const parts = [];
        if(ds.usability != null) parts.push(`Usability ${ds.usability}`);
        if(ds.file_count != null) parts.push(`${ds.file_count} File (CSV)`);
        if(ds.size) parts.push(ds.size);
        if(ds.downloads != null) parts.push(`${ds.downloads} downloads`);
        if(ds.notebooks != null) parts.push(`${ds.notebooks} notebooks`);
        return parts.length ? parts.join(' · ') : '共 xx 个文件（CSV）';
    }

    // ----------------------------
    // 可选: fetch datasets 和 tags
    // 如果 Django 已经通过 context 渲染，可省略
    // ----------------------------
    function fetchDatasets() {
        fetch('/datasets/api/')
            .then(res => res.json())
            .then(data => {
                datasets = data.results || [];
                // TODO: 动态渲染列表，如果不通过模板渲染
            })
            .catch(err => console.error(err));
    }

    function fetchTags() {
        fetch('/tags/api/')
            .then(res => res.json())
            .then(data => {
                tags = data.results || [];
                tagOptions = tags;
                // TODO: 动态更新下拉
            })
            .catch(err => console.error(err));
    }
    
    // ----------------------------
    // 动态渲染标签
    const tagRow = document.querySelector('.tag-row');

    // 创建“全部数据集”按钮
    const allBtn = document.createElement('button');
    allBtn.className = 'tag-btn active';
    allBtn.dataset.tag = 'all';
    allBtn.textContent = '全部数据集';
    allBtn.addEventListener('click', function() {
        activeTag = 'all';
        document.querySelectorAll('.tag-btn').forEach(b => b.classList.remove('active'));
        allBtn.classList.add('active');

        document.querySelectorAll('.list-card').forEach(card => card.style.display = 'flex');
    });
    tagRow.appendChild(allBtn);

    // 获取标签
    fetch('/labDataset/api/tags/')
        .then(res => res.json())
        .then(data => {
            const tags = data.results || [];
            tags.forEach(t => {
                const value = t.name;  
                const label = t.name;

                const btn = document.createElement('button');
                btn.className = 'tag-btn';
                btn.dataset.tag = value;
                btn.textContent = label;

                // 点击事件(绑定直接在创建按钮时):控制数据集card
                btn.addEventListener('click', function() {
                    activeTag = btn.dataset.tag;
                    document.querySelectorAll('.tag-btn').forEach(b => b.classList.remove('active'));
                    btn.classList.add('active');

                    document.querySelectorAll('.list-card').forEach(card => {
                        const tagText = card.querySelector('.ds-tags').textContent || '';
                        const tagsArray = tagText.split(',').map(t => t.trim());
                        card.style.display = (activeTag === 'all' || tagsArray.includes(activeTag)) ? 'flex' : 'none';
                    });
                });

                tagRow.appendChild(btn);
            });
        })
        .catch(err => console.error(err));

});