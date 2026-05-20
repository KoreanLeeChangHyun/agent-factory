"""constants.py - project common constant and static data integration module.

. defines common use constants, patterns, mappings in agent-factory/engine/ subscripts.
This module is a leaf module that does not import any other module.

Price:
    C RED, C BLUE, ..., C RESET: ANSI Color Code
    STEP COLORS: Color mapping by step
    TS PATTERN: YYYMMDD-HMMSS timestamp regular expression
    KST: KST Time Zone (UTC+9)
    TERMINAL STEPS: Termination status assembly
    FSM TRANSITIONS: FSM status pre-registration rules
    DANGER PATTERNS: List of risk command blocking patterns
    KEEP COUNT: .workflow/ directory retaining maximum number (environmental variable CLAUDE WORKFLOW KEEP COUNT)
    CHAIN SEPARATOR: Chain command separator (">" character)
    CHAIN MAX RETRY: The maximum number of reciprocating times when the chain stage fails (can override the environment variable CLAUDE CHAIN MAX RETRY)

T-453: Multi-key 8 status (NONE/INIT/PLAN/WORK/VALIDATE/REPORT/DONE/FAIL=FAILED alias).
"""

#   workflow_phase / work_step / kanban_status / artifact / final_report
#   phase_verify / ticket_validate / verifier_failure / validator_failure / retry_context

from __future__ import annotations

import os
import re
from datetime import timezone, timedelta


# =============================================================================
# . settings file loader — a single source of all settings
# =============================================================================
def _find_project_root() -> str:
    """Scripts/data/constants.py"""
    d = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(d, '..', '..', '..'))


