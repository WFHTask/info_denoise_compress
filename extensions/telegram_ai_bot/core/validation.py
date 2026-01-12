import re

EVENT_TYPES = ["security", "funding", "protocol", "regulation"]
_TIME_RE = re.compile(r"^\d{2}:\d{2}$")


def _is_valid_time(value: str) -> bool:
    if not isinstance(value, str) or not _TIME_RE.match(value):
        return False
    hour, minute = value.split(":")
    return 0 <= int(hour) <= 23 and 0 <= int(minute) <= 59


def validate_config(cfg: dict) -> tuple[bool, str]:
    if not isinstance(cfg, dict):
        return False, "配置必须是 JSON 对象"

    if "priority" not in cfg:
        return False, "缺少 priority 字段"

    if not isinstance(cfg["priority"], list):
        return False, "priority 必须是列表"

    if len(cfg["priority"]) != 4:
        return False, "priority 必须包含 4 个元素"

    for p in cfg["priority"]:
        if p not in EVENT_TYPES:
            return False, f"未知的事件类型 {p}"

    if len(set(cfg["priority"])) != 4:
        return False, "priority 不能包含重复项"

    for key in ["block_keywords", "allow_keywords"]:
        if key not in cfg:
            return False, f"缺少 {key} 字段"
        if not isinstance(cfg[key], list):
            return False, f"{key} 必须是列表"
        for item in cfg[key]:
            if not isinstance(item, str):
                return False, f"{key} 只能包含字符串"
            if len(item) > 50:
                return False, f"关键词'{item[:10]}...' 过长"

    if "brief_count" in cfg:
        if not isinstance(cfg["brief_count"], int):
            return False, "brief_count 必须是整数"
        if cfg["brief_count"] < 1 or cfg["brief_count"] > 6:
            return False, "brief_count 必须在 1-6 之间"

    if "brief_times" in cfg:
        if not isinstance(cfg["brief_times"], list):
            return False, "brief_times 必须是列表"
        if len(cfg["brief_times"]) > 6:
            return False, "brief_times 最多支持 6 个时间"
        for item in cfg["brief_times"]:
            if not _is_valid_time(item):
                return False, f"无效时间格式: {item}"

    if "daily_time" in cfg and cfg["daily_time"]:
        if not _is_valid_time(cfg["daily_time"]):
            return False, "daily_time 格式应为 HH:MM"

    return True, ""
