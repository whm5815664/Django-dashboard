import re, json, csv
import argparse
from pathlib import Path
from typing import List, Dict, Tuple, Any, Optional
import pandas as pd
# pip install pyvis # 可视化
from pyvis.network import Network
from IPython.display import display, IFrame, HTML


from ltp import LTP
ltp = LTP()

# ===================== 领域词表（可按需扩充） =====================
CROPS = [
    "水稻", "小麦", "冬小麦", "春小麦", "玉米", "大豆", "高粱", "马铃薯", "土豆",
    "花生", "油菜", "棉花", "番茄", "西红柿", "辣椒", "葡萄", "苹果", "梨", "香蕉",
    "柑橘", "茶树",
]
# 作物别名归一
CROP_ALIASES = {
    "冬小麦": "小麦",
    "春小麦": "小麦",
    "西红柿": "番茄",
    "稻谷":  "水稻",
    "夏玉米": "玉米",
    "春玉米": "玉米",
}
# 病害/虫害清单（与现有逻辑兼容，均当作“致病要素”处理）
DISEASES = [
    # —— 水稻 ——
    "稻瘟病","稻曲病","白叶枯病","纹枯病","黑粉病","根腐病","炭疽病","霜霉病",
    # —— 小麦 ——
    "条锈病","小麦条锈病","小麦白粉病","赤霉病","根腐病","纹枯病","黑粉病","叶锈病",
    # —— 玉米（病害） ——
    "大斑病","小斑病","灰斑病","玉米灰斑病","南方锈病","玉米南方锈病","普通锈病","锈病",
    "细菌性条斑病","弯孢叶斑病","茎腐病","穗腐病","丝黑穗病","矮花叶病","粗缩病","炭疽病","根腐病",
    # —— 玉米（虫害，仍归入本表以兼容现有关系名） ——
    "玉米螟","草地贪夜蛾","粘虫","棉铃虫","甜菜夜蛾","地老虎","蝼蛄","蓟马","蚜虫",
    # —— 柑橘（病害+虫害） ——
    "柑橘溃疡病","黄龙病","疮痂病","黑斑病","炭疽病","褐腐病","绿霉病","蓝霉病","煤污病","衰退病",
    "柑橘木虱","亚洲柑橘木虱","柑橘红蜘蛛","柑橘潜叶蛾","柑橘大实蝇","柑橘蚜虫","介壳虫","粉蚧","褐软蜡蚧",
    # —— 通用/保留 —— 
    "叶斑病","晚疫病","霜霉病","白叶枯病","纹枯病","黑粉病","根腐病","炭疽病","赤霉病",
]

# ===================== 地点启发式（上下文参考，不参与关系） =====================
# 地点启发式（帮助识别“黄淮海等主要冬小麦产区、部分地区”等；不参与关系，仅做上下文参考）
HEUR_LOC_SUFFIXES = ["地区","产区","省","市","县","区","州","自治区","平原","高原","流域","盆地"]
REGION_NAMES = ["黄淮海","江淮","江汉","江南","华北","华中","华南","西南","西北","东北","长江中下游","东北平原","四川盆地","部分地区"]

# ===================== 触发词 =====================
# 1) 明确感染动词（强证据）
VERB_INFECT = ["感染", "侵染"]
# 2) 风险/流行语义（弱证据，用于推断感染关系）
RISK_TRIGGERS = [
    "易发期","流行期","进入.*?期","步入.*?期","正值.*?期",
    "发病中心","发病","多发","高发","频发","流行",
    "菌源量.*?(高于|偏高|较高|明显增高|增加|较多|偏多)",
    "侵入","入侵","传入","扩散","传播","远距离传播","空中传播",
    "构成.*威胁","严重威胁","预警","严防","防治"
]
_RISK_PATTS = [re.compile(p) for p in RISK_TRIGGERS]

# ===================== 基础工具 =====================
def sent_split(text: str) -> List[str]:
    seps=set("。！？!?"); buf=""; sents=[]
    for ch in text:
        buf+=ch
        if ch in seps:
            if buf.strip(): sents.append(buf.strip()); buf=""
    if buf.strip(): sents.append(buf.strip())
    return sents

