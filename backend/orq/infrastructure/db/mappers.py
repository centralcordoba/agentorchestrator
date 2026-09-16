"""Traducción entre filas y entidades del dominio."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Mapping

from ...domain.audit import AuditAction, AuditEntry
from ...domain.enums import (
    AgentId,
    AgentRunStatus,
    AttachmentKind,
    FileStatus,
    PhiClassification,
    ProviderId,
    RunStatus,
    TraceEventType,
)
from ...domain.plan import Plan, PlanItem
from ...domain.profiles import AgentProfile, PromptVersion
from ...domain.requirement import Attachment, RepoCommit, RepoFile, RepoInfo, Requirement
from ...domain.run import AgentExecution, LLMCall, ProfileSnapshot, Run, TraceEvent, Usage
from .crypto import Cipher


def _aware(value: datetime | None) -> datetime | None:
    """PostgreSQL devuelve fechas con zona; una sin zona se interpreta como UTC."""
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _money(value: Any) -> float:
    if value is None:
        return 0.0
    return float(value) if not isinstance(value, Decimal) else float(value)


def repo_to_json(repo: RepoInfo) -> dict[str, Any]:
    return {
        "provider": repo.provider,
        "owner": repo.owner,
        "name": repo.name,
        "full_name": repo.full_name,
        "html_url": repo.html_url,
        "default_branch": repo.default_branch,
        "branch": repo.branch,
        "base": repo.base,
        "head_sha": repo.head_sha,
        "description": repo.description,
        "range_label": repo.range_label,
        "compare_url": repo.compare_url,
        "ahead_by": repo.ahead_by,
        "commits": [
            {"sha": c.sha, "message": c.message, "author": c.author, "date": c.date, "url": c.url}
            for c in repo.commits
        ],
        "files": [
            {
                "path": f.path,
                "status": f.status.value,
                "additions": f.additions,
                "deletions": f.deletions,
                "has_patch": f.has_patch,
            }
            for f in repo.files
        ],
        "files_truncated": repo.files_truncated,
        "languages": dict(repo.languages),
        "fetched_at": repo.fetched_at.isoformat() if repo.fetched_at else None,
    }


def repo_from_json(data: Mapping[str, Any]) -> RepoInfo:
    fetched = data.get("fetched_at")
    return RepoInfo(
        provider=data["provider"],
        owner=data["owner"],
        name=data["name"],
        full_name=data["full_name"],
        html_url=data["html_url"],
        default_branch=data["default_branch"],
        branch=data["branch"],
        base=data["base"],
        head_sha=data["head_sha"],
        description=data.get("description", ""),
        range_label=data.get("range_label", ""),
        compare_url=data.get("compare_url", ""),
        ahead_by=int(data.get("ahead_by", 0)),
        commits=tuple(
            RepoCommit(
                sha=c["sha"],
                message=c.get("message", ""),
                author=c.get("author", ""),
                date=c.get("date", ""),
                url=c.get("url", ""),
            )
            for c in data.get("commits", ())
        ),
        files=tuple(
            RepoFile(
                path=f["path"],
                status=FileStatus(f["status"]),
                additions=int(f.get("additions", 0)),
                deletions=int(f.get("deletions", 0)),
                has_patch=bool(f.get("has_patch", False)),
            )
            for f in data.get("files", ())
        ),
        files_truncated=bool(data.get("files_truncated", False)),
        languages=dict(data.get("languages", {})),
        fetched_at=datetime.fromisoformat(fetched) if fetched else None,
    )


def requirement_row(requirement: Requirement, cipher: Cipher) -> dict[str, Any]:
    return {
        "id": requirement.id,
        "owner": requirement.owner,
        "created_at": requirement.created_at,
        "phi": requirement.phi.value,
        "phi_set_by": requirement.phi_set_by,
        "title_enc": cipher.encrypt(requirement.title),
        "description_enc": cipher.encrypt(requirement.description),
        "acceptance_criteria_enc": cipher.encrypt_json(list(requirement.acceptance_criteria)),
    }


def attachment_rows(requirement: Requirement, cipher: Cipher) -> list[dict[str, Any]]:
    return [
        {
            "id": a.id,
            "requirement_id": requirement.id,
            "kind": a.kind.value,
            "added_by": a.added_by,
            "added_at": a.added_at,
            "name_enc": cipher.encrypt(a.name),
            "detail_enc": cipher.encrypt(a.detail),
            "repo_enc": cipher.encrypt_json(repo_to_json(a.repo)) if a.repo else None,
        }
        for a in requirement.attachments
    ]


def requirement_from_rows(
    row: Mapping[str, Any], attachments: list[Mapping[str, Any]], cipher: Cipher
) -> Requirement:
    return Requirement(
        id=row["id"],
        title=cipher.decrypt(row["title_enc"]),
        description=cipher.decrypt(row["description_enc"]),
        owner=row["owner"],
        created_at=_aware(row["created_at"]),  # type: ignore[arg-type]
        acceptance_criteria=tuple(cipher.decrypt_json(row["acceptance_criteria_enc"], []) or []),
        phi=PhiClassification(row["phi"]),
        phi_set_by=row["phi_set_by"] or "",
        attachments=tuple(
            Attachment(
                id=a["id"],
                kind=AttachmentKind(a["kind"]),
                name=cipher.decrypt(a["name_enc"]),
                added_by=a["added_by"],
                added_at=_aware(a["added_at"]),  # type: ignore[arg-type]
                detail=cipher.decrypt(a["detail_enc"]),
                repo=(
                    repo_from_json(cipher.decrypt_json(a["repo_enc"]))
                    if a["repo_enc"] is not None
                    else None
                ),
            )
            for a in attachments
        ),
    )


def plan_row(requirement_id: str, plan: Plan, cipher: Cipher) -> dict[str, Any]:
    return {
        "requirement_id": requirement_id,
        "suggested_at": plan.suggested_at,
        "overridden_by": plan.overridden_by,
        "items_enc": cipher.encrypt_json(
            [
                {
                    "agent_id": i.agent_id.value,
                    "suggested": i.suggested,
                    "enabled": i.enabled,
                    "reason": i.reason,
                    "source": i.source,
                }
                for i in plan.items
            ]
        ),
    }


def plan_from_row(row: Mapping[str, Any], cipher: Cipher) -> Plan:
    items = cipher.decrypt_json(row["items_enc"], []) or []
    return Plan(
        items=tuple(
            PlanItem(
                agent_id=AgentId(i["agent_id"]),
                suggested=bool(i["suggested"]),
                enabled=bool(i["enabled"]),
                reason=i.get("reason", ""),
                source=i.get("source", "regla"),
            )
            for i in items
        ),
        suggested_at=_aware(row["suggested_at"]),  # type: ignore[arg-type]
        overridden_by=row["overridden_by"] or "",
    )


def run_row(run: Run) -> dict[str, Any]:
    return {
        "id": run.id,
        "requirement_id": run.requirement_id,
        "started_by": run.started_by,
        "started_at": run.started_at,
        "status": run.status.value,
        "finished_at": run.finished_at,
        "cancelled_at": run.cancelled_at,
        "error": run.error,
        "enabled_agents": [a.value for a in run.enabled_agents],
        "profiles": {
            agent.value: {
                "provider": p.provider.value,
                "model": p.model,
                "prompt_version": p.prompt_version,
                "temperature": p.temperature,
                "max_steps": p.max_steps,
            }
            for agent, p in run.profiles.items()
        },
    }


def execution_rows(run: Run, cipher: Cipher) -> list[dict[str, Any]]:
    return [
        {
            "run_id": run.id,
            "agent_id": agent.value,
            "status": e.status.value,
            "reason": e.reason,
            "error": e.error,
            "started_at": e.started_at,
            "finished_at": e.finished_at,
            "tokens_in": e.usage.tokens_in,
            "tokens_out": e.usage.tokens_out,
            "cost_usd": e.usage.cost_usd,
            "output_enc": cipher.encrypt_json(e.output) if e.output is not None else None,
        }
        for agent, e in run.executions.items()
    ]


def call_rows(run: Run) -> list[dict[str, Any]]:
    return [
        {
            "run_id": run.id,
            "agent_id": call.agent_id.value,
            "provider": call.provider.value,
            "model": call.model,
            "prompt_version": call.prompt_version,
            "tokens_in": call.usage.tokens_in,
            "tokens_out": call.usage.tokens_out,
            "cost_usd": call.usage.cost_usd,
            "duration_ms": call.duration_ms,
            "attempts": call.attempts,
            "tools_used": list(call.tools_used),
            "tools_rejected": list(call.tools_rejected),
            "at": call.at,
            "error": call.error,
        }
        for execution in run.executions.values()
        for call in execution.calls
    ]


def run_from_rows(
    row: Mapping[str, Any],
    executions: list[Mapping[str, Any]],
    calls: list[Mapping[str, Any]],
    cipher: Cipher,
) -> Run:
    run = Run(
        id=row["id"],
        requirement_id=row["requirement_id"],
        started_by=row["started_by"],
        started_at=_aware(row["started_at"]),  # type: ignore[arg-type]
        enabled_agents=tuple(AgentId(a) for a in row["enabled_agents"]),
        profiles={
            AgentId(agent): ProfileSnapshot(
                provider=ProviderId(p["provider"]),
                model=p["model"],
                prompt_version=int(p["prompt_version"]),
                temperature=float(p.get("temperature", 0.0)),
                max_steps=int(p.get("max_steps", 4)),
            )
            for agent, p in (row["profiles"] or {}).items()
        },
        status=RunStatus(row["status"]),
        finished_at=_aware(row["finished_at"]),
        cancelled_at=_aware(row["cancelled_at"]),
        error=row["error"] or "",
    )

    by_agent: dict[AgentId, list[LLMCall]] = {}
    for call in calls:
        agent = AgentId(call["agent_id"])
        by_agent.setdefault(agent, []).append(
            LLMCall(
                agent_id=agent,
                provider=ProviderId(call["provider"]),
                model=call["model"],
                prompt_version=int(call["prompt_version"]),
                usage=Usage(
                    tokens_in=int(call["tokens_in"]),
                    tokens_out=int(call["tokens_out"]),
                    cost_usd=_money(call["cost_usd"]),
                ),
                duration_ms=int(call["duration_ms"]),
                attempts=int(call["attempts"]),
                tools_used=tuple(call["tools_used"] or ()),
                tools_rejected=tuple(call["tools_rejected"] or ()),
                at=_aware(call["at"]),
                error=call["error"] or "",
            )
        )

    for e in executions:
        agent = AgentId(e["agent_id"])
        execution = AgentExecution(
            agent_id=agent,
            status=AgentRunStatus(e["status"]),
            reason=e["reason"] or "",
            started_at=_aware(e["started_at"]),
            finished_at=_aware(e["finished_at"]),
            usage=Usage(
                tokens_in=int(e["tokens_in"]),
                tokens_out=int(e["tokens_out"]),
                cost_usd=_money(e["cost_usd"]),
            ),
            output=cipher.decrypt_json(e["output_enc"]) if e["output_enc"] is not None else None,
            calls=tuple(by_agent.get(agent, ())),
            error=e["error"] or "",
        )
        run.executions[agent] = execution
    return run


def event_row(event: TraceEvent, cipher: Cipher) -> dict[str, Any]:
    return {
        "run_id": event.run_id,
        "seq": event.seq,
        "at": event.at,
        "type": event.type.value,
        "agent": event.agent.value if event.agent else None,
        "to_agent": event.to.value if event.to else None,
        "tokens_in": event.usage.tokens_in if event.usage else None,
        "tokens_out": event.usage.tokens_out if event.usage else None,
        "cost_usd": event.usage.cost_usd if event.usage else None,
        "payload_enc": cipher.encrypt_json(
            {"title": event.title, "detail": event.detail, "data": event.data}
        ),
    }


def event_from_row(row: Mapping[str, Any], cipher: Cipher) -> TraceEvent:
    payload = cipher.decrypt_json(row["payload_enc"], {}) or {}
    usage = None
    if row["tokens_in"] is not None or row["cost_usd"] is not None:
        usage = Usage(
            tokens_in=int(row["tokens_in"] or 0),
            tokens_out=int(row["tokens_out"] or 0),
            cost_usd=_money(row["cost_usd"]),
        )
    return TraceEvent(
        seq=int(row["seq"]),
        run_id=row["run_id"],
        at=_aware(row["at"]),  # type: ignore[arg-type]
        type=TraceEventType(row["type"]),
        agent=AgentId(row["agent"]) if row["agent"] else None,
        to=AgentId(row["to_agent"]) if row["to_agent"] else None,
        title=payload.get("title", ""),
        detail=payload.get("detail", ""),
        data=payload.get("data", {}) or {},
        usage=usage,
    )


def profile_row(scope: str, profile: AgentProfile, now: datetime) -> dict[str, Any]:
    return {
        "scope": scope,
        "agent_id": profile.agent_id.value,
        "provider": profile.provider.value,
        "model": profile.model,
        "temperature": profile.temperature,
        "max_steps": profile.max_steps,
        "prompt_version": profile.prompt_version,
        "system_prompt": profile.system_prompt,
        "task_prompt": profile.task_prompt,
        "versions": [
            {
                "version": v.version,
                "saved_at": v.saved_at.isoformat(),
                "author": v.author,
                "note": v.note,
                "system_prompt": v.system_prompt,
                "task_prompt": v.task_prompt,
            }
            for v in profile.versions
        ],
        "updated_at": now,
    }


def profile_from_row(row: Mapping[str, Any]) -> AgentProfile:
    return AgentProfile(
        agent_id=AgentId(row["agent_id"]),
        provider=ProviderId(row["provider"]),
        model=row["model"],
        system_prompt=row["system_prompt"],
        task_prompt=row["task_prompt"],
        temperature=float(row["temperature"]),
        max_steps=int(row["max_steps"]),
        prompt_version=int(row["prompt_version"]),
        versions=tuple(
            PromptVersion(
                version=int(v["version"]),
                saved_at=datetime.fromisoformat(v["saved_at"]),
                author=v["author"],
                note=v["note"],
                system_prompt=v["system_prompt"],
                task_prompt=v["task_prompt"],
            )
            for v in (row["versions"] or ())
        ),
    )


def audit_row(entry: AuditEntry) -> dict[str, Any]:
    return {
        "at": entry.at,
        "actor": entry.actor,
        "action": entry.action.value,
        "target": entry.target,
        "detail": entry.detail,
        "prev_hash": entry.prev_hash,
        "hash": entry.hash,
    }


def audit_from_row(row: Mapping[str, Any]) -> AuditEntry:
    return AuditEntry(
        at=_aware(row["at"]),  # type: ignore[arg-type]
        actor=row["actor"],
        action=AuditAction(row["action"]),
        target=row["target"],
        detail=row["detail"] or "",
        prev_hash=row["prev_hash"],
        seq=int(row["seq"]),
    )
