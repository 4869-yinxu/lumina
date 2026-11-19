import pytest

from lumina.agent.reminders import (
    ReminderScheduler,
    _fire_reminder,
    _set_client,
    schedule_cron_tool,
    schedule_reminder_tool,
)


class FakeClient:
    def __init__(self):
        self.calls = []

    async def call_action(self, action, params):
        self.calls.append((action, params))
        return {}


@pytest.mark.asyncio
async def test_schedule_list_cancel(tmp_path):
    client = FakeClient()
    s = ReminderScheduler(client, str(tmp_path / "sched.db"))
    try:
        r = await s.schedule(
            {"group_id": 1, "user_id": 2, "delay_seconds": 3600, "message": "做作业"}
        )
        assert r["scheduled"] is True
        assert r["id"]
        jobs = s.list_jobs()
        assert len(jobs) == 1
        c = s.cancel(jobs[0]["id"])
        assert c["cancelled"] is True
        assert s.list_jobs() == []
    finally:
        s.scheduler.shutdown(wait=False)


@pytest.mark.asyncio
async def test_schedule_cron_invalid(tmp_path):
    client = FakeClient()
    s = ReminderScheduler(client, str(tmp_path / "sched.db"))
    try:
        r = await s.schedule_cron({"message": "x", "cron": "bad"})
        assert "error" in r
    finally:
        s.scheduler.shutdown(wait=False)


@pytest.mark.asyncio
async def test_schedule_cron_valid(tmp_path):
    client = FakeClient()
    s = ReminderScheduler(client, str(tmp_path / "sched.db"))
    try:
        r = await s.schedule_cron({"user_id": 2, "cron": "0 8 * * *", "message": "做作业"})
        assert r["scheduled"] is True
        assert len(s.list_jobs()) == 1
    finally:
        s.scheduler.shutdown(wait=False)


@pytest.mark.asyncio
async def test_fire_reminder_sends_at_message():
    client = FakeClient()
    _set_client(client)
    await _fire_reminder(1, 2, "做作业")
    action, params = client.calls[0]
    assert action == "send_group_msg"
    assert params["group_id"] == 1
    assert params["message"][0]["type"] == "at"
    assert params["message"][0]["data"]["qq"] == "2"


@pytest.mark.asyncio
async def test_fire_reminder_private():
    client = FakeClient()
    _set_client(client)
    await _fire_reminder(None, 2, "做作业")
    action, params = client.calls[0]
    assert action == "send_private_msg"
    assert params["user_id"] == 2


@pytest.mark.asyncio
async def test_tool_shapes(tmp_path):
    client = FakeClient()
    s = ReminderScheduler(client, str(tmp_path / "sched.db"))
    try:
        assert schedule_reminder_tool(s).to_openai()["function"]["name"] == "schedule_reminder"
        assert schedule_cron_tool(s).to_openai()["function"]["name"] == "schedule_cron"
    finally:
        s.scheduler.shutdown(wait=False)
