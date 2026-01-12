import datetime
import json
import logging

from litellm import acompletion

from core import config
from core.formatting import render_brief_data, render_event_analysis
from prompts.analysis import build_event_analysis_prompt
from prompts.brief import build_brief_system_prompt
from prompts.intent import SYSTEM_PROMPT

logger = logging.getLogger(__name__)

EVENT_CN = {
    "security": "安全事件",
    "funding": "融资",
    "protocol": "协议/产品更新",
    "regulation": "监管/政策",
}


ALLOWED_INTENT_TYPES = {
    "config_change",
    "preview",
    "rss_add",
    "rss_remove",
    "rss_list",
    "noise_toggle",
    "schedule_update",
    "event_insight",
    "rules_show",
    "export_config",
    "import_config",
    "apikey_set",
    "chat",
}


def _is_str_list(value) -> bool:
    return isinstance(value, list) and all(isinstance(x, str) for x in value)


def _validate_intent_payload(data: dict) -> bool:
    if not isinstance(data, dict):
        return False
    intent_type = data.get("type")
    if intent_type not in ALLOWED_INTENT_TYPES:
        return False

    if intent_type == "config_change":
        cfg = data.get("config_changes")
        if not isinstance(cfg, dict):
            return False
        for key in ("priority", "block_keywords", "allow_keywords"):
            if key not in cfg:
                return False
        if not _is_str_list(cfg.get("priority")):
            return False
        if not _is_str_list(cfg.get("block_keywords")):
            return False
        if not _is_str_list(cfg.get("allow_keywords")):
            return False
        return True
    if intent_type == "schedule_update":
        has_times = "brief_times" in data
        has_count = "brief_count" in data
        if not (has_times or has_count):
            return False
        if has_times and not _is_str_list(data.get("brief_times")):
            return False
        if has_count and not isinstance(data.get("brief_count"), int):
            return False
        return True
    if intent_type == "event_insight":
        return isinstance(data.get("event_query"), str)
    if intent_type in ("rules_show", "export_config", "rss_list", "preview"):
        return True
    if intent_type == "import_config":
        return isinstance(data.get("config_json"), str)
    if intent_type == "apikey_set":
        if not isinstance(data.get("api_key"), str):
            return False
        if "api_provider" in data and not isinstance(data.get("api_provider"), str):
            return False
        if "llm_model" in data and not isinstance(data.get("llm_model"), str):
            return False
        return True
    if intent_type in ("rss_add", "rss_remove"):
        return isinstance(data.get("rss_url"), str)
    if intent_type == "noise_toggle":
        return isinstance(data.get("enable_noise_filter"), bool)
    if intent_type == "chat":
        return isinstance(data.get("reply"), str)

    return False


def _validate_brief_payload(data: dict) -> bool:
    if not isinstance(data, dict):
        return False
    signals = data.get("signals", [])
    if not isinstance(signals, list):
        return False
    for signal in signals:
        if not isinstance(signal, dict):
            return False
        if not isinstance(signal.get("title", ""), str):
            return False
        if "source_id" in signal and not isinstance(signal.get("source_id"), (int, str)):
            return False
        if "priority" in signal and signal["priority"] not in ("high", "medium", "low"):
            return False
    return True


def _validate_event_analysis_payload(data: dict) -> bool:
    if not isinstance(data, dict):
        return False
    for key in ("title", "summary", "analysis", "impact"):
        if key in data and not isinstance(data.get(key), str):
            return False
    if "risks" in data and not _is_str_list(data.get("risks")):
        return False
    if "watch" in data and not _is_str_list(data.get("watch")):
        return False
    return True


def _resolve_model(config_data: dict | None, model: str | None = None) -> str | None:
    if model:
        return model
    if config_data and config_data.get("llm_model"):
        return config_data.get("llm_model")
    return config.LLM_MODEL


