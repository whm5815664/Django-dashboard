document.addEventListener('DOMContentLoaded', function(){

    const downloadBtn = document.getElementById('downloadDataset');
    const tagBtns = document.querySelectorAll('.tag-btn');


    // 格式化时间函数
    function formatTime(datetimeStr){
        if(!datetimeStr) return '';
        const d = new Date(datetimeStr);
        return d.toLocaleString();
    }

    // 下载数据集
    if(downloadBtn){
        downloadBtn.addEventListener('click', function(){
            const datasetId = downloadBtn.dataset.id;
            if(!datasetId){
                alert('数据集ID不存在');
                return;
            }
            // 显示加载状态
            downloadBtn.disabled = true;
            downloadBtn.textContent = '下载中...';
            
            fetch(`/labDataset/api/datasetFile/${datasetId}/`, {
                method:'GET',
                headers: {
                    'Accept': 'application/zip'
                }
            })
                .then(res => {
                    if(!res.ok){
                        throw new Error(`下载失败: ${res.status} ${res.statusText}`);
                    }
                    // 检查Content-Type
                    const contentType = res.headers.get('content-type');
                    if(!contentType || !contentType.includes('application/zip')){
                        console.warn('响应类型可能不正确:', contentType);
                    }
                    return res.blob();
                })
                .then(blob => {
                    // 验证blob大小
                    if(blob.size === 0){
                        throw new Error('下载的文件为空');
                    }
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `dataset_${datasetId}.zip`;
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    window.URL.revokeObjectURL(url);
                })
                .catch(err => { 
                    console.error('下载错误:', err); 
                    alert('下载失败: ' + err.message); 
                })
                .finally(() => {
                    // 恢复按钮状态
                    downloadBtn.disabled = false;
                    downloadBtn.innerHTML = '<span class="btn-text">下载(ZIP)</span>';
                });
        });
    }

    // 标签跳转
    tagBtns.forEach(btn => {
        btn.addEventListener('click', function(){
            const tagValue = btn.dataset.tag;
            window.location.href = `/datasets/?tag=${tagValue}`;
        });
    });

});