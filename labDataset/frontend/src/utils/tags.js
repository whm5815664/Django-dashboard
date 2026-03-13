// 分割tags
// src/utils/tags.js
export function parseTags(data_format) {
    if (!data_format) return [];
    return String(data_format)
      .split(/[,，、;；|/]+/)      // 支持多种分隔符
      .map(s => s.trim())
      .filter(Boolean)
      .map(name => ({
        label: name,
        value: name,
      }));
  }
  