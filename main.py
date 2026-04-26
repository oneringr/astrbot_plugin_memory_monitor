import asyncio
import re
import time
from typing import Optional

import psutil
from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register


@register(
    "memory_monitor",
    "ChatGPT",
    "监控本机内存占用，超过阈值后在群里@指定用户告警。",
    "1.2.0",
)
class MemoryMonitorPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self._task: Optional[asyncio.Task] = None
        self._is_running = True
        self._last_alert_ts: float = 0.0
        self._last_above_threshold = False

    async def initialize(self):
        if not bool(self.config.get("enable_monitor", True)):
            logger.info("[memory_monitor] 监控未启用，跳过启动。")
            return
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("[memory_monitor] 内存监控任务已启动。")

    async def terminate(self):
        self._is_running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("[memory_monitor] 内存监控任务已停止。")

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def detect_memchk_keyword(self, event: AstrMessageEvent):
        message = (event.message_str or "").strip()
        if not re.search(r"\bmemchk\b", message, flags=re.IGNORECASE):
            return

        vm = psutil.virtual_memory()
        percent = float(vm.percent)
        total_gb = vm.total / (1024 ** 3)
        used_gb = (vm.total - vm.available) / (1024 ** 3)
        threshold = int(self.config.get("mem_threshold_percent", 80) or 80)
        status = "⚠️ 高于阈值" if percent >= threshold else "✅ 正常"

        yield event.plain_result(
            f"{status}\n"
            f"当前内存占用：{percent:.1f}%（阈值 {threshold}%）\n"
            f"已用/总计：{used_gb:.2f}GB / {total_gb:.2f}GB"
        )

    async def _monitor_loop(self):
        while self._is_running:
            interval = max(5, int(self.config.get("check_interval_seconds", 30) or 30))
            try:
                await self._check_memory_and_alert()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"[memory_monitor] 监控异常: {e}", exc_info=True)
            await asyncio.sleep(interval)

    async def _check_memory_and_alert(self):
        threshold = int(self.config.get("mem_threshold_percent", 80) or 80)
        cooldown_min = max(0, int(self.config.get("alert_cooldown_minutes", 30) or 30))
        send_recovery = bool(self.config.get("send_recovery_notice", False))

        vm = psutil.virtual_memory()
        current_percent = float(vm.percent)
        above = current_percent >= threshold

        if send_recovery and self._last_above_threshold and not above:
            await self._send_group_alert(
                f"✅ 内存已恢复正常：当前 {current_percent:.1f}%（阈值 {threshold}%）"
            )

        self._last_above_threshold = above
        if not above:
            return

        now = time.time()
        if cooldown_min > 0 and now - self._last_alert_ts < cooldown_min * 60:
            return

        total_gb = vm.total / (1024 ** 3)
        used_gb = (vm.total - vm.available) / (1024 ** 3)
        custom_template = self.config.get("alert_message", "")
        msg = (
            custom_template.strip()
            if isinstance(custom_template, str) and custom_template.strip()
            else (
                "⚠️ 内存告警：当前占用 {percent:.1f}%（阈值 {threshold}%）\n"
                "已用/总计：{used:.2f}GB / {total:.2f}GB"
            )
        )
        msg = msg.format(
            percent=current_percent,
            threshold=threshold,
            used=used_gb,
            total=total_gb,
        )

        ok = await self._send_group_alert(msg)
        if ok:
            self._last_alert_ts = now

    def _get_client(self):
        try:
            for adapter in self.context.platform_manager.get_insts():
                if hasattr(adapter, "bot") and adapter.bot and hasattr(adapter.bot, "api"):
                    return adapter.bot
        except Exception as e:
            logger.debug(f"[memory_monitor] 获取适配器失败: {e}")
        return None

    def _parse_target_user_ids(self) -> list[str]:
        raw_multi = str(self.config.get("target_user_ids", "")).strip()

        tokens = [t.strip() for t in re.split(r"[\s,;，；]+", raw_multi) if t.strip()]
        result: list[str] = []
        seen = set()
        for token in tokens:
            if not token.isdigit() or token in seen:
                continue
            seen.add(token)
            result.append(token)
        return result

    async def _send_group_alert(self, text: str) -> bool:
        group_id = str(self.config.get("target_group_id", "")).strip()
        user_ids = self._parse_target_user_ids()

        if not group_id.isdigit() or not user_ids:
            logger.warning(
                "[memory_monitor] 发送告警失败：请正确配置 target_group_id 和 target_user_ids。"
            )
            return False

        client = self._get_client()
        if not client:
            logger.warning("[memory_monitor] 发送告警失败：未找到可用适配器客户端。")
            return False

        message = []
        for uid in user_ids:
            message.append({"type": "at", "data": {"qq": uid}})
            message.append({"type": "text", "data": {"text": " "}})
        message.append({"type": "text", "data": {"text": text}})

        try:
            await client.api.call_action(
                "send_group_msg",
                group_id=int(group_id),
                message=message,
            )
            logger.info(f"[memory_monitor] 告警消息发送成功，@人数: {len(user_ids)}")
            return True
        except Exception as e:
            logger.error(f"[memory_monitor] 发送告警异常: {e}", exc_info=True)
            return False
