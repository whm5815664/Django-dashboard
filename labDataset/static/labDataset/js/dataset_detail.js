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
            fetch(`/datasetFile/${datasetId}/`, {method:'GET'})
                .then(res => res.blob())
                .then(blob => {
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `dataset_${datasetId}.zip`;
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    window.URL.revokeObjectURL(url);
                })
                .catch(err => { console.error(err); alert('下载失败'); });
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