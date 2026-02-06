"""
aiModels.agent.spider_agent

网页爬虫智能体：负责网络搜索和网页内容提取
- 使用requests进行网络请求
- 解析网页内容或使用API
- 提取关键信息并格式化
- 支持多种搜索引擎
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup


class SpiderAgent:
    """
    网页爬虫智能体：支持网页抓取和搜索引擎API
    """

    def __init__(self, timeout: int = 10):
        """初始化爬虫智能体"""
        self.timeout = timeout
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    def execute(self, task: str, **kwargs) -> Dict[str, Any]:
        """
        执行爬虫任务
        
        Args:
            task: 任务类型（search, fetch, extract等）
            **kwargs: 任务参数
            
        Returns:
            Dict包含success, data, error等信息
        """
        try:
            if task == 'search':
                return self._web_search(**kwargs)
            elif task == 'fetch':
                return self._fetch_url(**kwargs)
            elif task == 'extract':
                return self._extract_content(**kwargs)
            else:
                return {
                    'success': False,
                    'error': f'未知任务类型: {task}',
                    'available_tasks': ['search', 'fetch', 'extract']
                }
        except Exception as e:
            return {
                'success': False,
                'error': f'{type(e).__name__}: {str(e)}',
                'task': task
            }

    def _web_search(self, query: str, engine: str = 'baidu', max_results: int = 5) -> Dict[str, Any]:
        """
        网络搜索
        
        Args:
            query: 搜索关键词
            engine: 搜索引擎（默认baidu，也支持duckduckgo）
            max_results: 最大结果数
        """
        try:
            if engine == 'baidu':
                return self._baidu_search(query, max_results)
            elif engine == 'duckduckgo':
                return self._duckduckgo_search(query, max_results)
            else:
                return {
                    'success': False,
                    'error': f'不支持的搜索引擎: {engine}，支持: baidu, duckduckgo'
                }
        except Exception as e:
            return {
                'success': False,
                'error': f'搜索失败: {type(e).__name__}: {str(e)}'
            }

    def _duckduckgo_search(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        """使用DuckDuckGo搜索（无需API密钥）"""
        try:
            # DuckDuckGo HTML搜索
            search_url = f"https://html.duckduckgo.com/html/?q={quote(query)}"
            
            response = requests.get(search_url, headers=self.headers, timeout=self.timeout)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            results = []
            
            # 解析搜索结果
            result_divs = soup.find_all('div', class_='result')[:max_results]
            
            for div in result_divs:
                title_elem = div.find('a', class_='result__a')
                snippet_elem = div.find('a', class_='result__snippet')
                
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    url = title_elem.get('href', '')
                    snippet = snippet_elem.get_text(strip=True) if snippet_elem else ''
                    
                    results.append({
                        'title': title,
                        'url': url,
                        'snippet': snippet
                    })
            
            return {
                'success': True,
                'data': {
                    'query': query,
                    'engine': 'duckduckgo',
                    'count': len(results),
                    'results': results
                }
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'DuckDuckGo搜索失败: {type(e).__name__}: {str(e)}'
            }

    def _baidu_search(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        """使用百度搜索"""
        try:
            search_url = f"https://www.baidu.com/s?wd={quote(query)}"
            
            response = requests.get(search_url, headers=self.headers, timeout=self.timeout)
            response.raise_for_status()
            response.encoding = 'utf-8'  # 确保正确编码
            
            soup = BeautifulSoup(response.text, 'html.parser')
            results = []
            
            # 百度搜索结果的主要容器选择器（多种尝试）
            # 方法1: 查找包含结果的div（百度搜索结果通常在特定容器中）
            result_containers = soup.find_all('div', {'id': re.compile(r'^\d+$')})  # 百度结果ID通常是数字
            
            # 方法2: 如果方法1失败，尝试查找包含标题和链接的div
            if not result_containers:
                result_containers = soup.find_all('div', class_=re.compile(r'result|content'))
            
            # 方法3: 查找所有包含h3标题的div（百度结果通常有h3标题）
            if not result_containers:
                h3_elements = soup.find_all('h3')
                result_containers = [h3.parent for h3 in h3_elements if h3.parent]
            
            for container in result_containers[:max_results]:
                try:
                    # 查找标题（通常在h3标签中）
                    title_elem = container.find('h3')
                    if not title_elem:
                        title_elem = container.find('a', target='_blank')
                    
                    if not title_elem:
                        continue
                    
                    # 提取标题文本
                    title = title_elem.get_text(strip=True)
                    if not title:
                        continue
                    
                    # 提取链接
                    link_elem = title_elem if title_elem.name == 'a' else title_elem.find('a')
                    url = ''
                    if link_elem:
                        url = link_elem.get('href', '')
                        # 处理百度跳转链接
                        if url.startswith('/link?url='):
                            # 尝试从data-href或其他属性获取真实URL
                            real_url = link_elem.get('data-href', '')
                            if real_url:
                                url = real_url
                    
                    # 查找摘要/描述（通常在span或div中）
                    snippet = ''
                    # 尝试多种选择器
                    snippet_elem = (
                        container.find('span', class_=re.compile(r'content|abstract|summary')) or
                        container.find('div', class_=re.compile(r'content|abstract|summary')) or
                        container.find('span', string=re.compile(r'.{20,}'))  # 包含较长文本的span
                    )
                    
                    if snippet_elem:
                        snippet = snippet_elem.get_text(strip=True)
                    else:
                        # 如果找不到专门的摘要，尝试获取容器中的文本（排除标题）
                        all_text = container.get_text(separator=' ', strip=True)
                        if title in all_text:
                            snippet = all_text.replace(title, '', 1).strip()[:200]  # 限制长度
                    
                    results.append({
                        'title': title,
                        'url': url,
                        'snippet': snippet[:300] if snippet else ''  # 限制摘要长度
                    })
                except Exception as e:
                    # 单个结果解析失败，继续处理下一个
                    continue
            
            # 如果仍然没有结果，返回基本信息
            if not results:
                return {
                    'success': True,
                    'data': {
                        'query': query,
                        'engine': 'baidu',
                        'count': 0,
                        'results': [],
                        'message': '未找到搜索结果，可能是百度页面结构变化或需要验证码'
                    }
                }
            
            return {
                'success': True,
                'data': {
                    'query': query,
                    'engine': 'baidu',
                    'count': len(results),
                    'results': results
                }
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'百度搜索失败: {type(e).__name__}: {str(e)}'
            }

    def _fetch_url(self, url: str, extract_text: bool = True) -> Dict[str, Any]:
        """
        获取网页内容
        
        Args:
            url: 网页URL
            extract_text: 是否提取纯文本
        """
        try:
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            response.raise_for_status()
            
            result = {
                'url': url,
                'status_code': response.status_code,
                'content_type': response.headers.get('Content-Type', ''),
                'html': response.text if not extract_text else None
            }
            
            if extract_text:
                soup = BeautifulSoup(response.text, 'html.parser')
                # 移除script和style标签
                for script in soup(["script", "style"]):
                    script.decompose()
                
                # 提取文本
                text = soup.get_text(separator='\n', strip=True)
                # 清理多余空白
                text = re.sub(r'\n\s*\n', '\n\n', text)
                result['text'] = text[:5000]  # 限制长度
                result['title'] = soup.title.string if soup.title else ''
            
            return {
                'success': True,
                'data': result
            }
        except requests.exceptions.Timeout:
            return {
                'success': False,
                'error': f'请求超时: {url}'
            }
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'error': f'请求失败: {type(e).__name__}: {str(e)}'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'解析失败: {type(e).__name__}: {str(e)}'
            }

    def _extract_content(self, url: str, selectors: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        从网页提取特定内容
        
        Args:
            url: 网页URL
            selectors: CSS选择器字典，例如 {'title': 'h1', 'content': '.article-content'}
        """
        try:
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            extracted = {}
            
            if selectors:
                for key, selector in selectors.items():
                    elements = soup.select(selector)
                    if elements:
                        extracted[key] = [elem.get_text(strip=True) for elem in elements]
                    else:
                        extracted[key] = []
            else:
                # 默认提取：标题、段落、链接
                extracted['title'] = soup.title.string if soup.title else ''
                extracted['headings'] = [h.get_text(strip=True) for h in soup.find_all(['h1', 'h2', 'h3'])[:10]]
                extracted['paragraphs'] = [p.get_text(strip=True) for p in soup.find_all('p')[:20]]
                extracted['links'] = [{'text': a.get_text(strip=True), 'url': a.get('href', '')} 
                                     for a in soup.find_all('a', href=True)[:10]]
            
            return {
                'success': True,
                'data': {
                    'url': url,
                    'extracted': extracted
                }
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'内容提取失败: {type(e).__name__}: {str(e)}'
            }


# 创建全局实例
_spider_agent = None


def get_spider_agent() -> SpiderAgent:
    """获取爬虫智能体单例"""
    global _spider_agent
    if _spider_agent is None:
        _spider_agent = SpiderAgent()
    return _spider_agent
