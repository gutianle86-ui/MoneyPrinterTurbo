"""Production estimates from existing records; never a provider billing ledger."""


def retained_cost(candidate):
    if candidate.get("provider") != "seedance":
        return 0
    # Definitive rejection before submission releases the budget reservation.
    if candidate.get("status") == "failed" and not candidate.get("task_id"):
        return 0
    return candidate.get("estimated_cost", 0)


def summary(project):
    from backend.services import candidate_matches

    seen, paid, rows = set(), [], []
    all_shots = list(project["shots"])
    for version in project.get("archived_versions", []):
        all_shots.extend(version.get("shots", []))
    multiple = 0
    for shot in all_shots:
        candidates = []
        for candidate in shot.get("candidates", []):
            if candidate["id"] in seen:
                continue
            seen.add(candidate["id"])
            if candidate.get("provider") == "seedance":
                candidates.append(candidate)
        paid.extend(candidates)
        multiple += sum(retained_cost(c) > 0 for c in candidates) > 1
    for shot in project["shots"]:
        selected = next(
            (
                c
                for c in shot["candidates"]
                if c["id"] == shot.get("selected")
                and c["status"] == "ready"
                and candidate_matches(project, shot, c)
            ),
            None,
        )
        rows.append(
            {
                "shot_id": shot["id"],
                "title": shot["title"],
                "attempts": sum(
                    c.get("provider") == "seedance" for c in shot["candidates"]
                ),
                "estimated_cost": round(
                    sum(retained_cost(c) for c in shot["candidates"]), 4
                ),
                "selected_cost": round(retained_cost(selected or {}), 4),
            }
        )
    selected_cost = round(sum(r["selected_cost"] for r in rows), 4)
    return {
        "estimated_video_cost": project.get("reserved_cost", 0),
        "selected_cost": selected_cost,
        "unselected_cost": round(
            max(0, project.get("reserved_cost", 0) - selected_cost), 4
        ),
        "paid_attempts": len(paid),
        "multiple_candidate_shots": multiple,
        "unsettled_tasks": sum(
            c.get("status") in {"generating", "uncertain", "interrupted", "checked"}
            or (c.get("status") == "failed" and bool(c.get("task_id")))
            for c in paid
        ),
        "shots": rows,
    }
