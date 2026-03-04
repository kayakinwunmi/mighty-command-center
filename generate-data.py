#!/usr/bin/env python3
"""
Mighty Command Center — Data Generator
Reads Kay's workspace files and generates public/data.json
"""

import json
import os
import re
from datetime import datetime, date
from pathlib import Path

WORKSPACE = os.environ.get("WORKSPACE_DIR", "/Users/ayoakwm/.openclaw/workspace")
OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public", "data.json")
TODAY = date.today()
Q1_END = date(2026, 3, 31)


def days_between(d1, d2):
    return abs((d1 - d2).days)


def parse_date(s):
    """Try to parse a date string."""
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            continue
    return None


def read_file(name):
    path = os.path.join(WORKSPACE, name)
    if os.path.exists(path):
        with open(path, "r") as f:
            return f.read()
    return ""


def parse_contacts():
    contacts_dir = os.path.join(WORKSPACE, "contacts")
    contacts = []
    if not os.path.isdir(contacts_dir):
        return contacts

    for fname in os.listdir(contacts_dir):
        if not fname.endswith(".md"):
            continue
        filepath = os.path.join(contacts_dir, fname)
        with open(filepath, "r") as f:
            content = f.read()

        name_match = re.search(r"^#\s+(.+?)(?:\s*[-—]|$)", content, re.MULTILINE)
        name = name_match.group(1).strip() if name_match else fname.replace(".md", "").replace("-", " ").title()
        # Clean name
        name = re.sub(r"\s*[-—].*$", "", name).strip()

        tier_match = re.search(r"\*\*Tier[:\*]*\s*\**\s*(\d)", content, re.IGNORECASE)
        if not tier_match:
            tier_match = re.search(r"\|\s*\*\*Tier\*\*\s*\|\s*(\d)", content, re.IGNORECASE)
        tier = int(tier_match.group(1)) if tier_match else 3

        # Find last contact date
        last_contact = None
        # Check "Last Contact:" field
        lc_match = re.search(r"\*\*Last Contact:\*\*\s*([\d-]+)", content)
        if lc_match:
            last_contact = parse_date(lc_match.group(1))
        # Check "Date:" under Last Interaction
        if not last_contact:
            li_match = re.search(r"\*\*Date:\*\*\s*([\d-]+)", content)
            if li_match:
                last_contact = parse_date(li_match.group(1))
        # Fallback: find the latest date in interaction log tables
        if not last_contact:
            dates = re.findall(r"\|\s*(20\d{2}-\d{2}-\d{2})\s*\|", content)
            if dates:
                parsed = [parse_date(d) for d in dates]
                parsed = [d for d in parsed if d]
                if parsed:
                    last_contact = max(parsed)

        # Get company/context
        company_match = re.search(r"\*\*(?:Company|Organisation|Org)\*\*\s*\|?\s*([^\n|]+)", content, re.IGNORECASE)
        if not company_match:
            company_match = re.search(r"\*\*Company:\*\*\s*(.+)", content)
        company = company_match.group(1).strip().strip("|").strip() if company_match else ""

        role_match = re.search(r"\*\*Role:\*\*\s*(.+)", content)
        if not role_match:
            role_match = re.search(r"\*\*Role\*\*\s*\|?\s*([^\n|]+)", content, re.IGNORECASE)
        role = role_match.group(1).strip().strip("|").strip() if role_match else ""

        days_since = days_between(TODAY, last_contact) if last_contact else None

        # Determine health
        thresholds = {1: 14, 2: 30, 3: 60}
        threshold = thresholds.get(tier, 60)
        if days_since is not None:
            health = "cooling" if days_since > threshold else "healthy"
        else:
            health = "unknown"

        contacts.append({
            "name": name,
            "tier": tier,
            "last_contact": last_contact.isoformat() if last_contact else None,
            "days_since": days_since,
            "health": health,
            "company": company,
            "role": role,
            "context": f"{company} — {role}" if company and role else company or role or "",
            "file": fname,
        })

    return sorted(contacts, key=lambda c: (c["tier"], -(c["days_since"] or 0)))


