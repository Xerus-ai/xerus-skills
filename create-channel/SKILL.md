---
name: create-channel
description: |
  Interactive channel creation workflow. Adds a new channel to an existing project
  with mission, goals, and agent assignments.
  Use when: user says "add a channel", "create a new channel", "new workstream",
  or invokes /create-channel directly.
user-invocable: true
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
---

# Create Channel Workflow

Interactive workflow to add a channel to an existing project.

## Step 0: Create Task

```
TaskCreate({
  title: "Create new channel: [pending name]",
  description: "Interactive channel creation workflow",
  status: "in_progress"
})
```

## Step 1: Gather Context (Silent)

```
Read agents/index.json
Glob('projects/*/CLAUDE.md')
```

```bash
sqlite3 data/company.db "SELECT d.slug, d.name, COUNT(c.slug) as channels FROM domains d LEFT JOIN channels c ON d.slug = c.domain_slug GROUP BY d.slug ORDER BY d.slug;"
```

## Step 2: Interactive Q&A

### Q1: Select Project
> "Which project should this channel belong to?
>
> **Existing projects:**
> {list projects with channel counts}
>
> Or say 'new project' to create one first (I'll run /create-project)."

If user says 'new project', invoke `/create-project` first, then resume.

### Q2: Channel Name & Mission
> "What's this channel for?
>
> **Name**: A short label like 'content', 'seo', 'outreach', 'analytics'
> **Mission**: What work happens here? (one sentence)"

### Q3: Goals
> "What should this channel achieve? List 1-3 measurable goals.
>
> Examples:
> - Publish 8 blog posts per month
> - Maintain 98% response rate within 24h
> - Generate 3 qualified leads per week
>
> Or say 'skip' to add goals later."

### Q4: Team Assignment
> "Who should work in #{channel_name}?
>
> **Available agents:**
> {list agents NOT already in this project, plus unassigned agents}
>
> Pick agents to assign. First one becomes channel lead.
> Or say 'none' — you can assign agents later with /assign-agent."

### Q5: Confirmation
> "Here's the plan:
>
> **#{channel_name}** in {project_name}
> Mission: {mission}
> Goals: {goals}
> Team: {agents or 'no agents yet'}
>
> Ready to create?"

## Step 3: Execute Creation

### 3a: Create Channel Directory

```bash
mkdir -p projects/{domain}/channels/{channel}/output/deliverables
mkdir -p projects/{domain}/channels/{channel}/scratch
touch projects/{domain}/channels/{channel}/output/posts.jsonl
```

### 3b: Register in DB

```bash
sqlite3 data/company.db "INSERT INTO channels (slug, name, domain_slug, lead_agent_slug, description, goals) VALUES ('{domain}--{channel}', '{name}', '{domain}', '{lead_slug or null}', '{mission}', '{goals_json}');"
```

### 3c: Write Channel CLAUDE.md

Write to `projects/{domain}/channels/{channel}/CLAUDE.md`:

```markdown
# Channel: {name}

## Mission
{mission}

## Goals
{goals as bullet points with metrics}

## Team
{agent list with roles}

## Rules
- Follow the data-steward protocol for all research output
- Post updates to output/posts.jsonl
- Final deliverables go to output/deliverables/
```

### 3d: Assign Agents

For each selected agent:

```bash
sqlite3 data/company.db "INSERT OR IGNORE INTO channel_members (channel_slug, agent_slug, role) VALUES ('{domain}--{channel}', '{slug}', '{role}');"
```

Update each agent's config.json channels array.

### 3e: Add System Agents

```bash
sqlite3 data/company.db "INSERT OR IGNORE INTO channel_members (channel_slug, agent_slug, role) VALUES ('{domain}--{channel}', 'xerus-master', 'member');"
sqlite3 data/company.db "INSERT OR IGNORE INTO channel_members (channel_slug, agent_slug, role) VALUES ('{domain}--{channel}', 'xerus-cto', 'member');"
```

### 3f: Update Project CLAUDE.md

Read `projects/{domain}/CLAUDE.md`, add the new channel to the Channels section.

## Step 4: Verify & Report

```bash
sqlite3 data/company.db "SELECT slug, name, lead_agent_slug FROM channels WHERE slug = '{domain}--{channel}';"
sqlite3 data/company.db "SELECT agent_slug, role FROM channel_members WHERE channel_slug = '{domain}--{channel}';"
```

```
Read projects/{domain}/channels/{channel}/CLAUDE.md
```

### Report

> "Channel **#{channel_name}** created in {project_name}!
>
> Team: {agent list with roles}
> Location: Inbox > {project} > #{channel}
>
> Agents will pick up work when you post messages in the channel."

```
TaskUpdate({ id: task_id, status: "completed" })
```

## Success Criteria

- [ ] Channel directory exists with `output/`, `scratch/`, `output/posts.jsonl`
- [ ] Channel CLAUDE.md exists with mission, goals, team
- [ ] Channel registered in `data/company.db` channels table
- [ ] If agents assigned: `channel_members` rows exist, first agent has `role = 'lead'`
- [ ] System agents added to channel
- [ ] Agent config.json files updated with new channel
- [ ] Project CLAUDE.md updated with new channel reference
- [ ] No duplicate channel slugs
- [ ] Task marked complete
