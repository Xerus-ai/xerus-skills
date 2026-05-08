---
name: add-knowledge
description: |
  Interactive knowledge base management workflow. Upload documents, connect drive files,
  or write new knowledge directly to an agent's knowledge directory.
  Use when: user says "add knowledge", "give this to an agent", "connect a document",
  "upload to knowledge base", or invokes /add-knowledge directly.
user-invocable: true
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
---

# Add Knowledge Workflow

Interactive workflow to add documents to an agent's knowledge base.

## Step 0: Create Task

```
TaskCreate({
  title: "Add knowledge to agent: [pending]",
  description: "Interactive knowledge base management workflow",
  status: "in_progress"
})
```

## Step 1: Gather Context (Silent)

```
Read agents/index.json                              # available agents
Glob('drive/**')                                     # files in user's drive
Glob('agents/*/knowledge/*')                         # existing KB files per agent
Glob('projects/*/knowledge/*')                       # project-level knowledge
```

## Step 2: Interactive Q&A

### Q1: What Knowledge?

> "What do you want to add to an agent's knowledge base?
>
> 1. **Connect a drive file** — link an existing file from your drive to an agent
> 2. **Upload a document** — upload a PDF, DOCX, or other file from your computer
> 3. **Import from URL** — download a document from a web URL
> 4. **Write new content** — I'll help you write a document and save it to the agent's KB
> 5. **Copy from another agent** — share knowledge between agents
> 6. **Copy from project** — give an agent access to project-level docs
>
> You can also paste content directly or describe what the document should contain."

### Q2: Select Agent

> "Which agent should receive this knowledge?
>
> **Your agents:**
> {for each agent in index.json:}
> - **{name}** ({role}) — {N} knowledge files
>
> Pick an agent."

### Q3: Source-Specific Flow

#### If uploading a document (PDF, DOCX, images, etc.):

The agent cannot access the user's local filesystem. Guide them to upload via the UI first.

> "I can't access files on your computer directly, but here's how to get them in:
>
> 1. Click the **Upload** button in the workspace sidebar (or drag and drop into the drive)
> 2. Your file will land in `drive/`
> 3. Tell me when it's uploaded and I'll move it to {agent_name}'s knowledge base
>
> Or if the file is available at a URL, share the link and I'll download it directly."

Once the file appears in `drive/`, proceed with the drive file connection flow below.

#### If importing from a URL:

> "Share the URL and I'll download it."

Download the file:
```bash
curl -fsSL -o "agents/{slug}/knowledge/{filename}" "{url}"
```

If the URL is a web page (HTML), convert to markdown for better agent readability:
```bash
curl -fsSL "{url}" | python3 -c "
import sys, html
from html.parser import HTMLParser
# Simple HTML to text extraction
content = sys.stdin.read()
# Strip tags, keep text
import re
text = re.sub('<[^>]+>', '', content)
text = html.unescape(text)
print(text)
" > "agents/{slug}/knowledge/{filename}.md"
```

Or use `WebFetch` tool if available for cleaner extraction.

#### If connecting a drive file:

> "Which file from your drive?
>
> **Available files:**
> {list files from drive/ directory}
>
> Pick a file, or describe what you're looking for and I'll search."

Then copy the file to the agent's knowledge directory.

#### If writing new content:

> "What should this document cover? Give me a topic and I'll draft it.
>
> Examples:
> - 'Our brand voice guidelines'
> - 'Competitor pricing analysis for Q2'
> - 'Product roadmap and priorities'
>
> Or paste the content directly."

If user gives a topic, ask clarifying questions:
> "A few quick questions to make this useful for {agent_name}:
>
> 1. What's the key information {agent_name} needs from this?
> 2. Any specific data, links, or references to include?
> 3. How detailed should it be — overview or comprehensive?"

Then generate the document and show a preview before saving.

#### If copying from another agent:

> "Which agent's knowledge do you want to share?
>
> {for each agent with knowledge files:}
> - **{name}**: {list knowledge files}
>
> Pick files to copy to {target_agent}'s knowledge base."

#### If copying from project:

> "Which project knowledge?
>
> {for each project with knowledge files:}
> - **{project}**: {list knowledge files}
>
> Pick files to copy."

### Q4: File Naming

If the file needs a name (new content or rename):

> "What should I name this file?
>
> Suggestion: `{auto-generated-name}.md`
> (Use descriptive names — 'competitor-pricing-q2-2026.md' not 'doc1.md')
>
> Accept the suggestion or type a name:"

### Q5: Confirmation

> "Add **{filename}** to **{agent_name}**'s knowledge base?
>
> {Preview first ~200 chars of content}
>
> The agent will reference this file in their next session."

## Step 3: Execute

### 3a: Write File to Agent Knowledge

```
Write agents/{slug}/knowledge/{filename}
  content: {content}
```

### 3b: If Connecting Drive File (Copy)

```bash
cp "drive/{source_file}" "agents/{slug}/knowledge/{filename}"
```

### 3c: If Sharing Between Agents (Copy)

```bash
cp "agents/{source_slug}/knowledge/{filename}" "agents/{target_slug}/knowledge/{filename}"
```

### 3d: Register in DB (for cross-agent discovery)

```bash
sqlite3 data/workspace.db "INSERT OR IGNORE INTO agent_knowledge_bases (agent_slug, kb_id, access_level) VALUES ('{slug}', '{filename}', 'read');"
```

### 3e: Update Module CLAUDE.md

The agent's Module CLAUDE.md has a "Knowledge Base" section that lists available documents. This is auto-regenerated by the ModuleClaudeMdGenerator on next execution, but we can verify it will pick up the new file.

```
Glob('agents/{slug}/knowledge/*')    # Verify file appears
```

## Step 4: Verify & Report

### Verification Checklist

```
Read agents/{slug}/knowledge/{filename}              # File exists and readable?
Glob('agents/{slug}/knowledge/*')                     # Total KB file count
```

```bash
sqlite3 data/workspace.db "SELECT agent_slug, kb_id FROM agent_knowledge_bases WHERE agent_slug = '{slug}';"
```

### Report

> "Added **{filename}** to **{agent_name}**'s knowledge base!
>
> {agent_name} now has {N} knowledge files:
> {list all files in agents/{slug}/knowledge/}
>
> They'll reference this document automatically in their next session.
>
> Want to add more? Just say 'add more knowledge' or drop another file."

### Update Task

```
TaskUpdate({ id: task_id, status: "completed" })
```

## Bulk Operations

If user wants to add multiple files at once:

> "I can add multiple files. List them all, or say 'add everything from drive/' to bulk-import."

For bulk:
```bash
cp drive/{file1} agents/{slug}/knowledge/
cp drive/{file2} agents/{slug}/knowledge/
# ... etc
```

Register each in DB:
```bash
sqlite3 data/workspace.db "INSERT OR IGNORE INTO agent_knowledge_bases (agent_slug, kb_id, access_level) VALUES ('{slug}', '{file1}', 'read'), ('{slug}', '{file2}', 'read');"
```

## Success Criteria

- [ ] Knowledge file exists at `agents/{slug}/knowledge/{filename}`
- [ ] File content is complete and not truncated
- [ ] File has a descriptive name (not generic like doc.md or temp.txt)
- [ ] Registered in `agent_knowledge_bases` table in `data/workspace.db`
- [ ] If copied from another source: original file unchanged
- [ ] If new content: reviewed/approved by user before saving
- [ ] Agent's knowledge directory is not empty
- [ ] No duplicate filenames in the agent's knowledge directory
- [ ] Task marked complete
