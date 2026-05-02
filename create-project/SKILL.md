---
name: create-project
description: |
  Interactive project creation workflow. Guides the user through naming, mission,
  OKRs, initial channels, and team assignment. Creates project directory structure,
  workspace DB records, and scaffolds CLAUDE.md files.
  Use when: user says "create a project", "set up a department", "new team",
  or invokes /create-project directly.
user-invocable: true
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
---

# Create Project Workflow

Interactive workflow to create a project (domain) with channels and team assignments.

## Step 0: Create Task

```
TaskCreate({
  title: "Create new project: [pending name]",
  description: "Interactive project creation workflow",
  status: "in_progress"
})
```

## Step 1: Gather Context (Silent)

```
Read agents/index.json                          # available agents to assign
Glob('projects/*/CLAUDE.md')                    # existing projects (avoid duplicates)
```

```bash
sqlite3 data/company.db "SELECT slug, name FROM domains ORDER BY slug;"
```

## Step 2: Interactive Q&A

### Q1: Project Name & Purpose
> "What's this project about?
>
> A project is a department or initiative — like 'Marketing', 'Product', 'Sales', or 'Q2 Launch'.
>
> **Name**: What should we call it?
> **Mission**: What's its purpose in one sentence?"

### Q2: Goals & OKRs
> "What are the key goals for {project_name}? These help agents stay aligned.
>
> Examples:
> - Publish 10 blog posts per month
> - Generate 50 qualified leads per week
> - Ship feature X by end of quarter
>
> List 2-4 goals (or say 'skip' to add later):"

### Q3: Initial Channels
> "Projects have channels — think of them as workstreams or teams.
>
> I'll always create a **#general** channel. Want any others?
>
> Examples for a Marketing project:
> - #content — blog posts, social media, copywriting
> - #seo — keyword research, optimization, analytics
> - #design — visual assets, brand guidelines
>
> List additional channels or say 'just general for now':"

### Q4: Team Assignment
For each channel, suggest agents:

> "Who should work in each channel?
>
> **#{channel_name}:**
> Available agents: {list from index.json}
>
> Pick agents for this channel, or say 'none for now'.
> The first agent assigned becomes the channel lead."

### Q5: Confirmation
> "Here's the plan:
>
> **Project: {name}**
> Mission: {mission}
>
> **Channels:**
> {for each channel: name, assigned agents}
>
> **Goals:**
> {goals list}
>
> Ready to create?"

## Step 3: Execute Creation

### 3a: Create Project Directory

```bash
mkdir -p projects/{slug}
mkdir -p projects/{slug}/knowledge
```

### 3b: Register Domain in DB

```bash
sqlite3 data/company.db "INSERT INTO domains (slug, name, description) VALUES ('{slug}', '{name}', '{mission}');"
```

### 3c: Write Project CLAUDE.md

Write to `projects/{slug}/CLAUDE.md`:

```markdown
# Project: {name}

## Mission
{mission}

## OKRs
{goals formatted as objectives with key results}

## Channels
{list of channels with descriptions}

## Team
{agents assigned across channels}
```

### 3d: Create Channels

For each channel (including #general):

1. Register in DB:
```bash
sqlite3 data/company.db "INSERT INTO channels (slug, name, domain_slug, description) VALUES ('{domain}--{channel}', '{Channel Name}', '{domain}', '{description}');"
```

2. Create directory structure:
```bash
mkdir -p projects/{domain}/channels/{channel}/output/deliverables
mkdir -p projects/{domain}/channels/{channel}/scratch
touch projects/{domain}/channels/{channel}/output/posts.jsonl
```

3. Write channel CLAUDE.md to `projects/{domain}/channels/{channel}/CLAUDE.md`

### 3e: Assign Agents to Channels

For each agent-channel assignment:

```bash
sqlite3 data/company.db "INSERT OR IGNORE INTO channel_members (channel_slug, agent_slug, role) VALUES ('{domain}--{channel}', '{agent_slug}', '{role}');"
```

First agent in each channel gets `role = 'lead'`, rest get `'member'`.

Also update each agent's config.json channels array.

### 3f: Add System Agents

Xerus Master and CTO are auto-added to every channel:

```bash
sqlite3 data/company.db "INSERT OR IGNORE INTO channel_members (channel_slug, agent_slug, role) VALUES ('{channel_slug}', 'xerus-master', 'member');"
sqlite3 data/company.db "INSERT OR IGNORE INTO channel_members (channel_slug, agent_slug, role) VALUES ('{channel_slug}', 'xerus-cto', 'member');"
```

## Step 4: Verify & Report

### Verification Checklist

```bash
sqlite3 data/company.db "SELECT slug, name FROM domains WHERE slug = '{slug}';"
sqlite3 data/company.db "SELECT slug, name, lead_agent_slug FROM channels WHERE domain_slug = '{slug}';"
sqlite3 data/company.db "SELECT channel_slug, agent_slug, role FROM channel_members WHERE channel_slug LIKE '{slug}--%';"
```

```
Read projects/{slug}/CLAUDE.md
Glob('projects/{slug}/channels/*/CLAUDE.md')
```

### Report to User

> "Project **{name}** is live!
>
> **Channels created:**
> {for each: #channel — N agents assigned}
>
> **Next steps:**
> - Chat in a channel: go to Inbox > {project} > #{channel}
> - Add more agents: /assign-agent
> - Create more channels: /create-channel"

### Update Task

```
TaskUpdate({ id: task_id, status: "completed" })
```

## Success Criteria

- [ ] `projects/{slug}/CLAUDE.md` exists with mission and OKRs
- [ ] Domain registered in `data/company.db` domains table
- [ ] #general channel exists in DB and filesystem
- [ ] All requested channels created in DB and filesystem
- [ ] Each channel has a CLAUDE.md with mission and team section
- [ ] Each channel has `output/posts.jsonl` initialized
- [ ] Agent assignments registered in `channel_members` table
- [ ] First agent per channel has `role = 'lead'`
- [ ] System agents (xerus-master, xerus-cto) added to all channels
- [ ] Agent config.json files updated with channel assignments
- [ ] No duplicate domain or channel slugs
- [ ] Task marked complete in TaskCreate tracker