def parse_goals():
    content = read_file("GOALS.md")
    goals = []

    # Parse business goals
    sections = re.split(r"###\s+\d+\.\s+", content)
    for section in sections[1:]:
        lines = section.strip().split("\n")
        name_line = lines[0]
        name = re.sub(r"\s*[⭐✅🟡🔴]+.*$", "", name_line).strip()

        priority_match = re.search(r"P(\d)", name_line)
        priority = f"P{priority_match.group(1)}" if priority_match else "P3"

        progress_match = re.search(r"\*\*Progress:\*\*\s*(\d+)%", section)
        progress = int(progress_match.group(1)) if progress_match else 0

        status_text = ""
        status_match = re.search(r"(On Track|AT RISK|COMPLETE|NEEDS DATA|STALLED)", section, re.IGNORECASE)
        if status_match:
            s = status_match.group(1).lower()
            if "complete" in s:
                status_text = "complete"
            elif "risk" in s:
                status_text = "at_risk"
            elif "stall" in s:
                status_text = "stalled"
            elif "track" in s:
                status_text = "on_track"
            else:
                status_text = "unknown"
        else:
            status_text = "on_track"

        # Parse key results
        key_results = []
        kr_matches = re.findall(r"\[(x| )\]\s+(.+?)(?:\s*[—✅🟡🔴].*)?$", section, re.MULTILINE)
        for done_mark, kr_name in kr_matches:
            key_results.append({
                "name": kr_name.strip(),
                "done": done_mark.lower() == "x"
            })

        risk = "low" if status_text == "complete" else ("high" if status_text in ("at_risk", "stalled") else "medium")

        if "COMPLETE" in name_line:
            status_text = "complete"
            risk = "low"

        goals.append({
            "name": name,
            "progress": progress,
            "status": status_text,
            "priority": priority,
            "key_results": key_results,
            "risk_level": risk,
        })

    # Parse personal goals table
    personal_rows = re.findall(
        r"\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*(AT RISK|ON TRACK|NEEDS DATA|UNTRACKED|Long horizon[^|]*)\s*\|",
        content, re.IGNORECASE
    )
    for row in personal_rows:
        name = row[0].strip()
        if name.startswith("---") or name == "Goal":
            continue
        status_raw = row[4].strip().lower()
        if "risk" in status_raw:
            status = "at_risk"
            risk = "high"
        elif "track" in status_raw:
            status = "on_track"
            risk = "medium"
        elif "untracked" in status_raw:
            status = "untracked"
            risk = "medium"
        else:
            status = "unknown"
            risk = "medium"

        goals.append({
            "name": name,
            "progress": 0,
            "status": status,
            "priority": "P3",
            "key_results": [],
            "risk_level": risk,
            "is_personal": True,
        })

    return goals


