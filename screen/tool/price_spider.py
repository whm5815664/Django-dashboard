"""
价格指数列表：无头 Chromium 打开页面，待 Ajax 改写 DOM 后解析 ul>li。
name ← div.name；num / time ← div.num、div.time 下子节点 font.fo。

首次使用需安装浏览器内核：pip install playwright && playwright install chromium
"""

from __future__ import annotations

import json
from typing import Any, Dict

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

#pip install playwright==1.49.1
#playwright install chromium （C:\Users\<你的用户名>\AppData\Local\ms-playwrigh）


SJ_URL = "https://www.agri.cn/sj/"
#  /html/body/div[2]/div/div[3]/div/div[2]/div[1]/div/div[1]/div[2] 
XP_CSS = (
    "body > div:nth-of-type(2) > div > div:nth-of-type(3) > div > "
    "div:nth-of-type(2) > div:nth-of-type(1) > div > div:nth-of-type(1) > div:nth-of-type(2)"
)
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"

# 与 XP_CSS 一致，供 page.wait_for_function 在浏览器内定位同一节点
XP_JS_QUERY = (
    "body > div:nth-of-type(2) > div > div:nth-of-type(3) > div > "
    "div:nth-of-type(2) > div:nth-of-type(1) > div > div:nth-of-type(1) > div:nth-of-type(2)"
)


def _txt(el) -> str:
    return el.get_text(strip=True) if el else ""


def _field_name_num_time(li) -> Dict[str, str]:
    num_el = li.select_one(".num > font.fo") or li.select_one(".num font.fo")
    time_el = li.select_one(".time > font.fo") or li.select_one(".time font.fo")
    return {
        "name": _txt(li.select_one(".name")),
        "num": _txt(num_el),
        "time": _txt(time_el),
    }


def _parse_items(html: str, url: str) -> Dict[str, Any]:
    root = BeautifulSoup(html, "html.parser")
    box = root.select_one(XP_CSS)
    if not box:
        return {"url": url, "items": [], "error": "XPath 对应节点未找到"}
    ul = box.find("ul", recursive=False)
    if not ul:
        return {"url": url, "items": [], "error": "节点下无 ul"}
    items = [_field_name_num_time(li) for li in ul.find_all("li", recursive=False)]
    return {"url": url, "items": items}


def _fetch_rendered_html(url: str, timeout_s: float, headless: bool) -> str:
    timeout_ms = max(5_000, int(timeout_s * 1000))
    wait_js = f"""
    () => {{
      const box = document.querySelector({json.dumps(XP_JS_QUERY)});
      if (!box) return false;
      let ok = 0;
      for (const li of box.querySelectorAll("ul > li")) {{
        const st = (li.getAttribute("style") || "").replace(/\\s/g, "");
        if (st.includes("display:none")) continue;
        const fo = li.querySelector(".num > font.fo") || li.querySelector(".num font.fo");
        const t = (fo && fo.textContent ? fo.textContent : "").trim();
        if (t && t !== "0") ok++;
        if (ok >= 2) return true;
      }}
      return false;
    }}
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        try:
            ctx = browser.new_context(locale="zh-CN", user_agent=USER_AGENT)
            page = ctx.new_page()
            page.set_default_timeout(timeout_ms)
            page.goto(url, wait_until="load", timeout=timeout_ms)
            try:
                page.wait_for_load_state("networkidle", timeout=min(20_000, timeout_ms))
            except Exception:
                pass
            try:
                page.wait_for_function(wait_js, timeout=min(25_000, timeout_ms))
            except Exception:
                page.wait_for_timeout(3_000)
            else:
                page.wait_for_timeout(500)
            return page.content()
        finally:
            browser.close()


def fetch_price_indices_json(
    url: str = SJ_URL,
    timeout: float = 45,
    *,
    headless: bool = True,
) -> Dict[str, Any]:
    """
    无头浏览器拉取页面，待接口改写 num 后再解析。
    返回: {"url", "items": [{"name","num","time"}, ...]}
    """
    html = _fetch_rendered_html(url, timeout_s=timeout, headless=headless)
    return _parse_items(html, url)


if __name__ == "__main__":
    print(json.dumps(fetch_price_indices_json(), ensure_ascii=False, indent=2))
