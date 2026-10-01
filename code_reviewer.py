"""
Code Review Agent

An agent that analyzes code and provides feedback on quality, bugs, and improvements.
Demonstrates how agents can evaluate and critique code.

Reviews are saved to ``code_reviews/`` as Markdown so you can refer back to
them or share them with teammates.

Prerequisites:
    pip install -r requirements.txt

Learning objectives:
- Understand automated code review patterns
- See how agents identify bugs and security issues
- Practice giving an agent tools so it can introspect a workspace
- See how to persist agent output as durable artifacts
"""

import re
import time
from datetime import datetime
from pathlib import Path
from shared.model import get_model
from shared.input_utils import get_multiline_input
from shared.streaming import StreamingCallbackHandler
from strands import Agent, tool


# Where code_generator.py writes its output. The tools below give the agent
# read-only access to this folder so it can fetch a script when the user
# asks about it by name.
GENERATED_DIR = Path(__file__).parent / "generated_code"

# Where this agent writes its reviews. Each turn produces one file.
REVIEWS_DIR = Path(__file__).parent / "code_reviews"

_SAFE_NAME = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]*\.py$")

# The most recent source we reviewed this turn — used to name the output
# Markdown file. Set by ``read_generated_script`` and by the 'example'
# command in the main loop. Cleared at the start of every turn.
_current_target: str | None = None


@tool
def list_generated_scripts() -> str:
    """List the Python scripts available in the workspace's generated_code folder.

    Use this when the user asks what scripts are available or which file to
    look at. Returns a newline-separated list of filenames, or a message
    explaining that the folder is empty.
    """
    print("          list_generated_scripts()")
    if not GENERATED_DIR.exists():
        out = "(generated_code/ does not exist yet — the user needs to run code_generator.py first)"
    else:
        names = sorted(p.name for p in GENERATED_DIR.glob("*.py"))
        out = "\n".join(names) if names else "(generated_code/ is empty)"
    print(f"          -> {out!r}")
    return out


@tool
def read_generated_script(name: str) -> str:
    """Read a Python script from the workspace's generated_code folder.

    Use this when the user mentions a script by name (with or without the
    .py suffix). Returns the source code, or an error message if the file
    isn't there.

    Args:
        name: The script's filename.
    """
    global _current_target
    print(f"          read_generated_script(name={name!r})")
    target = name if name.endswith(".py") else name + ".py"
    if not _SAFE_NAME.match(target):
        out = f"Error: unsafe filename {name!r}"
    else:
        path = GENERATED_DIR / target
        if not path.exists():
            available = sorted(p.name for p in GENERATED_DIR.glob("*.py")) if GENERATED_DIR.exists() else []
            if available:
                out = f"Error: {target} not found. Available: {', '.join(available)}"
            else:
                out = f"Error: {target} not found and generated_code/ is empty."
        else:
            out = path.read_text()
            _current_target = target[:-3]  # strip .py
    preview = out[:80].replace("\n", " ")
    print(f"          -> {len(out)} chars: {preview}...")
    return out


SYSTEM_PROMPT = """You are a code review assistant.

When the user mentions a script by name, or asks what scripts are
available, use your tools:
- list_generated_scripts(): see what's in the workspace folder.
- read_generated_script(name): fetch a script's source code.

When reviewing code:
1. Check for bugs and logic errors
2. Identify security vulnerabilities (SQL injection, XSS, etc.)
3. Suggest performance improvements
4. Evaluate readability and maintainability
5. Check for best practices and design patterns
6. Look for missing error handling

Provide specific, actionable feedback with line references when possible.
Be constructive—explain WHY something is an issue and HOW to fix it.

Format your review as Markdown with these sections:
- **Critical Issues**: Bugs or security problems that must be fixed
- **Improvements**: Suggestions for better code quality
- **Style**: Minor formatting or naming suggestions"""


# Streaming handler prints tokens as the review emerges. Pass callback_handler=None to suppress.
stream_handler = StreamingCallbackHandler()

agent = Agent(
    model=get_model(),
    system_prompt=SYSTEM_PROMPT,
    tools=[list_generated_scripts, read_generated_script],
    callback_handler=stream_handler,
)


# Sample buggy code lives in examples/ so it can be edited without touching the agent.
EXAMPLE_PATH = Path(__file__).parent / "examples" / "buggy_code.py"


def _next_review_path(stem: str) -> Path:
    """Return ``code_reviews/<stem>_review.md``, auto-suffixed if needed."""
    REVIEWS_DIR.mkdir(exist_ok=True)
    base = f"{stem}_review.md"
    candidate = REVIEWS_DIR / base
    if not candidate.exists():
        return candidate
    for i in range(2, 1000):
        candidate = REVIEWS_DIR / f"{stem}_review_{i}.md"
        if not candidate.exists():
            return candidate
    return REVIEWS_DIR / f"{stem}_review_overflow.md"


def _save_review(prompt: str, response_text: str) -> None:
    """Persist the review to ``code_reviews/`` as a Markdown file."""
    if not response_text.strip():
        return

    # Pick the filename stem based on what we just reviewed. _current_target
    # is set by the example branch and by read_generated_script. If neither
    # fired, the user pasted code, so fall back to a timestamped name.
    stem = _current_target or f"paste_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    path = _next_review_path(stem)
    header = (
        f"# Code review\n\n"
        f"_Generated at {datetime.now().isoformat(timespec='seconds')}_\n\n"
        f"---\n\n"
    )
    path.write_text(header + response_text.rstrip() + "\n")
    print(f"  [saved] {path.relative_to(path.parent.parent)}")


def main():
    """Run the code reviewer interactively."""
    global _current_target

    print("Code Review Agent")
    print("=" * 40)
    print("Talk to me in plain English. I can:")
    print("  - review code you paste directly")
    print("  - list and review scripts saved in generated_code/")
    print("  - review the buggy sample (type 'example')")
    print(f"Reviews are saved as Markdown in {REVIEWS_DIR.name}/.")
    print("Type 'quit' to exit\n")
    print("Tip: You can paste multi-line code!\n")

    while True:
        user_input = get_multiline_input("You: ").strip()

        if user_input.lower() in ["quit", "exit", "q"]:
            print("Goodbye!")
            break

        if not user_input:
            continue

        # Reset per-turn state — _current_target may be set later by either
        # the 'example' branch or the read_generated_script tool.
        _current_target = None

        if user_input.lower() == "example":
            example_code = EXAMPLE_PATH.read_text().strip()
            print(f"\nReviewing example code from examples/{EXAMPLE_PATH.name}:")
            print(f"```python\n{example_code}\n```\n")
            _current_target = EXAMPLE_PATH.stem  # e.g. 'buggy_code'
            prompt = f"Review this Python code:\n```python\n{example_code}\n```"
        else:
            prompt = user_input

        stream_handler.reset()
        print("\nAgent: ", end="", flush=True)
        start_time = time.time()
        response = agent(prompt)
        elapsed = time.time() - start_time

        _save_review(prompt, str(response))
        print(f"  ({elapsed:.1f}s)\n")


if __name__ == "__main__":
    main()
