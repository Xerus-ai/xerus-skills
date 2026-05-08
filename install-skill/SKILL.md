---
name: install-skill
description: |
  Interactive skill installation workflow. Browse marketplace, preview skill details,
  choose global or agent-specific install, and verify activation.
  Use when: user says "install a skill", "add a skill", "I need a skill for X",
  or invokes /install-skill directly.
user-invocable: true
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
---

# Install Skill Workflow

Interactive workflow to discover and install skills from the marketplace.

## Step 0: Create Task

```
TaskCreate({
  title: "Install skill: [pending]",
  description: "Interactive skill installation workflow",
  status: "in_progress"
})
```

## Step 1: Gather Context (Silent)

```
Glob('marketplace/skills/*/SKILL.md')           # available skills
Glob('marketplace/skills/*/xerushub.json')       # skill metadata
Glob('.claude/skills/*/SKILL.md')                # already installed skills
Read agents/index.json                           # agents to assign to
```

Build a list of: available (not yet installed), installed, and agent assignments.

## Step 2: Interactive Q&A

### Q1: What Do You Need?
> "What capability are you looking for? I'll search the marketplace.
>
> You can describe what you need or browse by category:
>
> 1. **Content** — writing, social media, SEO, copywriting
> 2. **Research** — web scraping, trend tracking, competitive analysis
> 3. **Data** — analytics, Google Sheets, PDF/DOCX generation
> 4. **Communication** — Discord, email, notifications
> 5. **Development** — code review, testing, DevOps
> 6. **Browse all** — see every available skill
>
> Or just describe what you need: 'I need something to track Twitter mentions'"

### Q2: Skill Selection

Search marketplace based on user's response, then present matches:

> "Here's what I found:
>
> {for each matching skill:}
> **{displayName}** (`{slug}`)
> {summary from xerushub.json}
> Tags: {tags}
> {if already installed: '(already installed)'}
>
> Which one do you want to install? Or say 'tell me more about {slug}' for details."

If user wants details, read and present the SKILL.md content.

### Q3: Install Scope
> "How should I install **{skill_name}**?
>
> 1. **Global** (recommended) — Available to all agents in the workspace.
> 2. **Agent-specific** — Only available to specific agents you choose.
>
> Global skills are auto-discovered by the SDK. Agent-specific skills are referenced in the agent's config."

If agent-specific:
> "Which agents should have this skill?
>
> {list agents from index.json}"

### Q4: Confirmation
> "Install **{skill_name}** {globally / for agents: {list}}?
>
> This will copy the skill files from marketplace to your workspace."

## Step 3: Execute Installation

### 3a: Copy Skill Files

For global install:
```bash
cp -r marketplace/skills/{slug} .claude/skills/{slug}
```

For agent-specific: still install globally (SDK discovers from `.claude/skills/`), but also register the assignment.

### 3b: Register in DB

```bash
sqlite3 data/workspace.db "INSERT OR IGNORE INTO skills (slug, name, version, source, source_ref, description) VALUES ('{slug}', '{displayName}', '{version}', 'marketplace', 'marketplace/skills/{slug}', '{summary}');"
```

If agent-specific, create assignment records:
```bash
sqlite3 data/workspace.db "INSERT OR IGNORE INTO agent_skills (agent_slug, skill_slug, enabled) VALUES ('{agent_slug}', '{slug}', 1);"
```

### 3c: Update Agent Configs (if agent-specific)

For each assigned agent, add to their config.json skills array:

```
Read agents/{agent_slug}/config.json
Edit agents/{agent_slug}/config.json
  # Add skill to skills array
```

## Step 4: Verify & Report

```
Glob('.claude/skills/{slug}/*')                  # Files copied?
Read .claude/skills/{slug}/SKILL.md              # Readable?
```

```bash
sqlite3 data/workspace.db "SELECT slug, name, version FROM skills WHERE slug = '{slug}';"
```

If agent-specific:
```bash
sqlite3 data/workspace.db "SELECT agent_slug, skill_slug, enabled FROM agent_skills WHERE skill_slug = '{slug}';"
```

### Report

> "Installed **{skill_name}**!
>
> - Location: `.claude/skills/{slug}/`
> - Scope: {global / assigned to: agent list}
> - Version: {version}
>
> {Brief usage tip from the SKILL.md 'When to Use' section}
>
> Agents will pick it up automatically on their next session."

```
TaskUpdate({ id: task_id, status: "completed" })
```

## Success Criteria

- [ ] `.claude/skills/{slug}/SKILL.md` exists (copied from marketplace)
- [ ] Skill registered in `data/workspace.db` skills table
- [ ] If agent-specific: `agent_skills` rows exist for each assigned agent
- [ ] If agent-specific: agent config.json skills arrays updated
- [ ] Skill was not already installed (no duplicate copy)
- [ ] No file corruption during copy
- [ ] Task marked complete