async def parse_user_intent(
    user_text: str,
    current_config: dict,
    api_key: str = None,
) -> tuple[dict, str]:
    """
    调用 LLM 解析用户意图 (通过 LiteLLM)。
    返回: (result_dict, error_message_str)
    """
    final_api_key = api_key or config.LLM_API_KEY
    model = _resolve_model(current_config)
    if not final_api_key:
        logger.error("API Key is not set.")
        return None, "Server Error: API Key not configured. Please set it using /apikey <key>."
    if not model:
        logger.error("LLM model is not set.")
        return None, "Server Error: LLM model not configured. Please set LLM_MODEL."

    safe_config = dict(current_config or {})
    safe_config.pop("api_key", None)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Current Config: {json.dumps(safe_config, ensure_ascii=False)}\n"
                f"User Input: {user_text}"
            ),
        },
    ]

    try:
        response = await acompletion(
            model=model,
            messages=messages,
            api_key=final_api_key,
            api_base=config.LLM_API_BASE,
            temperature=0.1,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content

        try:
            result = json.loads(content)
            if not _validate_intent_payload(result):
                logger.error("Invalid intent payload: %s", result)
                return None, "LLM 返回内容不合法。"
            return result, None
        except json.JSONDecodeError:
            logger.error("Failed to parse LLM response as JSON: %s", content)
            return None, "LLM 返回格式错误。"

    except Exception as e:
        logger.exception("Error calling LLM API: %s", e)
        return None, f"AI 服务暂时不可用: {str(e)}"


async def generate_brief(
    events: list[dict],
    config_data: dict,
    api_key: str = None,
    model: str | None = None,
) -> tuple[str, str]:
    """
    Web3 信号提取专用简报生成 (通过 LiteLLM)
    """
    final_api_key = api_key or config.LLM_API_KEY
    resolved_model = _resolve_model(config_data, model)
    if not final_api_key:
        return None, "Server Error: API Key not configured. Please set it using /apikey <key>."
    if not resolved_model:
        return None, "Server Error: LLM model not configured. Please set LLM_MODEL."

    if not events:
        return "今日暂无符合条件的新闻。", None

    priority = config_data.get("priority", [])
    allow_keywords = config_data.get("allow_keywords", [])

    top_events = events[:50]

    grouped = {}
    for item in top_events:
        etype = item.get("event_type", "other")
        grouped.setdefault(etype, []).append(item)

    id_map = {}
    global_id = 1

    events_by_category = []
    for etype in priority:
        if etype in grouped:
            items = grouped[etype]
            events_by_category.append(f"【{EVENT_CN.get(etype, etype)}】")
            for item in items[:8]:
                cid = global_id
                global_id += 1
                id_map[str(cid)] = item.get("url", "")

                title = item.get("title", "")
                platform = item.get("platform_id", "")
                rank = item.get("rank", "")
                events_by_category.append(f"  (ID:{cid}) [{platform}#{rank}] {title}")

    remaining_types = [t for t in grouped.keys() if t not in priority]
    if remaining_types:
        ordered_types = [t for t in remaining_types if t != "other"]
        if "other" in remaining_types:
            ordered_types.append("other")
        for etype in ordered_types:
            items = grouped[etype]
            events_by_category.append(f"【{EVENT_CN.get(etype, etype)}】")
            for item in items[:8]:
                cid = global_id
                global_id += 1
                id_map[str(cid)] = item.get("url", "")

                title = item.get("title", "")
                platform = item.get("platform_id", "")
                rank = item.get("rank", "")
                events_by_category.append(f"  (ID:{cid}) [{platform}#{rank}] {title}")

    events_text = "\n".join(events_by_category)
    if not events_text.strip():
        return "今日暂无可用于简报的候选信号。", None

    today_str = datetime.date.today().strftime("%Y-%m-%d")

    system_prompt = build_brief_system_prompt(
        today_str=today_str,
        candidate_count=len(top_events),
    )

    user_content = f"""
【用户偏好】
优先级: {' > '.join([EVENT_CN.get(p, p) for p in priority])}
特别关注: {', '.join(allow_keywords) if allow_keywords else '无'}

【今日候选新闻】{len(top_events)} 条
{events_text}

请生成简报。记住：我们追求的是**信号密度**，不是新闻数量。
    """

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    try:
        response = await acompletion(
            model=resolved_model,
            messages=messages,
            api_key=final_api_key,
            api_base=config.LLM_API_BASE,
            temperature=0.2,
            max_tokens=2000,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        logger.info("LLM Raw Response: %s", content)

        try:
            data = json.loads(content)
            if not _validate_brief_payload(data):
                logger.error("Invalid brief payload: %s", data)
                return None, "简报返回内容不合法。"
            signals = data.get("signals", [])
            if isinstance(signals, list):
                for signal in signals:
                    if not isinstance(signal, dict):
                        continue
                    if signal.get("url"):
                        continue
                    source_id = signal.get("source_id")
                    if source_id is None:
                        continue
                    mapped_url = id_map.get(str(source_id), "")
                    if mapped_url:
                        signal["url"] = mapped_url
            return render_brief_data(data), None
        except json.JSONDecodeError:
            logger.error("Brief generation returned invalid JSON: %s", content)
            return None, "生成内容格式解析失败"

    except Exception as e:
        logger.exception("Error generating brief: %s", e)
        return None, f"生成简报时发生错误: {str(e)}"


async def analyze_event(
    event: dict,
    api_key: str = None,
    model: str | None = None,
) -> tuple[str, str]:
    final_api_key = api_key or config.LLM_API_KEY
    resolved_model = _resolve_model(None, model)
    if not final_api_key:
        return None, "Server Error: API Key not configured. Please set it using /apikey <key>."
    if not resolved_model:
        return None, "Server Error: LLM model not configured. Please set LLM_MODEL."

    title = event.get("title", "")
    url = event.get("url", "")
    summary = event.get("summary", "")
    platform = event.get("platform_id", "")
    published = event.get("published_at", "")

    system_prompt = build_event_analysis_prompt()
    user_content = (
        f"标题: {title}\n"
        f"来源: {platform}\n"
        f"发布时间: {published}\n"
        f"链接: {url}\n"
        f"摘要: {summary}\n"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    try:
        response = await acompletion(
            model=resolved_model,
            messages=messages,
            api_key=final_api_key,
            api_base=config.LLM_API_BASE,
            temperature=0.2,
            max_tokens=800,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        logger.info("Event analysis response: %s", content)

        try:
            data = json.loads(content)
            if not _validate_event_analysis_payload(data):
                logger.error("Invalid event analysis payload: %s", data)
                return None, "事件解读返回内容不合法。"
            data.setdefault("title", title)
            data.setdefault("url", url)
            if summary and not data.get("summary"):
                data["summary"] = summary
            return render_event_analysis(data), None
        except json.JSONDecodeError:
            logger.error("Event analysis returned invalid JSON: %s", content)
            return None, "事件解读内容格式解析失败"

    except Exception as e:
        logger.exception("Error analyzing event: %s", e)
        return None, f"事件解读时发生错误: {str(e)}"
