PROMPT_RULES = (
    {
        "all": ["华中农业大学", "校长"],
        "prompt": "系统提示：严建兵，华中农业大学校长，作物遗传改良国家重点实验室（华中农业大学）副主任，长期从事玉米基因组学和分子育种研究"
    },
    {
        "all": ["严建兵"],
        "prompt": "系统提示：严建兵，华中农业大学校长，作物遗传改良国家重点实验室（华中农业大学）副主任，长期从事玉米基因组学和分子育种研究"
    },
    # 可以在此继续添加更多规则：
    # {
    #     "all": ["小麦", "病害"],
    #     "any": ["防治", "诊断"],
    #     "prompt": "聚焦小麦主要病害（如赤霉病、白粉病、锈病）的流行条件、症状识别与综合防治技术。"
    # },
)


def select_prompts_for_question(user_text):
    """根据用户问题选择需要注入的prompt列表（作为system消息）。"""
    text = (user_text or "").strip()
    prompts = []
    for rule in PROMPT_RULES:
        all_keywords = rule.get("all", [])
        any_keywords = rule.get("any", [])
        prompt = rule.get("prompt")
        if not prompt:
            continue
        all_ok = all(k in text for k in all_keywords)
        any_ok = True if not any_keywords else any(k in text for k in any_keywords)
        if all_ok and any_ok:
            prompts.append(prompt)
    return prompts