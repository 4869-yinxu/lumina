from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from lumina.tools.registry import Tool

_client = None
_agent = None


def _set_client(client):
    global _client
    _client = client


def _set_agent(agent):
    global _agent
    _agent = agent


async def _fire_reminder(group_id, user_id, message):
    """一次性提醒：直接发送写好的文字。"""
    if group_id:
        payload = [
            {"type": "at", "data": {"qq": str(user_id)}},
            {"type": "text", "data": {"text": " " + message}},
        ]
        await _client.call_action(
            "send_group_msg", {"group_id": group_id, "message": payload}
        )
    else:
        await _client.call_action(
            "send_private_msg", {"user_id": user_id, "message": message}
        )


async def _fire_task(group_id, user_id, task_prompt):
    """周期/复杂任务：把 task_prompt 交给 agent 真正执行（查天气、联网、推理），再发结果。"""
    context = {
        "scope": f"task:{group_id or user_id}",
        "user_id": user_id,
        "group_id": group_id,
        "nickname": "",
    }
    reply = await _agent.run_task(task_prompt, context)
    if group_id:
        payload = [
            {"type": "at", "data": {"qq": str(user_id)}},
            {"type": "text", "data": {"text": " " + reply}},
        ]
        await _client.call_action(
            "send_group_msg", {"group_id": group_id, "message": payload}
        )
    else:
        await _client.call_action(
            "send_private_msg", {"user_id": user_id, "message": reply}
        )


class ReminderScheduler:
    def __init__(self, client, db_path: str, timezone: str = "Asia/Shanghai"):
        _set_client(client)
        self.timezone = timezone
        self.scheduler = AsyncIOScheduler(timezone=timezone)
        self.scheduler.add_jobstore(
            SQLAlchemyJobStore(url=f"sqlite:///{db_path}"), "default"
        )
        self.scheduler.start()

    async def schedule(self, arguments: dict, context: dict | None = None) -> dict:
        group_id = arguments.get("group_id")
        user_id = arguments.get("user_id")
        delay = int(arguments.get("delay_seconds", 0))
        message = arguments.get("message", "")
        run_at = datetime.now(ZoneInfo(self.timezone)) + timedelta(seconds=delay)
        job = self.scheduler.add_job(
            _fire_reminder,
            DateTrigger(run_date=run_at),
            args=[group_id, user_id, message],
            id=f"remind-{uuid.uuid4().hex[:12]}",
            replace_existing=True,
        )
        return {
            "scheduled": True,
            "id": job.id,
            "run_at": run_at.strftime("%Y-%m-%d %H:%M:%S"),
        }

    async def schedule_cron(self, arguments: dict, context: dict | None = None) -> dict:
        group_id = arguments.get("group_id")
        user_id = arguments.get("user_id")
        task = arguments.get("task") or arguments.get("message", "")
        cron = (arguments.get("cron") or "").strip()
        parts = cron.split()
        if len(parts) != 5:
            return {"error": "cron 必须是 5 段：分 时 日 月 周，例如 '0 23 * * *'"}
        job = self.scheduler.add_job(
            _fire_task,
            CronTrigger(
                minute=parts[0], hour=parts[1], day=parts[2],
                month=parts[3], day_of_week=parts[4],
                timezone=ZoneInfo(self.timezone),
            ),
            args=[group_id, user_id, task],
            id=f"cron-{uuid.uuid4().hex[:12]}",
            replace_existing=True,
        )
        return {"scheduled": True, "id": job.id, "cron": cron}

    def update_job(
        self,
        job_id: str,
        delay_seconds: int | None = None,
        cron: str | None = None,
        content: str | None = None,
    ) -> dict:
        job = self.scheduler.get_job(job_id)
        if not job:
            return {"error": f"任务 {job_id} 不存在"}
        args = list(job.args)
        if content is not None:
            args[2] = content
        if delay_seconds is not None:
            run_at = datetime.now(ZoneInfo(self.timezone)) + timedelta(seconds=int(delay_seconds))
            self.scheduler.reschedule_job(job_id, trigger=DateTrigger(run_date=run_at))
            self.scheduler.modify_job(job_id, args=args)
        elif cron is not None:
            parts = cron.strip().split()
            if len(parts) != 5:
                return {"error": "cron 格式错误"}
            self.scheduler.reschedule_job(
                job_id,
                trigger=CronTrigger(
                    minute=parts[0], hour=parts[1], day=parts[2],
                    month=parts[3], day_of_week=parts[4],
                    timezone=ZoneInfo(self.timezone),
                ),
            )
            self.scheduler.modify_job(job_id, args=args)
        else:
            self.scheduler.modify_job(job_id, args=args)
        return {"updated": True, "id": job_id}

    def list_jobs(self) -> list[dict]:
        out = []
        for j in self.scheduler.get_jobs():
            out.append(
                {
                    "id": j.id,
                    "next_run": (
                        j.next_run_time.strftime("%Y-%m-%d %H:%M:%S")
                        if j.next_run_time
                        else ""
                    ),
                    "args": list(j.args),
                }
            )
        return out

    def cancel(self, job_id: str) -> dict:
        try:
            self.scheduler.remove_job(job_id)
            return {"cancelled": True, "id": job_id}
        except Exception as e:  # noqa: BLE001
            return {"error": str(e)}

    def schedule_once(self, func, args, run_at) -> str:
        """调度一个一次性回调（用于任务截止等）。返回 job id。"""
        job = self.scheduler.add_job(
            func, DateTrigger(run_date=run_at), args=args,
            id=f"once-{uuid.uuid4().hex[:12]}",
        )
        return job.id