def normalize_crop(name: str) -> str:
    return CROP_ALIASES.get(name, name)

def join_span(tokens: List[str], s: int, e: int) -> str:
    s=max(0,min(int(s),len(tokens)-1)); e=max(0,min(int(e),len(tokens)-1))
    if s>e: s,e=e,s
    return "".join(tokens[s:e+1])

def find_mentions_in_text(text: str, vocab: List[str]) -> List[str]:
    return sorted({w for w in vocab if w in text}, key=len, reverse=True)

def keep_shortest(names: List[str]) -> List[str]:
    keep=set(names)
    for x in names:
        for y in names:
            if x!=y and y in x and len(y)<len(x):
                if x in keep: keep.remove(x)
    return sorted(keep, key=len)

def split_clauses(tokens: List[str], s: int, e: int) -> List[Tuple[int,int]]:
    PUNC={"，","、","；","：","。"}; clauses=[]; i=s
    for k in range(s,e+1):
        if tokens[k] in PUNC:
            if i<=k-1: clauses.append((i,k-1)); i=k+1
    if i<=e: clauses.append((i,e))
    return clauses

def find_vocab_mentions_positions(tokens: List[str], start: int, end: int,
                                  vocab: List[str], normalize_map: Optional[Dict[str,str]]=None) -> List[Tuple[str,int,int]]:
    end=min(end,len(tokens)-1); mentions=[]; vocab_set=set(vocab)
    for i in range(start,end+1):
        cur=""
        for j in range(i,end+1):
            cur+=tokens[j]
            if cur in vocab_set:
                name = normalize_map.get(cur, cur) if normalize_map else cur
                mentions.append((name,i,j))
            if len(cur)>20: break
    return mentions

