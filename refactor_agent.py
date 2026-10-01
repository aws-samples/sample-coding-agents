"""
Refactoring Agent

An agent that improves existing code while preserving functionality.
Demonstrates code transformation and improvement patterns.

Prerequisites:
    pip install -r requirements.txt

Learning objectives:
- Understand automated refactoring patterns
- See how agents preserve behavior while improving structure
- Practice giving an agent tools so it can introspect a workspace
"""

import re
import time
from datetime import datetime
from pathlib import Path
from shared.model import get_model
from shared.input_utils import get_multiline_input
from shared.streaming import StreamingCallbackHandler
from strands import Agent, tool


# Where code_generator.py writes its output and code_reviewer.py writes its
# review reports. The tools below give the agent read-only access to both
# folders so it can fetch a script (and any prior review) by name.
GENERATED_DIR = Path(__file__).parent / "generated_code"
REVIEWS_DIR = Path(__file__).parent / "code_reviews"

# Where this agent writes the refactored code it produces. Each turn that
# yields a Python code block lands one file here.
REFACTORED_DIR = Path(__file__).parent / "refactored_code"

_SAFE_PY = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]*\.py$")
_SAFE_MD = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]*\.md$")

# The most recent source we refactored this turn — used to name the output
# file. Set by the example branch and by ``read_generated_script``.
# Cleared at the start of every turn.
_current_target: str | None = None


@tool
def list_generated_scripts() -> str:
    """List the Python scripts available in the workspace's generated_code folder.

    Use this when the user asks what scripts are available or which file to
    refactor. Returns a newline-separated list of filenames, or a message
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
    if not _SAFE_PY.match(target):
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


@tool
def list_code_reviews() -> str:
    """List the saved review reports available in the workspace's code_reviews folder.

    Use this when the user asks what reviews exist, or before reading a
    review by name. Returns a newline-separated list of review filenames,
    or a message explaining that the folder is empty.
    """
    print("          list_code_reviews()")
    if not REVIEWS_DIR.exists():
        out = "(code_reviews/ does not exist yet — the user needs to run code_reviewer.py first)"
    else:
        names = sorted(p.name for p in REVIEWS_DIR.glob("*.md"))
        out = "\n".join(names) if names else "(code_reviews/ is empty)"
    print(f"          -> {out!r}")
    return out


@tool
def read_code_review(name: str) -> str:
    """Read a saved review report from the workspace's code_reviews folder.

    Use this when the user mentions a prior review or asks you to take a
    review into account during the refactor. Accepts the bare script name, the review base, or
    the full filename.

    Args:
        name: The review's filename or a script stem.
    """
    print(f"          read_code_review(name={name!r})")
    if not REVIEWS_DIR.exists():
        out = "Error: code_reviews/ does not exist yet — run code_reviewer.py first."
        print(f"          -> {out!r}")
        return out

    available = sorted(p.name for p in REVIEWS_DIR.glob("*.md"))
    # Resolve the name: try exact, then with _review.md appended.
    candidates = []
    if name.endswith(".md"):
        candidates.append(name)
    else:
        candidates.extend([f"{name}.md", f"{name}_review.md"])

    target = next((c for c in candidates if _SAFE_MD.match(c) and (REVIEWS_DIR / c).exists()), None)
    if target is None:
        if available:
            out = f"Error: no review found for {name!r}. Available: {', '.join(available)}"
        else:
            out = "Error: code_reviews/ is empty."
        print(f"          -> {out!r}")
        return out

    out = (REVIEWS_DIR / target).read_text()
    preview = out[:80].replace("\n", " ")
    print(f"          -> {len(out)} chars: {preview}...")
    return out


SYSTEM_PROMPT = """You are a code refactoring assistant.

When the user mentions a script by name, or asks what scripts are
available, use your tools to read the workspace:
- list_generated_scripts(): see what's in the generated_code/ folder.
- read_generated_script(name): fetch a script's source code.

A separate Code Review agent writes its findings to a `code_reviews/`
folder. If the user mentions a review, or you think a recent review would
sharpen the refactor, look it up first:
- list_code_reviews(): see what reviews exist.
- read_code_review(name): read a review report.

When refactoring code:
1. PRESERVE the original functionality exactly
2. Improve readability and maintainability
3. Apply SOLID principles where appropriate
4. Extract reusable functions/methods
5. Add type hints (Python) or types (TypeScript/Java)
6. Improve variable and function naming
7. Remove code duplication
8. Simplify complex conditionals

Always:
- Show the refactored code
- Explain what changes you made and why
- Note any assumptions about the original behavior"""


# Streaming handler prints tokens as the refactor takes shape. Pass callback_handler=None to suppress.
stream_handler = StreamingCallbackHandler()

agent = Agent(
    model=get_model(),
    system_prompt=SYSTEM_PROMPT,
    tools=[list_generated_scripts, read_generated_script, list_code_reviews, read_code_review],
    callback_handler=stream_handler,
)


# Sample messy code lives in examples/ so it can be edited without touching the agent.
EXAMPLE_PATH = Path(__file__).parent / "examples" / "messy_code.py"


def _next_refactor_path(stem: str) -> Path:
    """Return ``refactored_code/<stem>_refactored.py``, auto-suffixed if needed."""
    REFACTORED_DIR.mkdir(exist_ok=True)
    base = f"{stem}_refactored.py"
    candidate = REFACTORED_DIR / base
    if not candidate.exists():
        return candidate
    for i in range(2, 1000):
        candidate = REFACTORED_DIR / f"{stem}_refactored_{i}.py"
        if not candidate.exists():
            return candidate
    return REFACTORED_DIR / f"{stem}_refactored_overflow.py"


def _save_refactor(response_text: str) -> None:
    """Pull the first python code block out of the agent's reply and save it."""
    block = re.search(r"```(?:python|py)?\s*\n(.*?)```", response_text, re.DOTALL)
    if not block:
        # The agent might have only explained itself without producing code
        # (e.g. when listing what's available). Nothing to save then.
        return
    code = block.group(1).rstrip() + "\n"

    # Pick the filename stem based on what we just refactored. If neither
    # the example branch nor read_generated_script fired, the user pasted
    # code, so fall back to a timestamped name.
    stem = _current_target or f"paste_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    path = _next_refactor_path(stem)
    path.write_text(code)
    print(f"  [saved] {path.relative_to(path.parent.parent)}")


def main():
    """Run the refactoring agent interactively."""
    global _current_target

    print("Refactoring Agent")
    print("=" * 40)
    print("Talk to me in plain English. I can:")
    print("  - refactor code you paste directly")
    print("  - list and refactor scripts saved in generated_code/")
    print("  - take a saved review from code_reviews/ into account")
    print("  - refactor the messy sample (type 'example')")
    print(f"Refactored code is saved in {REFACTORED_DIR.name}/.")
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
            print(f"\nRefactoring example code from examples/{EXAMPLE_PATH.name}:")
            print(f"```python\n{example_code}\n```\n")
            _current_target = EXAMPLE_PATH.stem  # e.g. 'messy_code'
            prompt = (
                "Refactor this Python code for better readability and "
                f"maintainability:\n```python\n{example_code}\n```"
            )
        else:
            prompt = user_input

        stream_handler.reset()
        print("\nAgent: ", end="", flush=True)
        start_time = time.time()
        response = agent(prompt)
        elapsed = time.time() - start_time

        _save_refactor(str(response))
        print(f"  ({elapsed:.1f}s)\n")


if __name__ == "__main__":
    main()
