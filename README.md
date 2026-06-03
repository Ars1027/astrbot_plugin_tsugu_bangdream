<div align="center">

<img src="logo.png" width="256" alt="icon">

# Tsugu BanG Dream Bot

[![AstrBot](https://img.shields.io/badge/AstrBot-Plugin-ff69b4?style=for-the-badge)](https://github.com/AstrBotDevs/AstrBot)
[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg?style=for-the-badge&color=76bad9)](https://www.python.org/)
[![Backend](https://img.shields.io/badge/Tsugu-Backend-FFEE88?style=for-the-badge)](https://github.com/Yamamoto-2/tsugu-bangdream-bot)

_✨ BanG Dream! 少女乐团派对多功能查询、玩家绑定、车牌与档线插件，基于 Tsugu 后端为 AstrBot 提供前端适配。 ✨_



</div>

---

## 配置

默认使用 Tsugu 公共后端：

```text
http://tsugubot.com:8080
```

如需使用自建 Tsugu 后端，可将 `backend_url` 改为你的服务器地址，例如：

```text
http://你的服务器IP:端口号
```

如果 `data_backend_url` 留空，会复用 `backend_url`。使用自建后端时，玩家绑定和车牌功能要求后端启用：

```env
LOCAL_DB=true
```

QQ/NapCat/OneBot 场景建议保持：

```text
platform_name=red
```

### QQ 白名单

插件支持分别限制允许使用功能的 QQ 群聊和私聊用户：

| 配置项 | 填写内容 | 默认行为 |
| --- | --- | --- |
| `group_whitelist` | 允许使用插件的 QQ 群号列表 | 留空则所有群聊可用 |
| `private_whitelist` | 允许私聊使用插件的用户 QQ 号列表 | 留空则所有私聊可用 |

例如，仅允许群 `123456789` 和用户 `987654321` 使用：

```text
group_whitelist=["123456789"]
private_whitelist=["987654321"]
```

白名单仅针对 QQ/NapCat/OneBot 场景。未在白名单中的会话会被静默忽略，不会请求 Tsugu 后端，也不会影响其他插件处理消息。

## 指令

- `查卡 <关键词>`
- `查卡面 <卡牌ID>`
- `查角色 <关键词>`
- `查活动 <关键词>`
- `查曲 <关键词>`
- `查谱面 <歌曲ID> [难度]`
- `随机曲 [关键词]`
- `查询分数表 [服务器]`
- `查试炼 [活动ID] [-m]`
- `查卡池 <卡池ID>`
- `查玩家 <玩家ID> [服务器]`
- `ycx <档位> [活动ID] [服务器]`
- `ycxall [活动ID] [服务器]`
- `lsycx <档位> [活动ID] [服务器]`
- `抽卡模拟 [次数] [卡池ID]`
- `绑定玩家 [服务器]`
- `解除绑定 [服务器]`
- `主服务器 <服务器>`
- `设置显示服务器 <服务器...>`
- `玩家状态 [序号或服务器]`
- `玩家状态列表`
- `玩家默认ID <序号>`
- `开启车牌转发`
- `关闭车牌转发`
- `ycm [关键词]`

服务器可使用 `cn`、`jp`、`tw`、`en`、`kr`，或 `国服`、`日服` 等中文名。

> [!NOTE]
> 本插件参考 [nonebot-plugin-tsugu-bangdream-bot](https://github.com/WindowsSov8forUs/nonebot-plugin-tsugu-bangdream-bot) 的 Python 前端移植实现，将 Tsugu Bot 的主要前端能力适配到 AstrBot。