def _load_dotenv() -> dict[str, str]:
    """. parse the agent-factory/.settings file and return it to key=value dict.

    Packaging:
        - The line starting with '#' is ignored by the tin.
        - blank rows.
        - '=' is not a valid KEY=VALUE format, so it is skipd.
        - The left side of the '=' is KEY, and the right side is VALUE (the '=' in VALUE as partition is preserved).
        - Remove the inline tin('#...') on the right side of VALUE.
          However, the value that is deprecated as a quote (e.g. KEY="val # not comment") will not be handled as a comment.
        - Strip both KEY and VALUE.

    Priority (high above):
        1. FAQ os.environ (runtime environment variable)
        2. .settings file (This function parsing)
        3. FAQs default value for each  env()/ env int()/ env float() call

    Returns:
        dict[str, str]: KEY -> VALUE mapping
    """
    cw_dir = os.path.join(_find_project_root(), '.agent-factory')
    settings_path = os.path.join(cw_dir, '.settings')
    env_file = settings_path
    result: dict[str, str] = {}
    if not os.path.exists(env_file):
        return result
    with open(env_file, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # The entire tin line begins with empty rows or '#' crosses
            if not line or line.startswith('#'):
                continue
            # KEY=VALUE
            if '=' not in line:
                continue
            # The partition is separated only the first '=', so the '=' in VALUE is preserved
            # Example: KEY=a=b=c → key="", value="a=b=c"
            key, _, value = line.partition('=')
            value = value.strip()
            # Inline tin removal: Remove the '#...' pattern of VALUE that is not wrapped with a quote
            # Example: 30# Inert Fixing Time → 30
            # Example: "hello # world" → hello # world (preserved inside a quote)
            if value and not (value.startswith('"') and value.endswith('"')) \
                      and not (value.startswith("'") and value.endswith("'")):
                # Remove the tin part by separating the '#' pattern
                # "#" without spaces (e.g. C#code, color=#fff) preserves as part of the value
                comment_idx = value.find(' #')
                if comment_idx != -1:
                    value = value[:comment_idx].rstrip()
            else:
                # The value that is depressed with a quote is only double quotes
                value = value[1:-1]
            result[key.strip()] = value
    return result


_DOTENV = _load_dotenv()


def _env(key: str, default: str) -> str:
    """os.environ > .settings > returns the value to default priority."""
    return os.environ.get(key, _DOTENV.get(key, default))


def _env_int(key: str, default: int) -> int:
    return int(_env(key, str(default)))


def _env_float(key: str, default: float) -> float:
    return float(_env(key, str(default)))


# =============================================================================
# ANSI Color Code constant
# =============================================================================
C_RED = "\033[0;31m"
C_BLUE = "\033[0;34m"
C_GREEN = "\033[0;32m"
C_PURPLE = "\033[0;35m"
C_YELLOW = "\033[0;33m"
C_CYAN = "\033[0;36m"
C_GRAY = "\033[0;90m"
C_CLAUDE = "\033[38;2;222;115;86m"  # Claude brand Peach #DE7356
C_BOLD = "\033[1m"
C_DIM = "\033[2m"
C_RESET = "\033[0m"

# =============================================================================
# Color Mapping by Step
# =============================================================================
STEP_COLORS = {
    "INIT": C_RED,
    "PLAN": C_BLUE,
    "WORK": C_GREEN,
    "VALIDATE": C_CYAN,  # multi mode — WORK→REPORT validation stage (STRATEGY and color sharing, context separation)
    "REPORT": C_PURPLE,
    "STRATEGY": C_CYAN,
    "DONE": C_YELLOW,
    "STALE": C_GRAY,
    "FAILED": C_RED,
    "CANCELLED": C_GRAY,
}

# {{ data.filesizeHumanReadable }}
PHASE_COLORS = STEP_COLORS

# =============================================================================
# YYYYMMDD-HMMSS pattern regular expression
# =============================================================================
TS_PATTERN = re.compile(r"^\d{8}-\d{6}$")

# =============================================================================
# KST Time Zone (UTC+9)
# =============================================================================
KST = timezone(timedelta(hours=9))

# =============================================================================
# {{ data.filesizeHumanReadable }}
# =============================================================================
STALE_TTL_MINUTES = _env_int("CLAUDE_STALE_TTL_MINUTES", 30)
ZOMBIE_TTL_HOURS = _env_int("CLAUDE_ZOMBIE_TTL_HOURS", 24)
REPORT_TTL_HOURS = _env_int("CLAUDE_REPORT_TTL_HOURS", 1)
KEEP_COUNT = _env_int("CLAUDE_WORKFLOW_KEEP_COUNT", 10)
WORK_NAME_MAX_LEN = _env_int("CLAUDE_WORK_NAME_MAX_LEN", 20)

# =============================================================================
# Terminal filename
#   - kanban status (To Do/Open/In Progress/Review/Done) and workflow phase (INIT.DONE)
# =============================================================================
STATUS_FILENAME = "status.json"
CONTEXT_FILENAME = ".context.json"
STOP_BLOCK_COUNTER_FILENAME = ".stop-block-counter"
BYPASS_FILENAME = "bypass"
# `full` == `multi` (including multi agent + VALIDATE stage, user explicit 2026-05-13).
# `light` is a star track (boil — no user express consent).
FSM_TRANSITIONS = {
    "multi": {
        "NONE": ["INIT", "STALE", "FAILED", "CANCELLED"],
        "INIT": ["PLAN", "STALE", "FAILED", "CANCELLED"],
        "PLAN": ["WORK", "STALE", "FAILED", "CANCELLED"],
        "WORK": ["VALIDATE", "STALE", "FAILED", "CANCELLED"],
        "VALIDATE": ["REPORT", "WORK", "STALE", "FAILED", "CANCELLED"],
        "REPORT": ["DONE", "STALE", "FAILED", "CANCELLED"],
    },
    "full": {
        "NONE": ["INIT", "STALE", "FAILED", "CANCELLED"],
        "INIT": ["PLAN", "STALE", "FAILED", "CANCELLED"],
        "PLAN": ["WORK", "STALE", "FAILED", "CANCELLED"],
        "WORK": ["VALIDATE", "STALE", "FAILED", "CANCELLED"],
        "VALIDATE": ["REPORT", "WORK", "STALE", "FAILED", "CANCELLED"],
        "REPORT": ["DONE", "STALE", "FAILED", "CANCELLED"],
    },
    "light": {
        "INIT": ["WORK", "STALE", "FAILED", "CANCELLED"],
        "NONE": ["WORK", "STALE", "FAILED", "CANCELLED"],
        "WORK": ["DONE", "STALE", "FAILED", "CANCELLED"],
    },
}

# =============================================================================
# Active command/mode assembly
# =============================================================================
VALID_COMMANDS = {"implement", "review", "research"}
VALID_MODES = {"full", "light"}

# =============================================================================
# Chain command
# =============================================================================
CHAIN_SEPARATOR = ">"
CHAIN_MAX_RETRY = _env_int("CLAUDE_CHAIN_MAX_RETRY", 2)

# =============================================================================
# Default 0 = retry inactive (Return 0 guarantee). .settings only retry operations when explicitly activated.
#   retry context = failure handler.py retry-context.json data structure
#   WORKFLOW RETRY <PHASE> value is equivalent to retry context.max retries
# =============================================================================
WORKFLOW_RETRY_INIT = _env_int("WORKFLOW_RETRY_INIT", 0)        # retry context: INIT workflow phase maximum retry count when failed
WORKFLOW_RETRY_PLAN = _env_int("WORKFLOW_RETRY_PLAN", 0)        # retry context: maximum retry count when PLAN workflow phase failed
WORKFLOW_RETRY_WORK = _env_int("WORKFLOW_RETRY_WORK", 0)        # retry context: WORK workflow phase maximum retry count when failed
WORKFLOW_RETRY_VALIDATE = _env_int("WORKFLOW_RETRY_VALIDATE", 0)  # retry context: VALIDATE workflow phase maximum retry count when failed
WORKFLOW_RETRY_REPORT = _env_int("WORKFLOW_RETRY_REPORT", 0)    # retry context: REPORT workflow phase maximum retry count when failed
WORKFLOW_RETRY_PROMPT_N = _env_int("WORKFLOW_RETRY_PROMPT_N", 3)  # retry context: hint history array cap (LIFO truncate)

# mapping retry maximum number of workflow phase keys — failure handler.py
PHASE_RETRY_MAX: dict[str, int] = {
    "INIT": WORKFLOW_RETRY_INIT,
    "PLAN": WORKFLOW_RETRY_PLAN,
    "WORK": WORKFLOW_RETRY_WORK,
    "VALIDATE": WORKFLOW_RETRY_VALIDATE,
    "REPORT": WORKFLOW_RETRY_REPORT,
}


def get_phase_retry_max(phase: str) -> int:
    """returns the maximum retry of the phase as a workflow phase identifier.

    Name Dictionary: The `phase` argument is the identifier of the workflow phase domain,
    The return value is used in retry context context to max retries.

    Args:
        phase: workflow phase identifier (INIT/PLAN/WORK/VALIDATE/REPORT).

    Returns:
        maximum retry of workflow phase. Unknown phase returns 0.
    """
    return PHASE_RETRY_MAX.get(phase, 0)


# =============================================================================
# Quality verification threshold
# =============================================================================
QUALITY_THRESHOLD = _env_float("CLAUDE_QUALITY_THRESHOLD", 0.6)

# =============================================================================
# Configuring a bidder
# =============================================================================
BUDGET_CEILING = _env_int("BUDGET_CEILING", 0)  # 0Reactive
BUDGET_THRESHOLDS: dict[int, str] = {75: "INFO", 80: "WARN", 90: "HIGH", 100: "CRITICAL"}

# =============================================================================
# Hallucination logging settings
# =============================================================================
HOOK_HALLUCINATION_LOGGER = _env("HOOK_HALLUCINATION_LOGGER", "true")
HALLU_TARGET_AGENT_TYPES: set[str] = {"worker", "explorer"}

# =============================================================================
# ERROR Settlement Notification
# =============================================================================
ERROR_THRESHOLD = _env_int("CLAUDE_ERROR_THRESHOLD", 3)  # ERROR count threshold for workflow


def parse_chain_command(raw: str) -> list[str]:
    """parsing the chain command string to return the segment list.

    Args:
        raw: command string. Single ("implement") or chain ("research>implement>review") format.

    Returns:
        Available command segment list. Single command returns to the length 1 list.

    Raises:
        ValueError: In case of unavailable segments.

    Note:
        Allows duplicate command segment (e.g. 'implement>implement').
        We use cookies to ensure that we give you the best experience on our website. If you continue to use this site we will assume that you are happy with it.Ok

    Examples:
        >>> parse_chain_command("implement")
        ['implement']
        >>> parse_chain_command("research>implement>review")
        ['research', 'implement', 'review']
        >>> parse_chain_command("implement>implement")
        ['implement', 'implement']
    """
    segments = [seg.strip() for seg in raw.split(CHAIN_SEPARATOR)]
    for seg in segments:
        if seg not in VALID_COMMANDS:
            raise ValueError(
                f"Invalid command segment: '   FIELD 0 '."
                f"Permissible Value:   FIELD 0  "
            )
    return segments


# =============================================================================
# Terminal step assembly
# =============================================================================
TERMINAL_STEPS = {"DONE", "FAILED", "STALE", "CANCELLED"}

# {{ data.filesizeHumanReadable }}
TERMINAL_PHASES = TERMINAL_STEPS

# =============================================================================
# Home
# =============================================================================
BYTES_GB = 1073741824
BYTES_MB = 1048576
BYTES_KB = 1024

# =============================================================================
# External API URL
# =============================================================================
SLACK_API_URL = _env("CLAUDE_SLACK_API_URL", "https://slack.com/api/chat.postMessage")

# =============================================================================
# Log In
# =============================================================================
CODE_SYNC_REMOTE_REPO = _env("CLAUDE_REPO_URL", "https://github.com/KoreanLeeChangHyun/claude-workflow.git")
STALE_TTL_SECONDS = STALE_TTL_MINUTES * 60

# =============================================================================
# Mapping moji by Slack Agent
# =============================================================================
SLACK_EMOJI_MAP = {
    "init": ":large_orange_circle:",
    "planner": ":large_blue_circle:",
    "worker": ":large_green_circle:",
    "reporter": ":purple_circle:",
}

# =============================================================================
# Scots Gaelic
# =============================================================================
HEADER_LINE = "| Date | WorkID | Title & Contents | Instruction | Status | Quality | File | Planning | Work | Report |"
SEPARATOR_LINE = "|------|--------|------------|--------|------|------|------|------|------|------|"
SKILLS_HEADER_LINE = "| Date | WorkID | Command | TSK | Original Skills | Skill List | fallback | Token sec |"
SKILLS_SEPARATOR_LINE = "|------|--------|--------|---------|----------|----------|---------|---------|"
LOGS_HEADER_LINE = "| Date | WorkID | Title | Command | WARN | ERROR | HALLU | ART | Size | Log |"
LOGS_SEPARATOR_LINE = "|------|--------|------|------|------|-------|------|-----|------|------|"
USAGE_HEADER_LINE = "| Date | Work ID | Title | Order | ORC | PLN | WRK | EXP | VAL | RPT | Total | Budget |"
USAGE_SEPARATOR_LINE = "|------|--------|------|------|-----|-----|-----|-----|-----|-----|------|------|"

# =============================================================================
# Step → One-Step Text Mapping
# =============================================================================
STEP_STATUS_MAP = {
    "DONE": "Application",
    "REPORT": "Venue",
    "STALE": "Home",
    "WORK": "Venue",
    "VALIDATE": "Venue",  # Multi Mode
    "STRATEGY": "Venue",
    "PLAN": "Venue",
    "INIT": "Venue",
    "CANCELLED": "Home",
    "FAILED": "Home",
    "UNKNOWN": "Home",
    "NONE": "Home",
}

# {{ data.filesizeHumanReadable }}
PHASE_STATUS_MAP = STEP_STATUS_MAP

# =============================================================================
# Hazard Command Whitelist (Herbal Pattern)
# =============================================================================
DANGER_WHITELIST = [
    {"pattern": "rm\\s+-r[f]?\\s+/tmp/", "note": None},
    {"pattern": "rm\\s+-r[f]?\\s+.*\\.workflow/", "note": None},
    {"pattern": "sudo\\s+rm\\s+-r[f]?\\s+/tmp/", "note": None},
    {"pattern": "sudo\\s+rm\\s+-r[f]?\\s+.*\\.workflow/", "note": None},
    {"pattern": "git\\s+push\\s+--force-with-lease", "note": None},
]

# =============================================================================
# Dangerous command blocking pattern
# =============================================================================
DANGER_PATTERNS = [
    {"pattern": "(sudo\\s+)?rm\\s+-r[f]*\\s+/\\s*$", "blocked": "rm -rf / (Remove root directory)", "alternative": "Specify a specific path or use a rm -ri-to-do dialog box."},
    {"pattern": "(sudo\\s+)?rm\\s+--recursive\\s+(-f|--force)\\s+/\\s*$", "blocked": "rm --recursive --force / (delete root directory)", "alternative": "Specify a specific path or use a rm -ri-to-do dialog box."},
    {"pattern": "(sudo\\s+)?rm\\s+(-f|--force)\\s+--recursive\\s+/\\s*$", "blocked": "rm --force --recursive / (delete root directory)", "alternative": "Specify a specific path or use a rm -ri-to-do dialog box."},
    {"pattern": "(sudo\\s+)?rm\\s+--recursive\\s+/\\s*$", "blocked": "rm --recursive / (delete root directory)", "alternative": "Specify a specific path or use a rm -ri-to-do dialog box."},
    {"pattern": "(sudo\\s+)?rm\\s+-r[f]*\\s+~", "blocked": "rm -rf", "alternative": "Specifies a specific file / directory."},
    {"pattern": "(sudo\\s+)?rm\\s+--recursive(\\s+--force)?\\s+~", "blocked": "rm --recursive ~ (Restore home directory)", "alternative": "Specifies a specific file / directory."},
    {"pattern": "(sudo\\s+)?rm\\s+-r[f]*\\s+\\.\\s*$", "blocked": "rm -rf . (current directory full deletion)", "alternative": "Specifies a specific file / directory."},
    {"pattern": "(sudo\\s+)?rm\\s+--recursive(\\s+--force)?\\s+\\.\\s*$", "blocked": "rm --recursive . (currently delete directory)", "alternative": "Specifies a specific file / directory."},
    {"pattern": "(sudo\\s+)?rm\\s+-r[f]*\\s+\\*", "blocked": "rm -rf * (Remove the wildcard)", "alternative": "Specifies a specific file / directory or checks the list as ls first."},
    {"pattern": "(sudo\\s+)?rm\\s+--recursive(\\s+--force)?\\s+\\*", "blocked": "rm --recursive * (delete wildcard)", "alternative": "Specifies a specific file / directory or checks the list as ls first."},
    {"pattern": "(sudo\\s+)?git\\s+reset\\s+--hard", "blocked": "git reset --hard", "alternative": "git stash"},
    {"pattern": "(sudo\\s+)?git\\s+push\\s+(--force|-f)", "blocked": "git push --force", "alternative": "git push --force-with-lease"},
    {"pattern": "(sudo\\s+)?git\\s+clean\\s+-[fd]*f", "blocked": "git clean -f (delete the files that aren't added)", "alternative": "git clean -n"},
    {"pattern": "(sudo\\s+)?git\\s+branch\\s+-D\\s+(main|master)", "blocked": "git branch -D main/master", "alternative": "The main branch deletion is very dangerous. Please check if you need it."},
    {"pattern": "(sudo\\s+)?git\\s+(checkout|restore)\\s+\\.\\s*$", "blocked": "git checkout/restore . (Return all changes)", "alternative": "git stash"},
    {"pattern": "(?i)(sudo\\s+)?DROP\\s+(TABLE|DATABASE)", "blocked": "DROP TABLE/DATABASE", "alternative": "Perform backups first and run within the transaction."},
    {"pattern": "(sudo\\s+)?chmod\\s+777", "blocked": "chmod 777", "alternative": "chmod 755"},
    {"pattern": "(sudo\\s+)?chmod\\s+a\\+rwx", "blocked": "chmod a+rwx", "alternative": "chmod 755"},
    {"pattern": "(sudo\\s+)?chmod\\s+o\\+w", "blocked": "chmod o+w", "alternative": "chmod 755"},
    {"pattern": "(sudo\\s+)?chmod\\s+ugo\\+rwx", "blocked": "chmod ugo+rwx", "alternative": "chmod 755"},
    {"pattern": "(sudo\\s+)?mkfs", "blocked": "mkfs (desk format)", "alternative": "Disk format is very dangerous. Please check the target device."},
    {"pattern": "(sudo\\s+)?dd\\s+if=", "blocked": "dd if=", "alternative": "dd command cannot be returned. Please check the target device."},
    {"pattern": "(sudo\\s+)?rm\\s+-r[f]*\\s+.*\\.claude\\.workflow/kanban", "blocked": "rm -rf .agent-factory/kanban (delete directory)", "alternative": "The Kanban Director is a workflow core data. Do not delete it."},
]

# =============================================================================
# hooks self-protection guard: read-only command pattern
# =============================================================================
GUARD_READONLY_PATTERNS = [
    "^\\s*git\\s", "^\\s*python3?\\s", "^\\s*node\\s", "^\\s*cat\\s",
    "^\\s*ls\\b", "^\\s*head\\s", "^\\s*tail\\s", "^\\s*wc\\s",
    "^\\s*grep\\s", "^\\s*file\\s", "^\\s*stat\\s", "^\\s*diff\\s",
    "^\\s*bash\\s", "^\\s*sh\\s", "^\\s*source\\s", "^\\s*\\.\\s",
    "^\\s*exec\\s", "^\\s*env\\s",
    "^(?:\\s*\\w+=\\S*\\s+)*(?:bash|sh|python3?|node)\\s",
    "^\\s*\\.claude\\.workflow/hooks/.*\\.sh\\b", "^\\s*/.*/\\.claude/hooks/.*\\.sh\\b",
    "^\\s*less\\s", "^\\s*more\\s", "^\\s*find\\s", "^\\s*tree\\b",
    "^\\s*realpath\\s", "^\\s*readlink\\s", "^\\s*sha256sum\\s",
    "^\\s*md5sum\\s", "^\\s*test\\s", "^\\s*\\[\\s",
]

# =============================================================================
# Hooks Self-Protection Guard: Fixed command pattern
# =============================================================================
GUARD_MODIFY_PATTERNS = [
    "sed\\s+.*-i", "sed\\s+-i", "\\bcp\\b", "\\bmv\\b",
    "echo\\s.*>\\s*", "echo\\s.*>>\\s*", "printf\\s.*>\\s*", "printf\\s.*>>\\s*",
    "\\btee\\b", "cat\\s.*>\\s*", "cat\\s.*>>\\s*",
    "\\bdd\\b", "\\binstall\\b", "\\brsync\\b", "\\bchmod\\b", "\\bchown\\b",
    "ln\\s+-sf?\\b", "rm\\s+-rf?\\b", "rm\\s+-f\\b",
    "\\btouch\\b", "\\bmkdir\\b", "\\brmdir\\b", ">\\s*\\S", ">>\\s*\\S",
]

# =============================================================================
# Hooks Self Protection Guard: Protection Path Pattern
# =============================================================================
GUARD_PROTECTED_PATH_PATTERNS = [
    "\\.agent-factory/hooks/",
    "\\.agent-factory/runs/bypass",
]

# =============================================================================
# Hooks Self-Protection Guard: Inline Writing Pattern
# =============================================================================
GUARD_INLINE_WRITE_PATTERNS = [
    "open\\s*\\(", "write\\s*\\(", "writeFile", "writeFileSync",
    "appendFile", "appendFileSync", ">\\s*",
]