def parse_pipeline():
    content = read_file("PIPELINE.md")
    pipeline = {
        "live": [],
        "onboarding": [],
        "negotiation": [],
        "engaged": [],
        "stalled": [],
        "lead": [],
    }

    # Live clients
    live_rows = re.findall(
        r"\|\s*([A-Z][^|]+?)\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|",
        content[content.find("### Live"):content.find("### Onboarding")] if "### Live" in content else ""
    )
    for row in live_rows:
        if row[0].strip().startswith("Company") or row[0].strip().startswith("---"):
            continue
        pipeline["live"].append({
            "company": row[0].strip(),
            "contact": row[1].strip() or "—",
            "volume": row[2].strip(),
            "health": row[4].strip(),
        })

    # Onboarding
    onboard_section = content[content.find("### Onboarding"):content.find("### Negotiation")] if "### Onboarding" in content else ""
    onboard_rows = re.findall(
        r"\|\s*([A-Z][^|]+?)\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|",
        onboard_section
    )
    for row in onboard_rows:
        if row[0].strip().startswith("Company") or row[0].strip().startswith("---"):
            continue
        days_match = re.search(r"~?(\d+)", row[4].strip())
        pipeline["onboarding"].append({
            "company": row[0].strip(),
            "contact": row[1].strip() or "—",
            "next_action": row[3].strip(),
            "days_in_stage": int(days_match.group(1)) if days_match else 0,
            "flag": row[5].strip(),
        })

    # Negotiation
    neg_section = content[content.find("### Negotiation"):content.find("### Engaged")] if "### Negotiation" in content else ""
    neg_rows = re.findall(
        r"\|\s*([A-Z][^|]+?)\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|",
        neg_section
    )
    for row in neg_rows:
        if row[0].strip().startswith("Company") or row[0].strip().startswith("---"):
            continue
        days_match = re.search(r"~?(\d+)", row[4].strip())
        is_stalled = "STALLED" in row[5].upper() or (days_match and int(days_match.group(1)) > 21)
        entry = {
            "company": row[0].strip(),
            "contact": row[1].strip() or "—",
            "stage": row[2].strip(),
            "next_action": row[3].strip(),
            "days_in_stage": int(days_match.group(1)) if days_match else 0,
            "flag": row[5].strip(),
        }
        if is_stalled:
            pipeline["stalled"].append(entry)
        else:
            pipeline["negotiation"].append(entry)

    # Engaged
    eng_section = content[content.find("### Engaged"):content.find("### Stalled")] if "### Engaged" in content else ""
    eng_rows = re.findall(
        r"\|\s*([A-Z][^|]+?)\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|",
        eng_section
    )
    for row in eng_rows:
        if row[0].strip().startswith("Company") or row[0].strip().startswith("---"):
            continue
        days_match = re.search(r"~?(\d+)", row[4].strip())
        is_stalled = "STALLED" in row[5].upper() or (days_match and int(days_match.group(1)) > 30)
        entry = {
            "company": row[0].strip(),
            "contact": row[1].strip() or "—",
            "stage": row[2].strip(),
            "next_action": row[3].strip(),
            "days_in_stage": int(days_match.group(1)) if days_match else 0,
            "flag": row[5].strip(),
        }
        if is_stalled:
            pipeline["stalled"].append(entry)
        else:
            pipeline["engaged"].append(entry)

    # Stalled / Needs Decision
    stalled_section = content[content.find("### Stalled"):content.find("## Pipeline Metrics")] if "### Stalled" in content else ""
    stalled_rows = re.findall(
        r"\|\s*([A-Z][^|]+?)\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|",
        stalled_section
    )
    for row in stalled_rows:
        if row[0].strip().startswith("Company") or row[0].strip().startswith("---"):
            continue
        pipeline["stalled"].append({
            "company": row[0].strip(),
            "contact": row[1].strip() or "—",
            "issue": row[2].strip(),
            "recommended_action": row[3].strip(),
            "days_in_stage": 50,  # approximate for stalled
            "flag": "STALLED",
        })

    return pipeline


def parse_tasks():
    content = read_file("MY-TASKS.md")
    tasks = {"overdue": [], "due_today": [], "upcoming": [], "completed_count": 0}

    # Count completed
    completed = re.findall(r"\| task-", content[content.find("## Completed"):] if "## Completed" in content else "")
    tasks["completed_count"] = len(completed)

    # Parse in-progress and pending tasks
    sections = re.split(r"^## ", content, flags=re.MULTILINE)
    for section in sections:
        if not any(s in section for s in ["In Progress", "Pending"]):
            continue

        task_blocks = re.split(r"### ", section)
        for block in task_blocks[1:]:
            lines = block.strip().split("\n")
            task_name_match = re.match(r"(task-\S+):\s*(.+)", lines[0])
            if not task_name_match:
                continue

            task_id = task_name_match.group(1)
            task_name = task_name_match.group(2).strip()

            due_match = re.search(r"\*\*Due:\*\*\s*([\d-]+)", block)
            due_date = parse_date(due_match.group(1)) if due_match else None

            priority_match = re.search(r"\*\*Priority:\*\*\s*(P\d)", block)
            priority = priority_match.group(1) if priority_match else "P3"

            assignee_match = re.search(r"\*\*Assignee:\*\*\s*(.+)", block)
            assignee = assignee_match.group(1).strip() if assignee_match else ""

            notes_match = re.search(r"\*\*Notes:\*\*\s*(.+)", block)
            notes = notes_match.group(1).strip() if notes_match else ""

            task_entry = {
                "id": task_id,
                "name": task_name,
                "due": due_date.isoformat() if due_date else None,
                "priority": priority,
                "assignee": assignee,
                "notes": notes,
            }

            if due_date:
                if due_date < TODAY:
                    tasks["overdue"].append(task_entry)
                elif due_date == TODAY:
                    tasks["due_today"].append(task_entry)
                else:
                    tasks["upcoming"].append(task_entry)
            else:
                tasks["upcoming"].append(task_entry)

    return tasks


