---
name: create-agent
description: |
  Interactive agent creation workflow. Guides the user through naming, personality,
  role, autonomy, channel assignment, and schedule setup via conversational Q&A.
  Creates config.json (triggers hook scaffold), generates soul files via agent-creation skill,
  and assigns the agent to a channel.
  Use when: user says "create an agent", "hire someone", "I need an agent for X",
  or invokes /create-agent directly.
user-invocable: true
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, Agent
---

# Create Agent Workflow

Interactive workflow to create a fully configured agent in the Xerus workspace.

## Step 0: Create Task

Before anything else, create a tracking task:

```
TaskCreate({
  title: "Create new agent: [pending name]",
  description: "Interactive agent creation workflow",
  status: "in_progress"
})
```

Update the task title once the agent name is decided.

## Step 1: Gather Context (Silent)

Read workspace state before asking questions — you need this to offer smart defaults:

```
Read agents/index.json                          # existing agents (avoid name collisions)
Glob('projects/*/channels/*/CLAUDE.md')         # available channels
Glob('marketplace/agents/*/config.json')        # marketplace templates to suggest
Glob('.claude/skills/*/SKILL.md')               # available skills
```

## Step 2: Interactive Q&A

Use `AskUserQuestion` for each question. Offer concrete options, not open-ended prompts. Adapt based on previous answers.

### Q1: Role & Purpose
> "What do you need this agent to do? Pick a category or describe it:
>
> 1. **Research** — market research, competitor analysis, trend tracking
> 2. **Content** — writing, editing, social media, copywriting
> 3. **Data** — analytics, reporting, dashboards, data entry
> 4. **Sales** — outreach, lead gen, CRM management
> 5. **Support** — customer service, documentation, FAQ
> 6. **Engineering** — code review, testing, DevOps, architecture
> 7. **Custom** — describe what you need
>
> You can also say something like 'I need someone to write blog posts about AI'"

### Q2: Name & Personality
Based on the role, suggest 2-3 names with personality previews:

> "Here are some personality options for your {role} agent:
>
> 1. **{Name A}** — Analytical and methodical. Thinks before acting, provides data-backed recommendations.
> 2. **{Name B}** — Creative and expressive. Brings fresh perspectives, experiments with formats.
> 3. **{Name C}** — Action-oriented and efficient. Gets things done fast, minimal deliberation.
> 4. **Custom** — pick your own name and describe the personality
>
> Which style fits what you need?"

### Q3: Autonomy Level
> "How much freedom should {name} have?
>
> 1. **Supervised** — Asks before taking any significant action. Good for new agents you want to train.
> 2. **Semi-autonomous** (recommended) — Acts freely on routine work, asks before destructive or external actions.
> 3. **Autonomous** — Works independently, notifies you after. Best for trusted, routine workflows.
>
> You can always change this later."

### Q4: Proactive vs Reactive
> "Should {name} work on their own schedule, or only when you ask?
>
> 1. **Reactive only** — Waits for your instructions. No scheduled work.
> 2. **Daily check-in** — Runs once a day to check tasks and inbox.
> 3. **Active worker** — Runs multiple times a day on scheduled tasks.
> 4. **Custom schedule** — you tell me the cadence.
>
> Proactive agents use credits on their scheduled runs."

### Q5: Channel Assignment
Show existing channels and offer to create a new one:

> "Which channel should {name} join? They'll work in this channel's context.
>
> **Existing channels:**
> {list channels from workspace DB}
>
> Or I can create a new channel for them. What project/channel?"

### Q6: Skills & Tools
Based on the role, suggest relevant skills:

> "Here are skills that match {name}'s role:
>
> {list matching skills from marketplace}
>
> Want me to install any of these? You can also add tools (Google Drive, Slack, etc.) later from Settings > Connectors."

### Q7: Confirmation
Show a summary card before creating:

> "Here's the plan:
>
> | Field | Value |
> |-------|-------|
> | Name | {name} |
> | Role | {role} |
> | Personality | {personality_type} |
> | Model | {model} |
> | Autonomy | {autonomy_level} |
> | Schedule | {schedule or 'none'} |
> | Channel | {channel} |
> | Skills | {skills list} |
>
> Ready to create? (yes / let me change something)"

