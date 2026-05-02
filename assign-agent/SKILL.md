---
name: assign-agent
description: |
  Interactive agent-to-channel assignment workflow. Picks an agent and channel,
  assigns with role, and updates all references.
  Use when: user says "add agent to channel", "assign agent", "move agent",
  or invokes /assign-agent directly.
user-invocable: true
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
---

# Assign Agent Workflow

Interactive workflow to assign an agent to a channel.

## Step 0: Create Task

```
TaskCreate({
  title: "Assign agent to channel",
  description: "Interactive agent assignment workflow",
  status: "in_progress"
})
```

## Step 1: Gather Context (Silent)

```
Read agents/index.json
```

```bash
sqlite3 data/company.db "SELECT d.slug as project, c.slug as channel_slug, c.name as channel_name, c.lead_agent_slug FROM domains d JOIN channels c ON d.slug = c.domain_slug ORDER BY d.slug, c.slug;"
sqlite3 data/company.db "SELECT cm.channel_slug, cm.agent_slug, cm.role FROM channel_members cm ORDER BY cm.channel_slug;"
```

Build a mental map of: which agents are where, which channels need agents.

## Step 2: Interactive Q&A

### Q1: Select Agent
> "Which agent do you want to assign?
>
> **Your agents:**
> {for each agent in index.json:}
> - **{name}** ({role}) — currently in: {channels or 'no channels'}
>
> Pick an agent by name or slug."

### Q2: Select Channel
> "Which channel should {agent_name} join?
>
> **Available channels:**
> {for each channel:}
> - **#{channel}** ({project}) — {N members}, lead: {lead or 'none'}
>
> Pick a channel."

### Q3: Role
> "What role should {agent_name} have in #{channel}?
>
> 1. **Lead** — Runs standups, coordinates team, manages tasks. Only one lead per channel.
> 2. **Member** (default) — Regular team member, executes work.
> 3. **Observer** — Read-only access, monitors but doesn't participate.
>
> If the channel has no lead, I'll recommend making {agent_name} the lead."

If channel has no lead, default to 'lead' and mention it.

### Q4: Confirmation
> "Assign **{agent_name}** to **#{channel}** as **{role}**?
>
> {If lead: 'This will make them the channel lead, responsible for standups and coordination.'}
> {If channel had a different lead and role=lead: 'This will replace {old_lead} as channel lead.'}"

## Step 3: Execute Assignment

### 3a: Insert Channel Member

```bash
sqlite3 data/company.db "INSERT OR IGNORE INTO channel_members (channel_slug, agent_slug, role) VALUES ('{channel_slug}', '{agent_slug}', '{role}');"
```

### 3b: Update Lead if Needed

If role is 'lead':
```bash
sqlite3 data/company.db "UPDATE channels SET lead_agent_slug = '{agent_slug}' WHERE slug = '{channel_slug}';"
sqlite3 data/company.db "UPDATE channel_members SET role = 'member' WHERE channel_slug = '{channel_slug}' AND agent_slug != '{agent_slug}' AND role = 'lead';"
```

### 3c: Update Agent Config

Read `agents/{slug}/config.json`, add the channel to the `channels` array, update `domain` and `primary_channel` if this is their first channel.

### 3d: Update Channel CLAUDE.md

Read `projects/{domain}/channels/{channel}/CLAUDE.md`, add the agent to the Team section.

## Step 4: Verify & Report

```bash
sqlite3 data/company.db "SELECT agent_slug, role FROM channel_members WHERE channel_slug = '{channel_slug}' ORDER BY role, agent_slug;"
```

```
Read agents/{slug}/config.json    # channels array updated?
```

### Report

> "Done! **{agent_name}** is now a **{role}** in **#{channel}**.
>
> {If lead: 'They'll run standups and coordinate the team.'}
> {If first channel: 'This is their first channel — they'll start receiving channel tasks.'}
>
> The agent will pick up channel context on their next session."

```
TaskUpdate({ id: task_id, status: "completed" })
```

## Success Criteria

- [ ] `channel_members` row exists with correct channel, agent, and role
- [ ] If lead: `channels.lead_agent_slug` updated, previous lead demoted to member
- [ ] Agent's `config.json` channels array includes the new channel
- [ ] Channel CLAUDE.md team section updated
- [ ] No duplicate `channel_members` entries
- [ ] Task marked complete
