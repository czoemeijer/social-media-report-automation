# Marketing Skills Maintenance Guide

## Quick Reference

```bash
# Management script location
MANAGE=~/.gemini/marketing-skills-upstream/marketing-skills-manage.sh

# List all installed skills with source
bash $MANAGE list

# Show active marketing skills
bash $MANAGE active

# Check for upstream updates
bash $MANAGE check-updates

# Validate all symlinks
bash $MANAGE validate

# Pull latest from both repos
bash $MANAGE update

# Pull only Corey Haines
bash $MANAGE update ch

# Pull only OpenClaudia
bash $MANAGE update oc

# Rollback Corey Haines to specific commit
bash $MANAGE rollback ch 0f8d899

# Check naming conflicts
bash $MANAGE conflicts
```

## Update Workflow

### Safe Update Process

1. **Check what changed before updating:**
   ```bash
   cd ~/.gemini/marketing-skills-upstream/marketingskills
   git fetch origin
   git log HEAD..origin/main --oneline
   ```

2. **Review the diff:**
   ```bash
   git diff HEAD..origin/main -- skills/
   ```

3. **Update if safe:**
   ```bash
   bash $MANAGE update ch
   ```

4. **Validate after update:**
   ```bash
   bash $MANAGE validate
   ```

### Rollback

If an update breaks something:

```bash
# Find the previous good commit
cd ~/.gemini/marketing-skills-upstream/marketingskills
git log --oneline -10

# Rollback
bash $MANAGE rollback ch <commit-sha>
```

## Adding New Skills

### From Corey Haines
```bash
ln -s ~/.gemini/marketing-skills-upstream/marketingskills/skills/SKILL_NAME \
      ~/.gemini/config/skills/SKILL_NAME
```

### From OpenClaudia
```bash
# If no naming conflict:
ln -s ~/.gemini/marketing-skills-upstream/openclaudia-skills/skills/SKILL_NAME \
      ~/.gemini/config/skills/SKILL_NAME

# If naming conflict, use oc- prefix:
ln -s ~/.gemini/marketing-skills-upstream/openclaudia-skills/skills/SKILL_NAME \
      ~/.gemini/config/skills/oc-SKILL_NAME
```

## Removing Skills

```bash
# Remove the symlink only (upstream files preserved)
rm ~/.gemini/config/skills/SKILL_NAME
```

## Upstream Repository Locations

| Repository | Local Path | Remote |
|-----------|-----------|--------|
| Corey Haines | `~/.gemini/marketing-skills-upstream/marketingskills/` | https://github.com/coreyhaines31/marketingskills |
| OpenClaudia | `~/.gemini/marketing-skills-upstream/openclaudia-skills/` | https://github.com/OpenClaudia/openclaudia-skills |

## Current Installation Record

| Field | Value |
|-------|-------|
| Installed | 2026-10-14 |
| CH Commit | `0f8d89961cdf782dd02644b9df3ddc671c21a7f0` |
| OC Commit | `ad0d1e5820ed5368a0cff4080cef6c8fd25a34d1` |
| Total Activated | 62 marketing skills |
| Management Script | `~/.gemini/marketing-skills-upstream/marketing-skills-manage.sh` |

## Troubleshooting

### Skill not showing in Antigravity discovery
1. Check symlink: `ls -la ~/.gemini/config/skills/skill-name`
2. Verify SKILL.md exists: `cat ~/.gemini/config/skills/skill-name/SKILL.md | head -5`
3. Check frontmatter has `name:` and `description:` fields

### Broken symlink after update
The upstream repo may have renamed or removed a skill directory. Run:
```bash
bash $MANAGE validate
```
Then re-link to the new directory name.

### Too many skills causing slow discovery
Remove unnecessary skills by deleting their symlinks. The upstream repos remain intact for re-activation later.