def pair_by_proximity(tokens: List[str],
                      diseases: List[Tuple[str,int,int]],
                      crops: List[Tuple[str,int,int]],
                      ranges: List[Tuple[int,int]]) -> List[Tuple[str,str]]:
    if not diseases or not crops: return []
    pairs=[]; clauses_by_range=[split_clauses(tokens,s,e) for s,e in ranges]
    def in_clause(pos:int, cl:Tuple[int,int])->bool: return cl[0]<=pos<=cl[1]
    for dname,ds,de in diseases:
        dc=(ds+de)//2; cand=[]
        for clauses in clauses_by_range:
            for cl in clauses:
                if in_clause(dc,cl):
                    for cname,cs,ce in crops:
                        cc=(cs+ce)//2
                        if in_clause(cc,cl): cand.append((abs(cc-dc),cname))
        if cand:
            cand.sort(key=lambda x:x[0]); pairs.append((dname,cand[0][1])); continue
        allc=[(abs(((cs+ce)//2)-dc),cname) for cname,cs,ce in crops]
        allc.sort(key=lambda x:x[0]); pairs.append((dname,allc[0][1]))
    return list({(d,c):(d,c) for d,c in pairs}.values())

def preferred_crop_for_disease(d: str) -> Optional[str]:
    if ("稻" in d) or (d in {"稻瘟病","稻曲病","白叶枯病","纹枯病"}): return "水稻"
    if ("玉米" in d) or (d in {"玉米南方锈病","南方锈病","大斑病","小斑病","灰斑病","玉米灰斑病",
                               "细菌性条斑病","茎腐病","穗腐病","丝黑穗病","矮花叶病","粗缩病"}): return "玉米"
    if d in {"小麦条锈病","小麦白粉病","条锈病"}: return "小麦"
    if any(k in d for k in {"柑橘溃疡病","黄龙病","疮痂病","褐腐病","绿霉病","蓝霉病","煤污病","衰退病",
                             "柑橘木虱","亚洲柑橘木虱","柑橘红蜘蛛","柑橘潜叶蛾","柑橘大实蝇","柑橘蚜虫",
                             "介壳虫","粉蚧","褐软蜡蚧"}): return "柑橘"
    return None

# ===================== LTP 注解（CWS + SRL） =====================
def ltp_annotate(sentence: str) -> Dict[str, Any]:
    out = ltp.pipeline([sentence], tasks=["cws","srl"])
    try:
        tokens = out.cws[0]
    except Exception:
        tokens = out.to_tuple()[0][0]
    raw_srl = getattr(out,"srl",[[]])[0] if hasattr(out,"srl") else []

    def locate_span_by_text(text:str)->Tuple[int,int]:
        if not text: return 0,0
        n=len(tokens)
        for i in range(n):
            cur=""
            for j in range(i,min(i+20,n)):
                cur+=tokens[j]
                if cur==text: return i,j
                if len(cur)>len(text): break
        for i,t in enumerate(tokens):
            if (text in t) or (t in text): return i,i
        return 0,0

    def clamp(s:int,e:int)->Tuple[int,int]:
        s=max(0,min(int(s),len(tokens)-1)); e=max(0,min(int(e),len(tokens)-1))
        if s>e: s,e=e,s
        return s,e

    def pred_index(f)->int:
        if isinstance(f,int): return max(0,min(f,len(tokens)-1))
        if isinstance(f,str):
            for i,t in enumerate(tokens):
                if t==f or (f in t) or (t in f): return i
            return 0
        if isinstance(f,dict):
            for k in ["index","idx","position","id","predicate_index","i"]:
                v=f.get(k)
                if isinstance(v,int): return max(0,min(v,len(tokens)-1))
                if isinstance(v,str) and v.strip().lstrip("-").isdigit(): return max(0,min(int(v),len(tokens)-1))
            for k in ["word","lemma","text","predicate","pred","verb"]:
                v=f.get(k)
                if isinstance(v,str):
                    for i,t in enumerate(tokens):
                        if t==v or (v in t) or (t in v): return i
            return 0
        return 0

    def norm_arg(a)->Optional[Dict[str,int]]:
        if isinstance(a,dict):
            role=a.get("role"); s=a.get("start",a.get("begin",a.get("beg"))); e=a.get("end",a.get("stop",a.get("to")))
            if s is not None and e is not None:
                s,e=clamp(s,e); return {"role":role,"start":s,"end":e}
            txt=a.get("text") or a.get("span") or a.get("content")
            if isinstance(txt,str) and txt:
                s,e=clamp(*locate_span_by_text(txt)); return {"role":role,"start":s,"end":e}
            return None
        if isinstance(a,(list,tuple)) and len(a)>=2:
            role=a[0]
            if len(a)>=3 and all(isinstance(x,int) or (isinstance(x,str) and x.strip().lstrip("-").isdigit()) for x in a[1:3]):
                s,e=clamp(int(a[1]),int(a[2])); return {"role":role,"start":s,"end":e}
            for x in a[1:]:
                if isinstance(x,str) and x:
                    s,e=clamp(*locate_span_by_text(x)); return {"role":role,"start":s,"end":e}
            return None
        return None

    frames=[]
    if isinstance(raw_srl,list) and raw_srl:
        if any(isinstance(x,dict) for x in raw_srl):
            for fr in raw_srl:
                if not isinstance(fr,dict): continue
                pi=pred_index(fr.get("predicate",fr.get("pred",fr.get("verb",0))))
                args=[na for a in fr.get("arguments",fr.get("roles",[])) or [] if (na:=norm_arg(a))]
                if args: frames.append({"predicate":pi,"arguments":args})
        for fr in raw_srl:
            if isinstance(fr,(list,tuple)) and len(fr)==2:
                pi=pred_index(fr[0])
                args=[na for a in (fr[1] or []) if (na:=norm_arg(a))]
                if args: frames.append({"predicate":pi,"arguments":args})
        if not frames and len(raw_srl)==len(tokens) and all(isinstance(x,list) for x in raw_srl):
            for i,args_raw in enumerate(raw_srl):
                args=[na for a in args_raw if (na:=norm_arg(a))]
                if args: frames.append({"predicate":i,"arguments":args})
    return {"tokens":tokens,"srl":frames,"text":sentence}

# ===================== 地点抽取（仅展示） =====================
def find_locations(text: str) -> List[str]:
    patt = re.compile(rf"([\u4e00-\u9fa5A-Za-z0-9]{{2,20}}?(?:{'|'.join(map(re.escape, HEUR_LOC_SUFFIXES))}))")
    locs = {m.group(1).strip() for m in patt.finditer(text)}
    for n in REGION_NAMES:
        if n in text: locs.add(n if (n+"地区") not in text else n+"地区")
    return sorted(locs, key=len, reverse=True)

# ===================== 实体与关系抽取 =====================
def extract_entities_from_sentence(doc: Dict[str, Any]) -> List[Dict[str,str]]:
    text=doc["text"]
    crops=find_mentions_in_text(text,CROPS)
    if "冬小麦" in text or "春小麦" in text: crops.append("小麦")
    if "夏玉米" in text or "春玉米" in text: crops.append("玉米")
    crops=[normalize_crop(c) for c in sorted(set(crops), key=len, reverse=True)]
    diseases=keep_shortest(find_mentions_in_text(text, DISEASES))
    if ("稻区" in text) or ("稻瘟病" in diseases) or ("稻曲病" in diseases):
        if "水稻" not in crops: crops.append("水稻")
    ents={**{c:{"name":c,"type":"Crop"} for c in crops},
          **{d:{"name":d,"type":"Disease"} for d in diseases}}
    return list(ents.values())

def _sentence_contains_infect(text: str) -> bool:
    return any(v in text for v in VERB_INFECT)

def extract_relations_strong(doc: Dict[str, Any], sentence_entities: List[Dict[str,str]]) -> List[Dict[str,str]]:
    """
    强触发：
      1) 首选 SRL（A0/A1 + 论元并集兜底）
      2) ★回退：若句含“感染/侵染”，对【包含该谓词的子句】做就近配对（即便 SRL 无论元）
    """
    tokens, srl, text = doc["tokens"], doc["srl"], doc["text"]
    ent_type = {e["name"]: e["type"] for e in sentence_entities}
    def ents_in(span: str, typ: str) -> List[str]:
        return sorted({n for n,t in ent_type.items() if t==typ and n in span}, key=len)

    edges=[]

    # 1) SRL 抽取
    for fr in srl:
        pred = tokens[fr["predicate"]]
        if not any(v in pred for v in VERB_INFECT): continue
        role_text, merged = {}, ""
        for a in fr.get("arguments",[]):
            s,e=a["start"],a["end"]; sp=join_span(tokens,s,e)
            role_text[a["role"]] = sp; merged += sp
        A0_c, A0_d = ents_in(role_text.get("A0",""),"Crop"), ents_in(role_text.get("A0",""),"Disease")
        A1_c, A1_d = ents_in(role_text.get("A1",""),"Crop"), ents_in(role_text.get("A1",""),"Disease")
        def add(d_list,c_list,ev):
            for d in d_list:
                for c in c_list:
                    edges.append({"source":d,"relation":"感染","target":c,"evidence":ev})
                    edges.append({"source":c,"relation":"被感染","target":d,"evidence":ev})
        if A0_d and A1_c:
            add(A0_d, A1_c, f"{'、'.join(A0_d)} 感染 {'、'.join(A1_c)}｜{text}")
        elif A0_c and A1_d:
            add(A1_d, A0_c, f"{'、'.join(A1_d)} 感染 {'、'.join(A0_c)}｜{text}")
        else:
            m_c, m_d = ents_in(merged,"Crop"), ents_in(merged,"Disease")
            if m_c and m_d:
                add(m_d, m_c, f"论元包含：{','.join(m_d)} 与 {','.join(m_c)}｜{text}")

    # 2) ★谓词就近回退（解决“番茄被叶斑病侵染”等 SRL 论元缺失）
    if _sentence_contains_infect(text):
        # 找出“感染/侵染”所在的 token 下标；若分词未独立成词，也抓“含有该字串”的 token
        verb_idx = [i for i,t in enumerate(tokens) if any(v in t for v in VERB_INFECT)]
        if not verb_idx:
            verb_idx = []
        if verb_idx:
            whole=(0,len(tokens)-1)
            clauses = split_clauses(tokens,*whole)
            # 逐个谓词所在子句做就近配对
            for vi in verb_idx:
                # 找到包含谓词的子句
                sub = None
                for cl in clauses:
                    if cl[0] <= vi <= cl[1]:
                        sub = cl; break
                if sub is None: sub = whole
                cs,ce = sub
                dis = find_vocab_mentions_positions(tokens, cs, ce, DISEASES, None)
                dis_names = keep_shortest([d[0] for d in dis]); dis = [m for m in dis if m[0] in dis_names]
                crops = find_vocab_mentions_positions(tokens, cs, ce, CROPS, CROP_ALIASES)
                # 子句无作物 → 用病害偏好作物兜底
                if not crops and dis:
                    fallbacks=set()
                    for dname,_,_ in dis:
                        pref=preferred_crop_for_disease(dname)
                        if pref: fallbacks.add(pref)
                    crops=[(c,-1,-1) for c in fallbacks]
                if not dis or not crops: continue
                pairs = pair_by_proximity(tokens, dis, crops, [(cs,ce)])
                for d,c in pairs:
                    ev = f"谓词就近：{'、'.join(VERB_INFECT)}｜{text}"
                    edges.append({"source":d,"relation":"感染","target":c,"evidence":ev})
                    edges.append({"source":c,"relation":"被感染","target":d,"evidence":ev})

    return list({(e["source"],e["relation"],e["target"]):e for e in edges}.values())

def extract_relations_weak(doc: Dict[str, Any], sentence_entities: List[Dict[str,str]]) -> List[Dict[str,str]]:
    tokens, text = doc["tokens"], doc["text"]
    hit=[p.pattern for p in _RISK_PATTS if p.search(text)]
    if not hit: return []
    trig=hit[0]; edges=[]
    whole=(0,len(tokens)-1); clauses=split_clauses(tokens,*whole)
    for (cs,ce) in clauses:
        dis=find_vocab_mentions_positions(tokens, cs, ce, DISEASES, None)
        dis_names=keep_shortest([d[0] for d in dis]); dis=[m for m in dis if m[0] in dis_names]
        crops=find_vocab_mentions_positions(tokens, cs, ce, CROPS, CROP_ALIASES)
        if not crops and dis:
            fallbacks=set()
            for dname,_,_ in dis:
                pref=preferred_crop_for_disease(dname)
                if pref: fallbacks.add(pref)
            crops=[(c,-1,-1) for c in fallbacks]
        if not dis or not crops: continue
        pairs = pair_by_proximity(tokens, dis, crops, [(cs,ce)])
        for d,c in pairs:
            edges.append({"source":d,"relation":"感染","target":c,"evidence":f"推断：{trig}｜{text}"})
            edges.append({"source":c,"relation":"被感染","target":d,"evidence":f"推断：{trig}｜{text}"})
    return list({(e["source"],e["relation"],e["target"]):e for e in edges}.values())



# # ===================== 测试样例 =====================
# text = (
#     "柑橘产区：华南、西南橘区炭疽病进入高发期，持续阴雨天气加速病原传播，部分果园已出现典型病斑，需及时清理病枝并喷施咪鲜胺或苯醚甲环唑进行预防。"
#
#     "玉米产区：东北、华北春玉米区大斑病流行风险较高，高温高湿条件下易快速蔓延，建议在玉米大喇叭口期喷施吡唑醚菌酯或戊唑醇等药剂控制病害扩展。"
#
#     "水稻产区：江南、华南稻区纹枯病发生普遍，田间郁闭度高田块病情扩展迅速，需加强水肥管理，并结合分蘖末期至孕穗期喷施井冈霉素或噻呋酰胺。"
#
#     "小麦产区：长江中下游、江淮麦区赤霉病偏重流行趋势明显，若抽穗扬花期遇连阴雨，需抢晴喷施氰烯菌酯、戊唑醇等药剂防控，降低毒素污染风险。"
#
#     "请各产区强化田间监测，抓住关键防治窗口期，推进专业化统防统治，科学选药轮换用药，保障粮食安全生产。"
# )
#
# entities, edges, locations = extract_from_text(text)
# print("entities:",entities)
# print("edges:",edges)
#
# print('\n--------逻辑关系-----------')
# for each in edges:
#     print("\n")
#     print(each)
#
# print('\n--------可视化-----------')
# _ = show_tables(entities, edges, locations)
# _ = visualize_pyvis(entities, edges, height_px=600)
#

# ===================== 对外导出：文本抽取与可视化 =====================
from io import StringIO
import tempfile

def extract_from_text(text: str) -> Tuple[List[Dict[str, str]], List[Dict[str, str]], List[str]]:
    """对整段文本进行句子切分、LTP标注、实体与关系抽取，并返回三元组。

    返回：
      - entities: [{name, type}]
      - edges: [{source, relation, target, evidence}]
      - locations: [str]
    """
    if not isinstance(text, str):
        text = str(text)
    sentences = sent_split(text)
    all_entities: Dict[Tuple[str, str], Dict[str, str]] = {}
    all_edges: Dict[Tuple[str, str, str], Dict[str, str]] = {}

    for sent in sentences:
        if not sent.strip():
            continue
        doc = ltp_annotate(sent)
        ents = extract_entities_from_sentence(doc)
        for e in ents:
            all_entities[(e["name"], e["type"])] = e
        strong_edges = extract_relations_strong(doc, ents)
        for ed in strong_edges:
            all_edges[(ed["source"], ed["relation"], ed["target"])] = ed
        weak_edges = extract_relations_weak(doc, ents)
        for ed in weak_edges:
            all_edges[(ed["source"], ed["relation"], ed["target"])] = ed

    locations = find_locations(text)
    return list(all_entities.values()), list(all_edges.values()), locations


def visualize_pyvis(entities: List[Dict[str, str]], edges: List[Dict[str, str]], height_px: int = 600) -> str:
    """使用 PyVis 生成交互式关系图 HTML 字符串。"""
    net = Network(height=f"{height_px}px", width="100%", directed=True, notebook=False, bgcolor="#ffffff")
    # 配置布局与交互
    net.toggle_physics(True)
    net.set_options(
        """
        {
          "nodes": {"font": {"size": 14}},
          "edges": {"arrows": {"to": {"enabled": true}}, "smooth": {"type": "dynamic"}},
          "physics": {"solver": "forceAtlas2Based", "stabilization": {"iterations": 150}}
        }
        """
    )

    # 添加节点
    for e in entities:
        nid = e.get("name", "")
        ntype = e.get("type", "")
        color = "#60a5fa" if ntype == "Disease" else ("#34d399" if ntype == "Crop" else "#94a3b8")
        shape = "dot"
        net.add_node(nid, label=nid, title=f"{ntype}", color=color, shape=shape)

    # 添加边
    for r in edges:
        src = r.get("source", "")
        dst = r.get("target", "")
        rel = r.get("relation", "")
        ev = r.get("evidence", "")
        net.add_edge(src, dst, label=rel, title=ev)

    # 生成HTML字符串
    html_str = None
    if hasattr(net, "generate_html"):
        try:
            html_str = net.generate_html()
        except Exception:
            html_str = None
    if not html_str:
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8") as tf:
            net.save_graph(tf.name)
            tf.flush()
            tf.seek(0)
            html_str = tf.read()
    return html_str

# ========== Django 视图（仅供路由直接调用） ==========
try:
    from django.http import JsonResponse
    from django.views.decorators.csrf import csrf_exempt

    @csrf_exempt
    def extract_api_view(request):
        if request.method != 'POST':
            return JsonResponse({'error': 'Method not allowed'}, status=405)
        try:
            body = request.body.decode('utf-8') if request.body else '{}'
            data = json.loads(body or '{}')
            text = (data.get('text') or '').strip()
            if not text:
                return JsonResponse({'error': '文本不能为空'}, status=400)
            entities, edges, locations = extract_from_text(text)
            graph_html = visualize_pyvis(entities, edges, height_px=640)
            return JsonResponse({
                'entities': entities,
                'edges': edges,
                'locations': locations,
                'graph_html': graph_html,
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
except Exception:
    # 非 Django 运行环境（如纯脚本调用）时，忽略引入失败
    pass
