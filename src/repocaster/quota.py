from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass, field


@dataclass
class WeeklyQuota:
    repo: str
    week: str
    limit: int
    count: int = 0
    executions: list[dict] = field(default_factory=list)

    @property
    def allowed(self) -> bool:
        return self.count < self.limit


def iso_week(now: dt.datetime | None = None) -> str:
    now = now or dt.datetime.now(dt.UTC)
    year, week, _ = now.isocalendar()
    return f"{year}-W{week:02d}"


def quota_key(repo: str, week: str | None = None) -> str:
    safe_repo = repo.replace("/", "__")
    return f"quotas/week/{week or iso_week()}/{safe_repo}.json"


def load_quota(raw: str | None, repo: str, limit: int, week: str | None = None) -> WeeklyQuota:
    if not raw:
        return WeeklyQuota(repo=repo, week=week or iso_week(), limit=limit)
    data = json.loads(raw)
    return WeeklyQuota(
        repo=data.get("repo", repo),
        week=data.get("week", week or iso_week()),
        limit=int(data.get("limit", limit)),
        count=int(data.get("count", 0)),
        executions=list(data.get("executions", [])),
    )


def record_execution(quota: WeeklyQuota, execution: dict) -> WeeklyQuota:
    if not quota.allowed:
        raise ValueError("weekly quota exceeded")
    quota.count += 1
    quota.executions.append(execution)
    return quota


def dump_quota(quota: WeeklyQuota) -> str:
    return json.dumps(
        {
            "repo": quota.repo,
            "week": quota.week,
            "limit": quota.limit,
            "count": quota.count,
            "executions": quota.executions,
        },
        indent=2,
        sort_keys=True,
    )
