## v0.2.0 - ✨ QQ 白名单

### 新增功能
- **群聊白名单** — 新增 `group_whitelist` 配置，可按 QQ 群号限制允许使用插件的群聊
- **私聊白名单** — 新增 `private_whitelist` 配置，可按用户 QQ 号限制允许私聊使用插件的用户

## v0.1.0 - ✨ 初始版本

### 新增功能
- **Tsugu 前端适配** — 基于 AstrBot 插件体系实现 Tsugu BanG Dream Bot 前端，参考 `nonebot-plugin-tsugu-bangdream-bot` 的 Python 移植思路
- **查询类指令** — 支持查卡、查卡面、查角色、查活动、查曲、查谱面、随机曲、查分数表、查试炼、查卡池、查玩家
- **档线与抽卡** — 支持 `ycx`、`ycxall`、`myycx`、`lsycx` 与抽卡模拟
- **玩家数据** — 支持绑定玩家、解除绑定、主服务器切换、默认显示服务器、玩家状态列表与默认玩家 ID
- **车牌功能** — 支持自动识别并转发车牌，支持 `ycm` / `有车吗` / `车来` 查询车牌
- **自建后端配置** — 支持通过 `backend_url` / `data_backend_url` 指向公共或自建 Tsugu 后端