def parse_follow_ups():
    content = read_file("FOLLOW-UPS.md")
    result = {"kays_commitments": [], "others_commitments": []}

    # Kay's commitments section
    kays_section = content[content.find("## Kay's Commitments"):content.find("## Commitments to Kay")] if "## Kay's Commitments" in content else ""
    rows = re.findall(
        r"\|\s*([A-Z\d]+-?\d*)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|",
        kays_section
    )
    for row in rows:
        if row[0].strip() == "ID" or row[0].strip().startswith("---"):
            continue
        result["kays_commitments"].append({
            "id": row[0].strip(),
            "commitment": row[1].strip(),
            "to_whom": row[2].strip(),
            "deadline": row[3].strip(),
            "status": row[4].strip(),
        })

    # Others' commitments
    others_section = content[content.find("## Commitments to Kay"):content.find("## Rules")] if "## Commitments to Kay" in content else ""
    rows = re.findall(
        r"\|\s*([A-Z\d]+-?\d*)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|",
        others_section
    )
    for row in rows:
        if row[0].strip() == "ID" or row[0].strip().startswith("---"):
            continue
        result["others_commitments"].append({
            "id": row[0].strip(),
            "commitment": row[1].strip(),
            "from_whom": row[2].strip(),
            "expected_by": row[3].strip(),
            "status": row[4].strip(),
        })

    return result


def parse_key_dates():
    content = read_file("KEY-DATES.md")
    dates = []

    # Parse all table rows with dates
    rows = re.findall(
        r"\|\s*([\d-]+(?:\s*to\s*[\d-]+)?|TBD|Every[^|]*|End[^|]*|ASAP|Ongoing)\s*\|\s*([^|]+?)\s*\|\s*([^|]*?)\s*\|",
        content
    )
    for row in rows:
        date_str = row[0].strip()
        event = row[1].strip()
        notes = row[2].strip()

        if date_str.startswith("Date") or date_str.startswith("---") or date_str == "Cadence":
            continue

        parsed = parse_date(date_str.split(" to ")[0] if " to " in date_str else date_str)

        # Determine type
        event_type = "business"
        if any(w in event.lower() for w in ["birthday", "trip", "lunch", "gym", "digital reset", "hurghada", "dinner"]):
            event_type = "personal"
        elif any(w in event.lower() for w in ["fca", "compliance", "mlro", "regulatory", "kyc"]):
            event_type = "compliance"
        elif any(w in event.lower() for w in ["deadline", "due", "review"]):
            event_type = "deadline"

        dates.append({
            "date": parsed.isoformat() if parsed else date_str,
            "date_raw": date_str,
            "event": event,
            "notes": notes,
            "type": event_type,
            "is_upcoming": parsed >= TODAY if parsed else True,
        })

    # Filter to upcoming and sort
    upcoming = [d for d in dates if d.get("is_upcoming", True)]
    return upcoming[:15]