def schedule_reminder_tool(scheduler: ReminderScheduler) -> Tool:
    return Tool(
        name="schedule_reminder",
        description=(
            "设定一个一次性提醒：在 delay_seconds 秒后提醒 user_id（群聊会艾特）。"
            "「X分钟后/小时后提醒我」「X点提醒我做某事」「稍后@我」用本工具。"
            "把「我」解析为发送者 user_id，时间换算成 delay_seconds 秒。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "group_id": {"type": "integer", "description": "群号；私聊则省略"},
                "user_id": {"type": "integer", "description": "要提醒的用户 QQ 号"},
                "delay_seconds": {"type": "integer", "description": "延迟多少秒后提醒"},
                "message": {"type": "string", "description": "提醒内容"},
            },
            "required": ["user_id", "delay_seconds", "message"],
        },
        risk="safe",
        category="定时任务",
        run_func=scheduler.schedule,
    )


def schedule_cron_tool(scheduler: ReminderScheduler) -> Tool:
    return Tool(
        name="schedule_cron",
        description=(
            "设定一个周期性重复任务：到点后 agent 会真正执行 task 描述的任务（例如联网查天气、推理）再把结果艾特用户。"
            "cron 为「分 时 日 月 周」5 段（每天8点='0 8 * * *'、每天23点='0 23 * * *'、每周一9点='0 9 * * 1'）。"
            "用户说「每天X点/每周X/每晚」等重复任务时调用。task 要写清要查什么、给出什么建议。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "group_id": {"type": "integer", "description": "群号；私聊则省略"},
                "user_id": {"type": "integer", "description": "要提醒的用户 QQ 号"},
                "cron": {"type": "string", "description": "5 段 cron 表达式，如 '0 23 * * *'"},
                "task": {"type": "string", "description": "要执行的任务描述，如「查明天重庆南山天气，给出带伞和穿衣建议」"},
            },
            "required": ["cron", "task"],
        },
        risk="safe",
        category="定时任务",
        run_func=scheduler.schedule_cron,
    )


def list_reminders_tool(scheduler: ReminderScheduler) -> Tool:
    async def run(arguments: dict, context: dict | None = None) -> dict:
        return {"reminders": scheduler.list_jobs()}

    return Tool(
        name="list_reminders",
        description="列出当前所有已设定的提醒/周期任务。",
        parameters={"type": "object", "properties": {}, "required": []},
        risk="safe",
        category="定时任务",
        run_func=run,
    )


def update_reminder_tool(scheduler: ReminderScheduler) -> Tool:
    async def run(arguments: dict, context: dict | None = None) -> dict:
        return scheduler.update_job(
            arguments.get("id", ""),
            delay_seconds=arguments.get("delay_seconds"),
            cron=arguments.get("cron"),
            content=arguments.get("message") or arguments.get("task"),
        )

    return Tool(
        name="update_reminder",
        description=(
            "修改一个已存在的提醒/周期任务：改时间或改内容。"
            "改一次性提醒时间用 delay_seconds；改周期任务用 cron；改内容用 message/task。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "任务 id（来自 list_reminders）"},
                "delay_seconds": {"type": "integer", "description": "新延迟秒数（一次性提醒）"},
                "cron": {"type": "string", "description": "新 cron 表达式（周期任务）"},
                "message": {"type": "string", "description": "新的提醒内容或任务描述"},
            },
            "required": ["id"],
        },
        risk="safe",
        category="定时任务",
        run_func=run,
    )


def cancel_reminder_tool(scheduler: ReminderScheduler) -> Tool:
    async def run(arguments: dict, context: dict | None = None) -> dict:
        return scheduler.cancel(arguments.get("id", ""))

    return Tool(
        name="cancel_reminder",
        description="取消一个提醒/周期任务。",
        parameters={
            "type": "object",
            "properties": {"id": {"type": "string", "description": "任务 id"}},
            "required": ["id"],
        },
        risk="safe",
        category="定时任务",
        run_func=run,
    )
