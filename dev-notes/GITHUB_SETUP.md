# GitHub Repository Setup Instructions

## Step 1: Create the Private Repository

### Via GitHub Web Interface:
1. Go to https://github.com/new
2. Repository name: `govee-ble-venus-py`
3. Description: "Govee H5101 BLE sensor bridge for Victron Venus OS"
4. **Select: Private**
5. Do NOT initialize with README (we have one)
6. Do NOT add .gitignore (we have one)
7. Do NOT add license (none specified yet)
8. Click "Create repository"

### Via GitHub CLI (alternative):
```bash
gh repo create govee-ble-venus-py --private --source=. --remote=origin --push
```

## Step 2: Initialize and Push Local Repository

On your local machine where you downloaded the project files:

```bash
# Navigate to the project directory
cd /path/to/govee-ble-venus-py

# Initialize git repository
git init

# Add all files
git add .

# Create initial commit
git commit -m "Initial commit: Phase 1 complete - BLE parsing and validation

- Implemented BLE advertisement parser (parser_adapter.py)
- Implemented btmon process manager (btmon_reader.py)
- Fixed HCI event detection using 0x3e pattern
- Added configuration management (config_manager.py)
- Created validation framework (validate_parsing_v2.py)
- Temperature accuracy: ±0.5°C
- Battery accuracy: exact
- Known issue: humidity ~15-20% error
- Documentation and sample data included"

# Add remote (replace YOUR_USERNAME with your GitHub username)
git remote add origin https://github.com/YOUR_USERNAME/govee-ble-venus-py.git

# Push to GitHub
git branch -M main
git push -u origin main
```

## Step 3: Grant Claude Access to Repository

To allow Claude to access your private repository for making commits and updates:

### Option A: Personal Access Token (Recommended)
1. Go to GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Click "Generate new token (classic)"
3. Note: "Claude AI access for govee-ble-venus-py"
4. Expiration: Choose appropriate duration (90 days, 1 year, or no expiration)
5. Select scopes:
   - ✓ `repo` (Full control of private repositories)
   - ✓ `workflow` (if using GitHub Actions)
6. Click "Generate token"
7. **IMPORTANT:** Copy the token immediately (you won't see it again)
8. Provide this token to Claude in your next conversation

### Option B: Deploy Key (Read-only or Read-write)
1. Generate SSH key pair:
```bash
ssh-keygen -t ed25519 -C "claude-ai-govee-ble" -f ~/.ssh/claude_govee_key
```
2. Go to repository Settings → Deploy keys → Add deploy key
3. Title: "Claude AI Access"
4. Key: Paste contents of `~/.ssh/claude_govee_key.pub`
5. ✓ Check "Allow write access"
6. Click "Add key"
7. Provide the private key to Claude

### Option C: GitHub App (Most Secure, Advanced)
Create a GitHub App with repository access - more complex but most secure for production.

## Step 4: Verify Claude Can Access Repository

Once you've provided Claude with access credentials, ask Claude to:
1. Clone the repository
2. Make a test commit
3. Push the test commit
4. Verify it appears on GitHub

Test command for Claude:
```bash
# Claude should be able to run:
git clone https://github.com/YOUR_USERNAME/govee-ble-venus-py.git
cd govee-ble-venus-py
echo "# Test file" > TEST.md
git add TEST.md
git commit -m "Test: Verify Claude repository access"
git push origin main
```

## Step 5: Set Up Automated Documentation Updates

### Create GitHub Action for Auto-commits (Optional)
You can create a workflow that automatically commits documentation updates:

`.github/workflows/auto-update-docs.yml` (create this if desired):
```yaml
name: Auto-update Documentation
on:
  workflow_dispatch:  # Manual trigger
  
jobs:
  update-docs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Update documentation
        run: |
          # Scripts to update docs
          echo "Documentation updated: $(date)" >> docs/UPDATE_LOG.md
      - name: Commit changes
        run: |
          git config --local user.email "action@github.com"
          git config --local user.name "GitHub Action"
          git add docs/
          git commit -m "Auto-update documentation [skip ci]" || echo "No changes"
          git push
```

## Ongoing Workflow

### When Working with Claude:
1. **Before each session:** Claude reads latest CONVERSATION_CONTINUITY.md
2. **During session:** Claude makes code changes and commits them
3. **End of session:** Claude updates CONVERSATION_CONTINUITY.md
4. **Regular updates:** Claude updates ENVIRONMENT_NOTES.md when learning new constraints

### Commit Message Format:
```
Type: Brief description

- Detailed change 1
- Detailed change 2
- Related issue or context

[optional] Breaking changes or notes
```

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`

### Example Commits:
```bash
# Feature addition
git commit -m "feat: Add D-Bus temperature sensor registration

- Implement temperature sensor class
- Add D-Bus service path configuration
- Handle sensor disconnection gracefully
- Tested with both Govee H5101 sensors"

# Bug fix
git commit -m "fix: Correct HCI event pattern for btmon truncation

- Changed pattern to match on 0x3e hex code
- Resolves issue with events stopping after #99
- Verified against 60-second btmon capture"

# Documentation update
git commit -m "docs: Update conversation continuity for validation phase

- Added current validation test status
- Documented humidity accuracy findings
- Updated next steps for Phase 2"
```

## Backup Strategy

### Local Backups:
```bash
# Create backup of entire project
tar -czf govee-ble-venus-py-backup-$(date +%Y%m%d).tar.gz govee-ble-venus-py/
```

### GitHub Protections:
1. Enable branch protection for `main`
2. Require pull requests for major changes
3. Consider creating `develop` branch for active work

## Repository Maintenance

### Regular Tasks:
- [ ] Weekly: Review commits for consistency
- [ ] After major changes: Update README.md
- [ ] After each development session: Update CONVERSATION_CONTINUITY.md
- [ ] When discovering new constraints: Update ENVIRONMENT_NOTES.md
- [ ] Before major version: Tag release (e.g., `v1.0.0-phase1`)

### Tagging Releases:
```bash
# Phase 1 complete
git tag -a v1.0.0-phase1 -m "Phase 1: BLE parsing and validation complete"
git push origin v1.0.0-phase1

# Future phases
git tag -a v2.0.0-phase2 -m "Phase 2: D-Bus integration complete"
git push origin v2.0.0-phase2
```

## Security Considerations

1. **Never commit secrets:** API keys, passwords, tokens
2. **Verify .gitignore:** Check it excludes sensitive files
3. **Review commits:** Before pushing, review what's being committed
4. **Rotate tokens:** Regularly update access tokens
5. **Private repository:** Keep repository private (already set)

## Troubleshooting

### Authentication Failed
```bash
# Check remote URL
git remote -v

# Update if needed (use HTTPS with token or SSH)
git remote set-url origin https://YOUR_TOKEN@github.com/YOUR_USERNAME/govee-ble-venus-py.git
```

### Push Rejected
```bash
# Pull latest changes first
git pull origin main --rebase

# Then push
git push origin main
```

### Claude Can't Access
- Verify token hasn't expired
- Check token has correct scopes (repo access)
- Ensure repository name is correct
- Verify token is properly configured

## Next Steps After Setup

1. ✓ Repository created
2. ✓ Initial commit pushed
3. ✓ Claude has access
4. → Begin Phase 2 development with version control
5. → All changes committed regularly
6. → Documentation updated after each session

## Getting Help

- GitHub Docs: https://docs.github.com
- Git Basics: https://git-scm.com/doc
- Issues with access: Check GitHub token permissions
