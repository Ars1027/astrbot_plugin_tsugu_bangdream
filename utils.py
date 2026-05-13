from __future__ import annotations

import base64
import re
import uuid
from pathlib import Path
from typing import Any

import astrbot.api.message_components as Comp


SERVER_NAMES = {
    "0": 0,
    "1": 1,
    "2": 2,
    "3": 3,
    "4": 4,
    "jp": 0,
    "en": 1,
    "tw": 2,
    "cn": 3,
    "kr": 4,
    "日服": 0,
    "国际服": 1,
    "台服": 2,
    "国服": 3,
    "韩服": 4,
}

SERVER_FULL_NAMES = ["日服", "国际服", "台服", "国服", "韩服"]

DIFFICULTY_NAMES = {
    "ez": 0,
    "easy": 0,
    "简单": 0,
    "nm": 1,
    "normal": 1,
    "普通": 1,
    "hd": 2,
    "hard": 2,
    "困难": 2,
    "ex": 3,
    "expert": 3,
    "专家": 3,
    "sp": 4,
    "special": 4,
    "特殊": 4,
}

CAR_KEYWORDS = {
    "q1",
    "q2",
    "q3",
    "q4",
    "Q1",
    "Q2",
    "Q3",
    "Q4",
    "缺1",
    "缺2",
    "缺3",
    "缺4",
    "差1",
    "差2",
    "差3",
    "差4",
    "3火",
    "三火",
    "3把",
    "三把",
    "打满",
    "清火",
    "奇迹",
    "中途",
    "大e",
    "大分e",
    "exi",
    "大分跳",
    "大跳",
    "大a",
    "大s",
    "大分a",
    "大分s",
    "长途",
    "生日车",
    "军训",
    "禁fc",
}

FAKE_CAR_KEYWORDS = {
    "114514",
    "野兽",
    "恶臭",
    "1919",
    "下北泽",
    "粪",
    "粞",
    "臭",
    "11451",
    "xiabeize",
    "雀魂",
    "麻将",
    "打牌",
    "maj",
    "麻",
    "[",
    "]",
    "断幺",
    "qq.com",
    "腾讯会议",
    "master",
    "疯狂星期四",
    "离开了我们",
    "日元",
    "av",
    "bv",
}

ROOM_PATTERN = re.compile(r"^(\d{5,6})(.*)$")


def server_id_to_name(server: int) -> str:
    try:
        return SERVER_FULL_NAMES[int(server)]
    except Exception:
        return str(server)


def parse_server_name(server: str) -> int:
    key = str(server or "").strip().lower()
    if key in SERVER_NAMES:
        return SERVER_NAMES[key]
    raise ValueError("错误: 服务器名未能匹配任何服务器")


def parse_difficulty(text: str | None, default: int = 3) -> int:
    if not text:
        return default
    key = text.strip().lower()
    if key in DIFFICULTY_NAMES:
        return DIFFICULTY_NAMES[key]
    raise ValueError("错误: 难度名未能匹配任何难度")


def split_args(text: str) -> list[str]:
    return [part for part in text.strip().split() if part]


def is_room_message(text: str) -> tuple[int, str] | None:
    match = ROOM_PATTERN.match(text.strip())
    if not match:
        return None
    return int(match.group(1)), match.group(0)


def looks_like_car(text: str) -> bool:
    return any(keyword in text for keyword in CAR_KEYWORDS) and not any(
        keyword in text for keyword in FAKE_CAR_KEYWORDS
    )


def strip_command(message: str, names: set[str]) -> str:
    raw = message.strip()
    raw_no_slash = raw[1:].lstrip() if raw.startswith("/") else raw
    for name in sorted(names, key=len, reverse=True):
        if raw_no_slash == name:
            return ""
        if raw_no_slash.startswith(name + " "):
            return raw_no_slash[len(name) :].strip()
    return raw_no_slash


def save_base64_image(cache_dir: Path, content: str) -> str:
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"tsugu_{uuid.uuid4().hex}.png"
    path.write_bytes(base64.b64decode(content))
    return str(path)


def response_to_chain(response: Any, cache_dir: Path) -> list[Any]:
    if isinstance(response, dict) and response.get("status") == "failed":
        return [Comp.Plain(str(response.get("data", "请求失败")))]

    if not isinstance(response, list):
        return [Comp.Plain(str(response))]

    chain: list[Any] = []
    for item in response:
        if not isinstance(item, dict):
            chain.append(Comp.Plain(str(item)))
            continue
        if item.get("type") == "base64":
            chain.append(Comp.Image.fromFileSystem(save_base64_image(cache_dir, item["string"])))
        else:
            chain.append(Comp.Plain(str(item.get("string", ""))))
    return chain or [Comp.Plain("没有返回内容")]
