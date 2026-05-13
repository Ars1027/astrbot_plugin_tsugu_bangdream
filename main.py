from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register

from .tsugu_client import TsuguClient, TsuguClientError, now_ms
from .utils import (
    is_room_message,
    looks_like_car,
    parse_difficulty,
    parse_server_name,
    response_to_chain,
    server_id_to_name,
    split_args,
    strip_command,
)


QUERY_COMMANDS = {
    "查玩家",
    "查询玩家",
    "查卡",
    "查卡牌",
    "查卡面",
    "查卡插画",
    "查插画",
    "查角色",
    "查活动",
    "查曲",
    "查谱面",
    "随机曲",
    "随机",
    "查询分数表",
    "查分数表",
    "查询分数榜",
    "查分数榜",
    "查试炼",
    "查stage",
    "查舞台",
    "查festival",
    "查5v5",
    "查卡池",
    "ycx",
    "ycxall",
    "myycx",
    "lsycx",
    "抽卡模拟",
    "ycm",
    "有车吗",
    "车来",
}


@register(
    "astrbot_plugin_tsugu_bangdream",
    "Codex",
    "Tsugu BanG Dream! Bot 的 AstrBot 前端适配插件",
    "v0.1.0",
)
class TsuguBangDreamPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config

        self.backend_url = str(
            config.get("backend_url", "http://127.0.0.1:9999") or ""
        ).rstrip("/")
        self.data_backend_url = str(config.get("data_backend_url", "") or "").rstrip(
            "/"
        )
        self.use_easy_bg = bool(config.get("use_easy_bg", False))
        self.compress = bool(config.get("compress", True))
        self.timeout = max(1, int(config.get("timeout", 30) or 30))
        self.retries = max(0, int(config.get("retries", 2) or 2))
        self.proxy = str(config.get("proxy", "") or "") or None
        self.bandori_station_token = str(
            config.get("bandori_station_token", "") or ""
        ).strip()
        self.auto_forward_room = bool(config.get("auto_forward_room", True))
        self.platform_name = str(config.get("platform_name", "red") or "red").strip()

        self.client = TsuguClient(
            self.backend_url,
            self.data_backend_url or self.backend_url,
            timeout=self.timeout,
            proxy=self.proxy,
            retries=self.retries,
        )
        self.cache_dir = Path(__file__).resolve().parent / "cache"
        self.pending: dict[str, dict[str, Any]] = {}

    async def initialize(self):
        await self.client.open()
        self.cache_dir.mkdir(exist_ok=True)
        self._clean_cache()
        logger.info(f"Tsugu AstrBot 插件已初始化，后端: {self.backend_url}")

    async def terminate(self):
        await self.client.close()
        logger.info("Tsugu AstrBot 插件已卸载")

    def _clean_cache(self, max_age_seconds: int = 3600):
        try:
            now = time.time()
            for file in self.cache_dir.glob("tsugu_*.png"):
                if now - file.stat().st_mtime > max_age_seconds:
                    file.unlink(missing_ok=True)
        except Exception as exc:
            logger.warning(f"清理 Tsugu 图片缓存失败: {exc}")

    def _sender_id(self, event: AstrMessageEvent) -> str:
        try:
            return str(event.get_sender_id())
        except Exception:
            return "unknown"

    def _sender_name(self, event: AstrMessageEvent) -> str:
        try:
            return str(event.get_sender_name())
        except Exception:
            return self._sender_id(event)

    def _platform(self, event: AstrMessageEvent) -> str:
        # Tsugu 历史上 QQ/OneBot 生态常映射到 red；这里默认 red，可在配置中覆盖。
        return self.platform_name or "red"

    def _args(self, event: AstrMessageEvent, *names: str) -> str:
        return strip_command(event.message_str or "", set(names))

    async def _send_response(self, event: AstrMessageEvent, response: Any):
        yield event.chain_result(response_to_chain(response, self.cache_dir))

    async def _call_query(self, path: str, payload: dict[str, Any]):
        payload.setdefault("compress", self.compress)
        return await self.client.post(path, payload)

    async def _get_user(self, event: AstrMessageEvent) -> dict[str, Any]:
        response = await self.client.post(
            "/user/getUserData",
            {"platform": self._platform(event), "userId": self._sender_id(event)},
            use_data_backend=True,
        )
        if response.get("status") != "success":
            raise TsuguClientError(str(response.get("data", "获取用户数据失败")))
        return response["data"]

    async def _change_user(self, event: AstrMessageEvent, update: dict[str, Any]) -> str:
        response = await self.client.post(
            "/user/changeUserData",
            {
                "platform": self._platform(event),
                "userId": self._sender_id(event),
                "update": update,
            },
            use_data_backend=True,
        )
        if response.get("status") == "success":
            return "设置成功"
        return str(response.get("data", "设置失败"))

    async def _server_from_text(self, text: str) -> int:
        try:
            return parse_server_name(text)
        except ValueError:
            response = await self.client.post("/fuzzySearch", {"text": text})
            servers = response.get("data", {}).get("server", [])
            if servers and servers[0] in (0, 1, 2, 3, 4):
                return int(servers[0])
            raise

    async def _displayed_servers(self, event: AstrMessageEvent) -> list[int]:
        return list((await self._get_user(event)).get("displayedServerList") or [3, 0])

    async def _main_server(self, event: AstrMessageEvent) -> int:
        return int((await self._get_user(event)).get("mainServer", 3))

    async def _player_from_user(
        self,
        event: AstrMessageEvent,
        index: int | None = None,
        server: int | None = None,
    ) -> dict[str, Any]:
        user = await self._get_user(event)
        players = user.get("userPlayerList") or []
        if not players:
            raise TsuguClientError("未绑定任何玩家")
        if index is not None:
            if index < 1 or index > len(players):
                raise TsuguClientError("错误: 无效的绑定信息ID")
            return players[index - 1]
        server = int(server if server is not None else user.get("mainServer", 3))
        default_index = int(user.get("userPlayerIndex", 0))
        if 0 <= default_index < len(players) and int(players[default_index]["server"]) == server:
            return players[default_index]
        for player in players:
            if int(player["server"]) == server:
                return player
        raise TsuguClientError("用户在对应服务器上未绑定 player")

    async def _handle_query_command(self, event: AstrMessageEvent, command: str, arg_text: str):
        args = split_args(arg_text)
        user_id = self._sender_id(event)
        platform = self._platform(event)

        if command in {"ycm", "有车吗", "车来"}:
            rooms = await self.client.get("/station/queryAllRoom", use_data_backend=True)
            if rooms.get("status") != "success":
                return rooms.get("data", "获取车牌失败")
            room_list = rooms.get("data") or []
            if arg_text.strip():
                keyword = arg_text.strip()
                room_list = [
                    room
                    for room in room_list
                    if keyword in str(room.get("rawMessage", ""))
                ]
            if not room_list:
                return "myc"
            return await self._call_query("/roomList", {"roomList": room_list})

        if command in {"查玩家", "查询玩家"}:
            if not args:
                return "错误: 未指定玩家ID"
            player_id = int(args[0])
            server = await self._server_from_text(args[1]) if len(args) > 1 else await self._main_server(event)
            return await self._call_query(
                "/searchPlayer",
                {"playerId": player_id, "mainServer": server, "useEasyBG": self.use_easy_bg},
            )

        if command in {"查卡", "查卡牌"}:
            return await self._call_query(
                "/searchCard",
                {
                    "displayedServerList": await self._displayed_servers(event),
                    "text": arg_text,
                    "useEasyBG": self.use_easy_bg,
                },
            )

        if command in {"查卡面", "查卡插画", "查插画"}:
            if not args:
                return "错误: 未指定卡牌ID"
            return await self._call_query("/getCardIllustration", {"cardId": int(args[0])})

        if command == "查角色":
            return await self._call_query(
                "/searchCharacter",
                {"displayedServerList": await self._displayed_servers(event), "text": arg_text},
            )

        if command == "查活动":
            return await self._call_query(
                "/searchEvent",
                {
                    "displayedServerList": await self._displayed_servers(event),
                    "text": arg_text,
                    "useEasyBG": self.use_easy_bg,
                },
            )

        if command == "查曲":
            return await self._call_query(
                "/searchSong",
                {"displayedServerList": await self._displayed_servers(event), "text": arg_text},
            )

        if command == "查谱面":
            if not args:
                return "错误: 未指定歌曲ID"
            difficulty = parse_difficulty(args[1] if len(args) > 1 else None)
            return await self._call_query(
                "/songChart",
                {
                    "displayedServerList": await self._displayed_servers(event),
                    "songId": int(args[0]),
                    "difficultyId": difficulty,
                },
            )

        if command in {"随机曲", "随机"}:
            return await self._call_query(
                "/songRandom",
                {"mainServer": await self._main_server(event), "text": arg_text},
            )

        if command in {"查询分数表", "查分数表", "查询分数榜", "查分数榜"}:
            server = await self._server_from_text(args[0]) if args else await self._main_server(event)
            return await self._call_query(
                "/songMeta",
                {
                    "displayedServerList": await self._displayed_servers(event),
                    "mainServer": server,
                },
            )

        if command in {"查试炼", "查stage", "查舞台", "查festival", "查5v5"}:
            meta = "-m" in args
            event_ids = [arg for arg in args if arg != "-m"]
            event_id = int(event_ids[0]) if event_ids else None
            return await self._call_query(
                "/eventStage",
                {
                    "mainServer": await self._main_server(event),
                    "eventId": event_id,
                    "meta": meta,
                },
            )

        if command == "查卡池":
            if not args:
                return "错误: 未指定卡池ID"
            return await self._call_query(
                "/searchGacha",
                {
                    "displayedServerList": await self._displayed_servers(event),
                    "gachaId": int(args[0]),
                    "useEasyBG": self.use_easy_bg,
                },
            )

        if command == "ycx":
            if not args:
                return "错误: 未指定档位"
            tier = int(args[0])
            event_id = int(args[1]) if len(args) > 1 and args[1].isdigit() else None
            server_name = args[2] if len(args) > 2 else (args[1] if len(args) > 1 and not args[1].isdigit() else None)
            server = await self._server_from_text(server_name) if server_name else await self._main_server(event)
            return await self._call_query(
                "/cutoffDetail",
                {"mainServer": server, "tier": tier, "eventId": event_id},
            )

        if command in {"ycxall", "myycx"}:
            event_id = int(args[0]) if args and args[0].isdigit() else None
            server_name = args[1] if len(args) > 1 else (args[0] if args and not args[0].isdigit() else None)
            server = await self._server_from_text(server_name) if server_name else await self._main_server(event)
            return await self._call_query(
                "/cutoffAll",
                {"mainServer": server, "eventId": event_id},
            )

        if command == "lsycx":
            if not args:
                return "错误: 未指定档位"
            tier = int(args[0])
            event_id = int(args[1]) if len(args) > 1 and args[1].isdigit() else None
            server_name = args[2] if len(args) > 2 else (args[1] if len(args) > 1 and not args[1].isdigit() else None)
            server = await self._server_from_text(server_name) if server_name else await self._main_server(event)
            return await self._call_query(
                "/cutoffListOfRecentEvent",
                {"mainServer": server, "tier": tier, "eventId": event_id},
            )

        if command == "抽卡模拟":
            times = int(args[0]) if args else None
            gacha_id = int(args[1]) if len(args) > 1 else None
            return await self._call_query(
                "/gachaSimulate",
                {
                    "mainServer": await self._main_server(event),
                    "times": times,
                    "gachaId": gacha_id,
                },
            )

        return "暂不支持该指令"

    async def _run_query(self, event: AstrMessageEvent, command: str, arg_text: str):
        event.stop_event()
        try:
            response = await self._handle_query_command(event, command, arg_text)
        except Exception as exc:
            logger.warning(f"Tsugu 指令执行失败: {exc}")
            response = f"错误: {exc}"
        async for result in self._send_response(event, response):
            yield result

    async def _start_bind(self, event: AstrMessageEvent, bind_type: str, server_name: str | None):
        user_id = self._sender_id(event)
        server = await self._server_from_text(server_name) if server_name else await self._main_server(event)
        if bind_type == "unbind":
            player = await self._player_from_user(event, server=server)
            player_id = int(player["playerId"])
        else:
            player_id = None

        response = await self.client.post(
            "/user/bindPlayerRequest",
            {"platform": self._platform(event), "userId": user_id},
            use_data_backend=True,
        )
        if response.get("status") != "success":
            return str(response.get("data", "请求验证码失败"))

        verify_code = response["data"]["verifyCode"]
        self.pending[user_id] = {
            "type": bind_type,
            "server": server,
            "player_id": player_id,
            "expire": time.time() + 600,
        }
        action = "绑定" if bind_type == "bind" else "解除绑定"
        extra = "" if player_id is None else f" 玩家ID: {player_id}"
        return (
            f"正在{action}来自 {server_id_to_name(server)} 的账号{extra}\n"
            "请将你的游戏内评论/个性签名，或当前卡组名改为下面的验证码，"
            "然后直接发送玩家ID继续：\n"
            f"{verify_code}"
        )

    async def _finish_pending(self, event: AstrMessageEvent):
        user_id = self._sender_id(event)
        pending = self.pending.get(user_id)
        if not pending:
            return None
        if time.time() > pending["expire"]:
            self.pending.pop(user_id, None)
            return "绑定流程已超时，请重新发起。"

        text = (event.message_str or "").strip()
        if pending["type"] == "bind":
            if not text.isdigit():
                return "错误: 无效的玩家ID，请直接发送数字玩家ID。"
            player_id = int(text)
        else:
            player_id = int(pending["player_id"])

        response = await self.client.post(
            "/user/bindPlayerVerification",
            {
                "platform": self._platform(event),
                "userId": user_id,
                "server": int(pending["server"]),
                "playerId": player_id,
                "bindingAction": pending["type"],
            },
            use_data_backend=True,
        )
        if response.get("status") == "success":
            self.pending.pop(user_id, None)
            if pending["type"] == "bind":
                return await self._call_query(
                    "/searchPlayer",
                    {
                        "playerId": player_id,
                        "mainServer": int(pending["server"]),
                        "useEasyBG": self.use_easy_bg,
                    },
                )
            return str(response.get("data", "解除绑定成功"))
        return str(response.get("data", "验证失败"))

    async def _forward_room_if_needed(self, event: AstrMessageEvent):
        if not self.auto_forward_room:
            return
        text = event.message_str or ""
        room = is_room_message(text)
        if not room or not looks_like_car(text):
            return
        try:
            user = await self._get_user(event)
            if not user.get("shareRoomNumber", True):
                return
            await self.client.post(
                "/station/submitRoomNumber",
                {
                    "number": room[0],
                    "rawMessage": room[1],
                    "platform": self._platform(event),
                    "userId": self._sender_id(event),
                    "userName": self._sender_name(event),
                    "time": now_ms(),
                    "bandoriStationToken": self.bandori_station_token or None,
                },
                use_data_backend=True,
            )
            logger.info(f"已转发车牌: {room[1]}")
        except Exception as exc:
            logger.debug(f"车牌转发失败: {exc}")

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_any_message(self, event: AstrMessageEvent):
        pending_response = await self._finish_pending(event)
        if pending_response is not None:
            event.stop_event()
            async for result in self._send_response(event, pending_response):
                yield result
            return
        await self._forward_room_if_needed(event)

    @filter.command("开启车牌转发")
    async def open_forward(self, event: AstrMessageEvent):
        event.stop_event()
        yield event.plain_result(await self._change_user(event, {"shareRoomNumber": True}))

    @filter.command("关闭车牌转发")
    async def close_forward(self, event: AstrMessageEvent):
        event.stop_event()
        yield event.plain_result(await self._change_user(event, {"shareRoomNumber": False}))

    @filter.command("绑定玩家")
    async def bind_player(self, event: AstrMessageEvent):
        event.stop_event()
        try:
            args = split_args(self._args(event, "绑定玩家"))
            yield event.plain_result(await self._start_bind(event, "bind", args[0] if args else None))
        except Exception as exc:
            yield event.plain_result(f"错误: {exc}")

    @filter.command("解除绑定", alias={"解绑玩家"})
    async def unbind_player(self, event: AstrMessageEvent):
        event.stop_event()
        try:
            args = split_args(self._args(event, "解除绑定", "解绑玩家"))
            yield event.plain_result(await self._start_bind(event, "unbind", args[0] if args else None))
        except Exception as exc:
            yield event.plain_result(f"错误: {exc}")

    @filter.command("主服务器", alias={"服务器模式", "切换服务器"})
    async def main_server(self, event: AstrMessageEvent):
        event.stop_event()
        args = split_args(self._args(event, "主服务器", "服务器模式", "切换服务器"))
        if not args:
            yield event.plain_result("错误: 请指定服务器，例如：主服务器 cn")
            return
        try:
            server = await self._server_from_text(args[0])
            await self._change_user(event, {"mainServer": server})
            yield event.plain_result(f"已切换到{server_id_to_name(server)}模式")
        except Exception as exc:
            yield event.plain_result(f"错误: {exc}")

    @filter.command("设置显示服务器", alias={"默认服务器", "设置默认服务器"})
    async def display_servers(self, event: AstrMessageEvent):
        event.stop_event()
        args = split_args(self._args(event, "设置显示服务器", "默认服务器", "设置默认服务器"))
        if not args:
            yield event.plain_result("错误: 请指定至少一个服务器")
            return
        try:
            servers = [parse_server_name(arg) for arg in args]
            if len(set(servers)) != len(servers):
                yield event.plain_result("错误: 指定了重复的服务器")
                return
            await self._change_user(event, {"displayedServerList": servers})
            yield event.plain_result(
                "成功切换默认显示服务器顺序: "
                + ", ".join(server_id_to_name(server) for server in servers)
            )
        except Exception as exc:
            yield event.plain_result(f"错误: {exc}")

    @filter.command("玩家状态")
    async def player_status(self, event: AstrMessageEvent):
        args = split_args(self._args(event, "玩家状态"))
        try:
            index = int(args[0]) if args and args[0].isdigit() else None
            server = await self._server_from_text(args[0]) if args and not args[0].isdigit() else None
            player = await self._player_from_user(event, index=index, server=server)
            async for result in self._run_query(
                event,
                "查玩家",
                f"{player['playerId']} {player['server']}",
            ):
                yield result
        except Exception as exc:
            event.stop_event()
            yield event.plain_result(f"错误: {exc}")

    @filter.command("玩家状态列表", alias={"玩家列表", "玩家信息列表"})
    async def player_list(self, event: AstrMessageEvent):
        event.stop_event()
        try:
            user = await self._get_user(event)
            players = user.get("userPlayerList") or []
            lines = ["已绑定玩家列表:"]
            if not players:
                lines = ["未绑定任何玩家"]
            else:
                for index, player in enumerate(players, start=1):
                    lines.append(
                        f"{index}. {server_id_to_name(player['server'])}: {player['playerId']}"
                    )
                lines.append(f"当前默认玩家绑定信息ID: {int(user.get('userPlayerIndex', 0)) + 1}")
            lines.append(f"当前主服务器: {server_id_to_name(user.get('mainServer', 3))}")
            lines.append(
                "默认显示服务器顺序: "
                + ", ".join(server_id_to_name(server) for server in user.get("displayedServerList", [3, 0]))
            )
            yield event.plain_result("\n".join(lines))
        except Exception as exc:
            yield event.plain_result(f"错误: {exc}")

    @filter.command("玩家默认ID", alias={"默认玩家ID", "默认玩家", "玩家ID"})
    async def switch_player_index(self, event: AstrMessageEvent):
        event.stop_event()
        args = split_args(self._args(event, "玩家默认ID", "默认玩家ID", "默认玩家", "玩家ID"))
        if not args or not args[0].isdigit():
            yield event.plain_result("错误: 请指定默认玩家绑定信息ID")
            return
        try:
            index = int(args[0])
            user = await self._get_user(event)
            if index < 1 or index > len(user.get("userPlayerList") or []):
                yield event.plain_result("错误: 无效的绑定信息ID")
                return
            await self._change_user(event, {"userPlayerIndex": index - 1})
            yield event.plain_result(f"已切换至绑定信息ID: {index}")
        except Exception as exc:
            yield event.plain_result(f"错误: {exc}")

    @filter.command("ycm", alias={"有车吗", "车来"})
    async def ycm(self, event: AstrMessageEvent):
        async for result in self._run_query(event, "ycm", self._args(event, "ycm", "有车吗", "车来")):
            yield result

    @filter.command("查玩家", alias={"查询玩家"})
    async def search_player(self, event: AstrMessageEvent):
        async for result in self._run_query(event, "查玩家", self._args(event, "查玩家", "查询玩家")):
            yield result

    @filter.command("查卡", alias={"查卡牌"})
    async def search_card(self, event: AstrMessageEvent):
        async for result in self._run_query(event, "查卡", self._args(event, "查卡", "查卡牌")):
            yield result

    @filter.command("查卡面", alias={"查卡插画", "查插画"})
    async def card_illustration(self, event: AstrMessageEvent):
        async for result in self._run_query(event, "查卡面", self._args(event, "查卡面", "查卡插画", "查插画")):
            yield result

    @filter.command("查角色")
    async def search_character(self, event: AstrMessageEvent):
        async for result in self._run_query(event, "查角色", self._args(event, "查角色")):
            yield result

    @filter.command("查活动")
    async def search_event(self, event: AstrMessageEvent):
        async for result in self._run_query(event, "查活动", self._args(event, "查活动")):
            yield result

    @filter.command("查曲")
    async def search_song(self, event: AstrMessageEvent):
        async for result in self._run_query(event, "查曲", self._args(event, "查曲")):
            yield result

    @filter.command("查谱面")
    async def song_chart(self, event: AstrMessageEvent):
        async for result in self._run_query(event, "查谱面", self._args(event, "查谱面")):
            yield result

    @filter.command("随机曲", alias={"随机"})
    async def random_song(self, event: AstrMessageEvent):
        async for result in self._run_query(event, "随机曲", self._args(event, "随机曲", "随机")):
            yield result

    @filter.command("查询分数表", alias={"查分数表", "查询分数榜", "查分数榜"})
    async def song_meta(self, event: AstrMessageEvent):
        async for result in self._run_query(event, "查询分数表", self._args(event, "查询分数表", "查分数表", "查询分数榜", "查分数榜")):
            yield result

    @filter.command("查试炼", alias={"查stage", "查舞台", "查festival", "查5v5"})
    async def event_stage(self, event: AstrMessageEvent):
        async for result in self._run_query(event, "查试炼", self._args(event, "查试炼", "查stage", "查舞台", "查festival", "查5v5")):
            yield result

    @filter.command("查卡池")
    async def search_gacha(self, event: AstrMessageEvent):
        async for result in self._run_query(event, "查卡池", self._args(event, "查卡池")):
            yield result

    @filter.command("ycx")
    async def ycx(self, event: AstrMessageEvent):
        async for result in self._run_query(event, "ycx", self._args(event, "ycx")):
            yield result

    @filter.command("ycxall", alias={"myycx"})
    async def ycx_all(self, event: AstrMessageEvent):
        async for result in self._run_query(event, "ycxall", self._args(event, "ycxall", "myycx")):
            yield result

    @filter.command("lsycx")
    async def lsycx(self, event: AstrMessageEvent):
        async for result in self._run_query(event, "lsycx", self._args(event, "lsycx")):
            yield result

    @filter.command("抽卡模拟")
    async def gacha_simulate(self, event: AstrMessageEvent):
        async for result in self._run_query(event, "抽卡模拟", self._args(event, "抽卡模拟")):
            yield result
