# astrbot_plugin_memory_monitor

AstrBot 插件：监控本机内存占用，达到阈值后自动在群聊中 `@` 一个或多个指定用户。

## 功能

- 定时读取本机内存占用（`psutil.virtual_memory()`）
- 内存占用达到阈值后自动发送群消息
- 支持同时 `@` 多个 QQ 用户
- 支持关键词 `memchk`：仅在完整词匹配时触发并返回当前内存占用
- 支持告警冷却，避免反复刷屏
- 支持可选的“恢复正常”通知

## 安装

1. 网页安装或将本插件放到 `AstrBot/data/plugins/astrbot_plugin_memory_monitor`。
2. 在 AstrBot 插件管理中启用插件并填写配置。

## 配置项说明

- `enable_monitor`: 是否启用监控
- `mem_threshold_percent`: 内存告警阈值（百分比）
- `check_interval_seconds`: 检查周期（秒）
- `alert_cooldown_minutes`: 告警冷却时间（分钟）
- `target_group_id`: 发送告警的群号
- `target_user_ids`: 被 @ 的用户 QQ 号列表（支持逗号/分号/空格）
- `alert_message`: 自定义告警消息模板（可选）
  - 支持变量：`{percent}` `{threshold}` `{used}` `{total}`
- `send_recovery_notice`: 内存恢复时发送恢复通知（可选）

## 使用说明

- 自动告警：内存到达阈值后插件主动发送群告警并 @ 配置用户。
- 手动查询：在群聊或私聊发送完整词 `memchk` 即可查看当前内存占用。

## 告警消息示例

```text
@12345678 @87654321 ⚠️ 内存告警：当前占用 87.5%（阈值 80%）
已用/总计：13.99GB / 16.00GB
```

## 关键词查询示例

```text
memchk
✅ 正常
当前内存占用：42.3%（阈值 80%）
已用/总计：6.77GB / 16.00GB
```