def build_cost_of_inaction(pipeline, contacts, goals):
    """Build the urgency-driving cost of inaction items."""
    costs = []

    # Stalled deals
    for deal in pipeline.get("stalled", []):
        costs.append({
            "type": "stalled_deal",
            "name": deal["company"],
            "contact": deal.get("contact", "—"),
            "days_stalled": deal.get("days_in_stage", 30),
            "estimated_value": "$2-5M annual volume" if "iFast" in deal["company"] else "$500K-2M annual",
            "what_you_lose": deal.get("issue", deal.get("flag", "Deal going cold")),
        })

    # Cooling tier 1 relationships
    for c in contacts:
        if c["tier"] == 1 and c["health"] == "cooling" and c["days_since"]:
            costs.append({
                "type": "cooling_relationship",
                "name": c["name"],
                "contact": c["name"],
                "days_stalled": c["days_since"],
                "estimated_value": "Tier 1 relationship",
                "what_you_lose": f"No contact for {c['days_since']} days — {c['context']}",
            })

    # At-risk goals
    for g in goals:
        if g["risk_level"] == "high" and g.get("status") != "complete":
            costs.append({
                "type": "at_risk_goal",
                "name": g["name"],
                "contact": "—",
                "days_stalled": 0,
                "estimated_value": "Q1 Goal",
                "what_you_lose": f"Goal at risk — {g['progress']}% complete with Q1 ending",
            })

    return sorted(costs, key=lambda x: -x["days_stalled"])


def main():
    print("🔧 Generating Mighty Command Center data...")

    contacts = parse_contacts()
    goals = parse_goals()
    pipeline = parse_pipeline()
    tasks = parse_tasks()
    follow_ups = parse_follow_ups()
    key_dates = parse_key_dates()

    q1_days = (Q1_END - TODAY).days
    q1_total = (Q1_END - date(2026, 1, 1)).days
    q1_progress = round(((q1_total - q1_days) / q1_total) * 100)

    cooling = [c for c in contacts if c["health"] == "cooling"]
    healthy = [c for c in contacts if c["health"] == "healthy"]

    cost_of_inaction = build_cost_of_inaction(pipeline, contacts, goals)

    data = {
        "generated_at": datetime.now().isoformat(),
        "q1_countdown": {
            "days_remaining": max(q1_days, 0),
            "end_date": Q1_END.isoformat(),
            "weeks_remaining": round(q1_days / 7, 1),
            "progress_pct": q1_progress,
        },
        "cost_of_inaction": cost_of_inaction,
        "goals": goals,
        "pipeline": pipeline,
        "relationships": {
            "cooling": [{
                "name": c["name"],
                "days_since": c["days_since"],
                "tier": c["tier"],
                "context": c["context"],
                "company": c["company"],
            } for c in cooling],
            "healthy": [{
                "name": c["name"],
                "days_since": c["days_since"],
                "tier": c["tier"],
                "context": c["context"],
            } for c in healthy],
            "all": [{
                "name": c["name"],
                "days_since": c["days_since"],
                "tier": c["tier"],
                "health": c["health"],
                "context": c["context"],
            } for c in contacts],
            "total_contacts": len(contacts),
        },
        "tasks": tasks,
        "follow_ups": follow_ups,
        "key_dates": key_dates,
        "stats": {
            "total_pipeline_value": "~$10M+ annual",
            "deals_in_motion": len(pipeline["onboarding"]) + len(pipeline["negotiation"]) + len(pipeline["engaged"]),
            "live_clients": len(pipeline["live"]),
            "stalled_deals": len(pipeline["stalled"]),
            "overdue_tasks": len(tasks["overdue"]),
            "cooling_relationships": len(cooling),
            "healthy_relationships": len(healthy),
            "goals_complete": len([g for g in goals if g["status"] == "complete"]),
            "goals_at_risk": len([g for g in goals if g["risk_level"] == "high"]),
            "goals_total": len(goals),
            "completed_tasks": tasks["completed_count"],
        },
    }

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w") as f:
        json.dump(data, f, indent=2, default=str)

    print(f"✅ Generated {OUTPUT}")
    print(f"   Q1: {q1_days} days remaining ({q1_progress}% complete)")
    print(f"   Goals: {len(goals)} total, {data['stats']['goals_at_risk']} at risk")
    print(f"   Pipeline: {data['stats']['deals_in_motion']} active, {data['stats']['stalled_deals']} stalled")
    print(f"   Contacts: {len(contacts)} total, {len(cooling)} cooling")
    print(f"   Cost of inaction items: {len(cost_of_inaction)}")


if __name__ == "__main__":
    main()
