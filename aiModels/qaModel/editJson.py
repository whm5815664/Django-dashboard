from pathlib import Path
import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods

# 数据文件路径：位于当前目录下的 agriculture_dat.json
DATA_PATH = Path(__file__).parent / "agriculture_dat.json"


def _load_json_data():
    """
    读取本地 JSON 知识库，返回列表结构。
    统一字段：id（若原始无则补 i），instruction, input, output。
    """
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"知识库文件不存在: {DATA_PATH}")

    with open(DATA_PATH, 'r', encoding='utf-8') as f:
        raw = json.load(f)

    if not isinstance(raw, list):
        raise ValueError("知识库 JSON 顶层必须是数组(list)")

    data = []
    for i, d in enumerate(raw):
        if not isinstance(d, dict):
            # 跳过非法项
            continue
        data.append({
            "id": d.get("id", i),
            "instruction": (d.get("instruction") or "").strip(),
            "input": (d.get("input") or "").strip(),
            "output": (d.get("output") or "").strip(),
        })
    return data


def _write_json_data(items):
    """将标准化后的数据写回文件，保持为数组对象。"""
    serializable = [{
        "id": it.get("id"),
        "instruction": it.get("instruction", ""),
        "input": it.get("input", ""),
        "output": it.get("output", ""),
    } for it in items]
    with open(DATA_PATH, 'w', encoding='utf-8') as f:
        json.dump(serializable, f, ensure_ascii=False, indent=2)


@csrf_exempt
@require_GET
def get_knowledge_data_view(request):
    """GET /knowledge/data
    返回 agriculture_dat.json 的标准化数据结构：
    { success: true, data: [...] }
    失败时：{ success: false, error: "..." }
    """
    try:
        data = _load_json_data()
        return JsonResponse({
            "success": True,
            "data": data,
        })
    except Exception as e:
        return JsonResponse({
            "success": False,
            "error": str(e),
        }, status=500)


@csrf_exempt
@require_http_methods(["POST", "DELETE"])
def delete_knowledge_item_view(request):
    """POST/DELETE /knowledge/delete
    Body: { id: number|string }
    按 id 删除对应记录并写回文件。
    返回：{ success:true, deleted: id, total: n }
    """
    try:
        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
        except Exception:
            payload = {}
        del_id = payload.get('id')
        if del_id is None:
            return JsonResponse({"success": False, "error": "缺少 id"}, status=400)

        data = _load_json_data()
        # 将字符串数字与数字统一比较
        def same_id(v):
            try:
                return str(v) == str(del_id)
            except Exception:
                return False
        new_data = [it for it in data if not same_id(it.get('id'))]

        if len(new_data) == len(data):
            return JsonResponse({"success": False, "error": "未找到该 id"}, status=404)

        _write_json_data(new_data)
        return JsonResponse({"success": True, "deleted": del_id, "total": len(new_data)})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"]) 
def add_knowledge_item_view(request):
    """POST /knowledge/add
    Body: { instruction: string, input: string, output: string }
    追加一条记录到 JSON 末尾，自动分配 id（取现有数值最大id+1）。
    返回：{ success:true, item:{...}, total:n }
    """
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
        instruction = (payload.get('instruction') or '').strip()
        input_text = (payload.get('input') or '').strip()
        output_text = (payload.get('output') or '').strip()
        if not instruction and not input_text and not output_text:
            return JsonResponse({"success": False, "error": "至少填写一个字段"}, status=400)

        data = _load_json_data()
        # 计算新ID：采用最大可解析为整数的 id + 1
        max_id = -1
        for it in data:
            try:
                v = int(str(it.get('id')))
                if v > max_id:
                    max_id = v
            except Exception:
                continue
        new_id = max_id + 1 if max_id >= 0 else (len(data))

        new_item = {
            "id": new_id,
            "instruction": instruction,
            "input": input_text,
            "output": output_text,
        }
        data.append(new_item)
        _write_json_data(data)
        return JsonResponse({"success": True, "item": new_item, "total": len(data)})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)