## Step 3: Execute Creation

### 3a: Write config.json

The PostToolUse hook will automatically scaffold supporting files (inbox/, knowledge/, memory dirs, index.json update, DB registration).

```json
{
  "slug": "{slug}",
  "name": "{name}",
  "description": "{description}",
  "role": "{role}",
  "model": "{model}",
  "autonomy_level": "{autonomy_level}",
  "adapter_type": "claudecode",
  "domain": "{domain}",
  "primary_channel": "{channel}",
  "channels": ["{domain}/{channel}"],
  "tools": [],
  "skills": ["{skills}"],
  "heartbeat_cron": "{cron or empty}"
}
```

Write to: `agents/{slug}/config.json`

### 3b: Generate Soul Files

Invoke the `agent-creation` skill to generate personalized soul files:

```
Skill({ skill: "agent-creation" })
```

This creates: SOUL.md, system-prompt.md, HEARTBEAT.md, STATUS.md, BOOTSTRAP.md, RELATIONSHIPS.md

### 3c: Write agent.md (System Prompt)

Generate a focused system prompt based on the role, personality, and goals gathered in Q&A. Write to `agents/{slug}/agent.md`.

### 3d: Channel Assignment

If a channel was selected, add the agent as a member:

```bash
sqlite3 data/company.db "INSERT OR IGNORE INTO channel_members (channel_slug, agent_slug, role) VALUES ('{channel_slug}', '{slug}', 'member');"
```

Also update the agent's config.json channels array if not already set.

### 3e: Install Skills

For each selected skill, copy from marketplace:

```bash
cp -r marketplace/skills/{skill-slug} .claude/skills/{skill-slug}
```

### 3f: Create Schedule (if proactive)

If user chose a schedule, use the MCP tool:

```
platform.create_schedule({
  agent_slug: "{slug}",
  name: "{name} daily check-in",
  prompt: "Check your inbox and task board. Execute any pending tasks. Update your STATUS.md.",
  rrule: "FREQ=DAILY;BYHOUR=9;BYMINUTE=0"
})
```

## Step 4: Verify & Report

### Verification Checklist

Run these checks and report results:

```
Glob('agents/{slug}/*')                        # All files created?
Read agents/{slug}/config.json                  # Valid JSON?
Read agents/{slug}/SOUL.md                      # Soul file exists and has content?
Read agents/index.json                          # Agent registered in index?
```

```bash
sqlite3 data/company.db "SELECT slug, name, status FROM agents WHERE slug = '{slug}';"
sqlite3 data/company.db "SELECT * FROM channel_members WHERE agent_slug = '{slug}';"
```

### Report to User

> "{name} is ready!
>
> - Identity: agents/{slug}/SOUL.md
> - Config: agents/{slug}/config.json
> - Channel: #{channel}
> - Schedule: {schedule description or 'none — reactive only'}
>
> {name} will run their bootstrap on first session — they'll introduce themselves and ask you a few calibration questions.
>
> Chat with them now? → /chat?agent={slug}"

### Update Task

```
TaskUpdate({ id: task_id, status: "completed" })
```

## Success Criteria

- [ ] `agents/{slug}/config.json` exists and is valid JSON
- [ ] `agents/{slug}/SOUL.md` exists with unique personality content (not template placeholders)
- [ ] `agents/{slug}/agent.md` exists with role-specific system prompt
- [ ] `agents/{slug}/STATUS.md` exists with initial state
- [ ] `agents/{slug}/BOOTSTRAP.md` exists with `completed_at: null`
- [ ] `agents/{slug}/RELATIONSHIPS.md` exists with peer map from index.json
- [ ] `agents/index.json` contains the new agent entry
- [ ] Agent registered in `data/company.db` agents table
- [ ] If channel assigned: `channel_members` row exists
- [ ] If schedule set: schedule created via MCP tool
- [ ] If skills selected: skills copied to `.claude/skills/`
- [ ] No placeholder brackets `{...}` remain in any generated file
- [ ] Task marked complete in TaskCreate tracker
