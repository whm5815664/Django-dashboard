from __future__ import annotations

import posixpath
import urllib.request

from django.conf import settings
from django.http import HttpRequest, HttpResponse, StreamingHttpResponse
from django.views.decorators.http import require_GET


def _safe_join_media_path(subpath: str) -> str:
    p = (subpath or "").lstrip("/")
    p = posixpath.normpath(p)
    if p in (".", ""):
        return ""
    if p.startswith("../") or p == "..":
        return ""
    return p


@require_GET
def remote_media_proxy(request: HttpRequest, subpath: str) -> HttpResponse:
    """
    同源代理远程媒体资源，解决 HTTPS 页面下的 mixed content。
    """
    base = (getattr(settings, "REMOTE_MEDIA_BASE", "") or "").strip().rstrip("/")
    if not base:
        return HttpResponse("REMOTE_MEDIA_BASE 未配置", status=500)

    safe_path = _safe_join_media_path(subpath)
    if not safe_path:
        return HttpResponse("非法路径", status=400)

    upstream_url = f"{base}/media/{safe_path}"
    upstream = urllib.request.urlopen(upstream_url, timeout=10)
    content_type = upstream.headers.get("Content-Type") or "application/octet-stream"
    resp = StreamingHttpResponse(upstream, content_type=content_type)
    cache_control = upstream.headers.get("Cache-Control")
    if cache_control:
        resp["Cache-Control"] = cache_control
    return resp
