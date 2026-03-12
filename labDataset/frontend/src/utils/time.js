// src/utils/time.js

// 把 ISO8601 时间字符串格式化为：YYYY-MM-DD HH:mm:ss（本地时区）
export function formatTime(isoString) {
    if (!isoString) return "";
  
    const d = new Date(isoString);
    if (Number.isNaN(d.getTime())) return String(isoString); // 不是合法时间就原样返回
  
    const pad = (n) => String(n).padStart(2, "0");
  
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ` +
           `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}
  
  // 只显示到分钟：YYYY-MM-DD HH:mm
export function formatTimeMinute(isoString) {
    if (!isoString) return "";
    const d = new Date(isoString);
    if (Number.isNaN(d.getTime())) return String(isoString);
  
    const pad = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ` +
           `${pad(d.getHours())}:${pad(d.getMinutes())}`;
}
  