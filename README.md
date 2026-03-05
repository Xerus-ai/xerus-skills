# Xerus Skills Marketplace

Curated skill folders for the Xerus AI agent platform. Each folder is a self-contained skill with a `SKILL.md` entry point.

## Structure

```
skills/
  blog-writer/
    SKILL.md              # Required entry point
    references/           # Optional reference docs
    scripts/              # Optional scripts
  stock-analysis/
    SKILL.md
    references/
  ...
```

## Adding a Skill

1. Create a folder under `skills/` with a kebab-case slug
2. Add at minimum a `SKILL.md` file
3. Optionally add `references/`, `scripts/`, or other supporting files
4. Include a `.clawdhub.json` metadata file (see format below)
5. Push to `main` — GitHub Action syncs to S3 automatically

## .clawdhub.json Format

```json
{
  "slug": "blog-writer",
  "displayName": "Blog Writer",
  "summary": "Short description of what this skill does",
  "tags": ["content", "writing"],
  "version": "1.0.0"
}
```

## CI/CD

On push to `main`, the GitHub Action:
1. Detects which skill folders changed
2. Uploads changed folders to `s3://xerus-marketplace/skills/{slug}/`
3. Calls the Xerus backend API to upsert skill metadata in the DB

## Environment Secrets Required

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_REGION` (default: `ap-southeast-1`)
- `S3_MARKETPLACE_BUCKET` (default: `xerus-marketplace`)
- `XERUS_API_URL` (optional, for DB upsert)
- `XERUS_API_KEY` (optional, for DB upsert)
