# Quick Start: GitHub Repository Setup

## What You Have

Complete GitHub-ready project structure in `govee-ble-venus-py.tar.gz`:

```
govee-ble-venus-py/
├── src/                           # Source code (all fixed and working)
│   ├── parser_adapter.py          # BLE parser v1.0.3
│   ├── btmon_reader.py            # btmon manager (0x3e pattern fix)
│   ├── config_manager.py          # Configuration management
│   └── validate_parsing_v2.py     # Validation framework
├── docs/                          # Documentation
│   ├── CONVERSATION_CONTINUITY.md # For LLM session handoff
│   ├── ENVIRONMENT_NOTES.md       # Venus OS constraints
│   ├── INSTALL.md                 # Installation guide
│   └── PHASE1_SUMMARY.md          # Phase 1 completion
├── samples/                       # Sample data
│   ├── btmon_raw_60sec.txt        # 60s btmon capture
│   ├── samples_*.json             # Validation samples
│   └── README.md
├── README.md                      # Main project README
├── GITHUB_SETUP.md                # Detailed GitHub setup (this file)
└── .gitignore                     # Git ignore rules
```

## Three-Step Setup

### 1. Extract and Review
```bash
tar -xzf govee-ble-venus-py.tar.gz
cd govee-ble-venus-py
```

### 2. Create GitHub Repository
**Web Interface:**
- Go to https://github.com/new
- Name: `govee-ble-venus-py`
- **Private repository**
- Don't initialize with anything
- Create

**Or use GitHub CLI:**
```bash
gh repo create govee-ble-venus-py --private --source=. --remote=origin
```

### 3. Push to GitHub
```bash
git init
git add .
git commit -m "Initial commit: Phase 1 complete - BLE parsing and validation"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/govee-ble-venus-py.git
git push -u origin main
```

## Grant Claude Access

Choose ONE method:

### Method A: Personal Access Token (Easiest)
1. GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Generate new token
3. Select scope: `repo` (Full control of private repositories)
4. Copy token
5. Tell Claude: "Here's the access token: ghp_xxxxx..."

### Method B: Add Claude as Collaborator
1. Repository Settings → Collaborators
2. Add Claude's GitHub account (if available)

### Method C: Deploy Key
1. Generate key: `ssh-keygen -t ed25519 -f ~/.ssh/claude_govee`
2. Repository Settings → Deploy keys
3. Add public key with write access
4. Provide private key to Claude

## What Claude Will Do With Access

1. **Read** CONVERSATION_CONTINUITY.md at start of each session
2. **Read** ENVIRONMENT_NOTES.md before writing code
3. **Commit** all code changes with descriptive messages
4. **Update** CONVERSATION_CONTINUITY.md after significant work
5. **Update** ENVIRONMENT_NOTES.md when learning new constraints
6. **Push** changes regularly to keep repository current

## Verify It Works

After granting access, ask Claude:
```
"Clone the govee-ble-venus-py repository and verify you can access it"
```

Claude should respond with repository contents and confirm access.

## Important Files for Claude

### CONVERSATION_CONTINUITY.md
- Current project state
- Recent fixes and changes
- What's in progress
- Next steps
- Updated after each significant development session

### ENVIRONMENT_NOTES.md
- Venus OS command constraints
- What works, what doesn't
- Regex patterns that must be maintained
- Code patterns to follow
- Updated when new constraints discovered

## Regular Workflow

```
Session Start:
1. Claude reads CONVERSATION_CONTINUITY.md
2. Claude reads ENVIRONMENT_NOTES.md
3. You describe what needs to be done

During Session:
4. Claude makes changes
5. Claude commits changes: git commit -m "feat: description"
6. Claude pushes: git push origin main

Session End:
7. Claude updates CONVERSATION_CONTINUITY.md
8. Claude commits documentation update
9. Claude pushes final changes
```

## Next Conversation

In your next chat with Claude, say:
```
"Read the CONVERSATION_CONTINUITY.md and ENVIRONMENT_NOTES.md files 
from the govee-ble-venus-py repository to understand where we are."
```

Claude will:
1. Clone/pull latest code
2. Read documentation
3. Understand current state
4. Continue where you left off

## See GITHUB_SETUP.md for Details

The GITHUB_SETUP.md file has comprehensive instructions including:
- Detailed access methods
- Commit message formats
- Branch protection setup
- Backup strategies
- Troubleshooting
- Security considerations

---

**Current Status:** Phase 1 complete, 15-minute validation test running
**Next:** Compare validation results, then Phase 2 (D-Bus integration)
