---
name: content-creation
description: "Xerus content strategy for non-technical audience — solo founders, coaches, creators, consultants. Pain-point-first storytelling, virtual office narrative, and show-don't-tell product marketing. Triggers on: content strategy, blog post, content creation, video script, content repurposing, brand narrative."
---

# Content Creation — Xerus

## Brand Narrative

**Core story**: You're a one-person show. You can't afford a team. Xerus lets you build a virtual office and hire AI agents as your team members. Each has a role, personality, tools, knowledge — ready when you need them.

**NOT the story**: "We built an AI agent platform with SDK orchestration and multi-model support."

## Content Pillars

### 1. "Running a Business Alone is Hard" (40%)
Pain points the audience lives every day:
- Wearing 10 hats as a solo founder
- Spending more time on admin than on actual work
- Can't afford to hire but can't scale without help
- The 3am email catch-up, the weekend content batch

### 2. "What If You Had a Team?" (30%)
The Xerus solution, always shown through specific examples:
- "My research agent pulled competitor pricing while I slept"
- "My content agent drafted 5 social posts. I just approved them."
- "Client onboarding used to take me 2 hours. Now it's 15 minutes."

### 3. "Building in Public" (20%)
The founder journey — transparent, honest, relatable:
- What we shipped this week
- What broke and how we fixed it
- User feedback that changed our roadmap
- The decision to build Xerus (founder story)

### 4. "The Future of Work" (10%)
Light industry commentary — always framed for non-technical audience:
- "AI won't replace you. But someone using AI will."
- NOT: "Claude 4 has 200K context and tool use"
- Always bring it back to: what does this mean for a solo founder?

## Audience Personas (write for THEM, not for developers)

### Maya — Solo Founder (Primary)
- Runs a small SaaS or service business
- Technical enough to use Notion, not enough to code
- Pain: drowning in operations, can't focus on product
- Dream: "I just want to build my product and let someone else handle the rest"
- Language: "overwhelmed", "wearing too many hats", "need to hire but can't afford it"

### Jordan — Content Creator
- YouTube, newsletter, social media presence
- Pain: content calendar management, research, scheduling
- Dream: "I want to create, not manage a content empire"
- Language: "burnout", "content treadmill", "batch creation"

### Priya — Coach/Mentor
- 1-on-1 or small group coaching practice
- Pain: session prep, follow-up notes, client onboarding, scheduling
- Dream: "I want to coach more clients without working more hours"
- Language: "scaling", "admin work", "client experience"

### Sam — Consultant
- Solo consultant or small firm
- Pain: proposals, research, invoicing prep, client comms
- Dream: "I want to do the strategy work, not the admin"
- Language: "billable hours", "back office", "overhead"

## Writing Rules

### Headlines
- Lead with pain, not product
- Bad: "Xerus: AI Agent Platform for Business Automation"
- Good: "You're running a business alone. Here's your team."

### Body copy
- Short sentences. Short paragraphs.
- Concrete examples over abstract claims
- "Draft your newsletter" not "content generation capabilities"
- "Research your competitors" not "autonomous information retrieval"
- Use "you" and "your" — talk TO them
- Never explain how the tech works — show what it DOES

### Product references
- "Your virtual office" — not "AI platform"
- "Hire agents" — not "deploy agents"
- "Give them tools" — not "configure MCP integrations"
- "Watch them work" — not "monitor execution traces"
- "Workspaces, projects, channels" — like Slack, but your team is AI

## Content Formats

### Twitter (primary — see twitter-engagement skill)
- Replies to target accounts (40%)
- Pain point threads (25%)
- Product glimpses (15%)
- Building in public (10%)
- Industry commentary (10%)

### LinkedIn (secondary)
- Longer-form founder story posts
- "Day in the life of a solo founder with a virtual office"
- Target: founders, coaches, consultants in professional context

### Blog / Newsletter (planned)
- Use case deep-dives: "How a coach uses Xerus to handle 30 clients"
- "Behind the build" — technical decisions explained simply
- Guest posts from early users

## Content Production Process

1. **Find the pain**: What are solo founders complaining about today? (bird search, Reddit, HN)
2. **Draft from pain**: Start with the problem, not the solution
3. **Score with x-algo**: Run draft through `analyze_x_post.py` — aim for score >= 1.0
4. **Check voice**: Does this sound like a founder talking to a friend? Or a SaaS marketing page?
5. **Post**: Via `post.py` for X, manual for LinkedIn
6. **Engage**: Reply to every comment within 2 hours
7. **Learn**: Track what resonated, update `.memory/agents/{slug}/expertise.md`

## Anti-Patterns (NEVER do these)

- "Revolutionary AI-powered platform" — vague, sounds like every other startup
- "10x your productivity" — meaningless multiplier
- Technical architecture as a selling point — nobody cares about your SDK
- Feature lists — "supports 100+ integrations" says nothing about value
- Comparing to developer tools — your audience doesn't use developer tools
- AI industry jargon — "multi-modal", "fine-tuned", "RAG", "vector embeddings"
