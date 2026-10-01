"""
Interactive Coding Assistant

A multi-purpose coding agent that combines generation, review, refactor,
explanation, and testing. Has read-only access to the same workspace
folders the specialized agents use, and (when strands-agents-tools is
installed) general read/write file tools for everything else.

Prerequisites:
    pip install -r requirements.txt

Learning objectives:
- Understand multi-capability coding agents
- See how scoped tools enable workspace awareness without giving the agent the keys to the filesystem
- Practice combining narrow workspace tools with general-purpose file tools
"""

import re
import time
from pathlib import Path
from shared.model import get_model
from shared.input_utils import get_multiline_input
from shared.streaming import StreamingCallbackHandler
from strands import Agent, tool

# Optional general-purpose file tools. The workspace tools above work
# regardless; these add unrestricted read/write when strands-agents-tools is
# installed.
#
# strands-agents-tools 0.8.x exposes each tool as a submodule (file_read,
# file_write) and Strands' Agent expects the *module* to be passed as the
# tool — the module carries the TOOL_SPEC constant. Older 0.4–0.7 versions
# exposed top-level functions named read_file / write_file instead. We try
# the new shape first and fall back to the old, so this lab works on either.
file_read = file_write = None
try:
    from strands_tools import file_read, file_write  # >=0.8: import modules
    HAS_FILE_TOOLS = True
except ImportError:
    try:
        from strands_tools import read_file as file_read  # <=0.7: top-level fns
        from strands_tools import write_file as file_write
        HAS_FILE_TOOLS = True
    except ModuleNotFoundError:
        # Package isn't installed at all.
        HAS_FILE_TOOLS = False
        print("Note: strands-agents-tools not installed. General file operations disabled.")
        print("Run: pip install -r requirements.txt\n")
    except ImportError as e:
        HAS_FILE_TOOLS = False
        print(f"Note: general file tools unavailable in strands_tools ({e}).")
        print("Try: pip install -r requirements.txt\n")


# Workspace folders the other lab 5 agents use. The tools below give this
# assistant the same read access so it can reason across the workspace.
GENERATED_DIR = Path(__file__).parent / "generated_code"
REVIEWS_DIR = Path(__file__).parent / "code_reviews"
REFACTORED_DIR = Path(__file__).parent / "refactored_code"
TESTS_DIR = Path(__file__).parent / "generated_tests"

_SAFE_PY = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]*\.py$")
_SAFE_MD = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]*\.md$")


# --- generated_code/ tools ---

@tool
def list_generated_scripts() -> str:
    """List the Python scripts available in the workspace's generated_code folder."""
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

    Args:
        name: The script's filename.
    """
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
    preview = out[:80].replace("\n", " ")
    print(f"          -> {len(out)} chars: {preview}...")
    return out


# --- code_reviews/ tools ---

@tool
def list_code_reviews() -> str:
    """List the saved review reports available in the workspace's code_reviews folder."""
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

    Accepts the bare script name, the review base, or the full filename.

    Args:
        name: The review's filename or a script stem.
    """
    print(f"          read_code_review(name={name!r})")
    if not REVIEWS_DIR.exists():
        out = "Error: code_reviews/ does not exist yet — run code_reviewer.py first."
        print(f"          -> {out!r}")
        return out

    available = sorted(p.name for p in REVIEWS_DIR.glob("*.md"))
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


# --- refactored_code/ tools ---

@tool
def list_refactored_scripts() -> str:
    """List the refactored scripts available in the workspace's refactored_code folder."""
    print("          list_refactored_scripts()")
    if not REFACTORED_DIR.exists():
        out = "(refactored_code/ does not exist yet — the user needs to run refactor_agent.py first)"
    else:
        names = sorted(p.name for p in REFACTORED_DIR.glob("*.py"))
        out = "\n".join(names) if names else "(refactored_code/ is empty)"
    print(f"          -> {out!r}")
    return out


@tool
def read_refactored_script(name: str) -> str:
    """Read a refactored Python script from the workspace's refactored_code folder.

    Accepts the bare script name, the refactored base, or the full filename.

    Args:
        name: The script's filename or a script stem.
    """
    print(f"          read_refactored_script(name={name!r})")
    if not REFACTORED_DIR.exists():
        out = "Error: refactored_code/ does not exist yet — run refactor_agent.py first."
        print(f"          -> {out!r}")
        return out

    available = sorted(p.name for p in REFACTORED_DIR.glob("*.py"))
    candidates = []
    if name.endswith(".py"):
        candidates.append(name)
    else:
        candidates.extend([f"{name}.py", f"{name}_refactored.py"])

    target = next((c for c in candidates if _SAFE_PY.match(c) and (REFACTORED_DIR / c).exists()), None)
    if target is None:
        if available:
            out = f"Error: no refactored script found for {name!r}. Available: {', '.join(available)}"
        else:
            out = "Error: refactored_code/ is empty."
        print(f"          -> {out!r}")
        return out

    out = (REFACTORED_DIR / target).read_text()
    preview = out[:80].replace("\n", " ")
    print(f"          -> {len(out)} chars: {preview}...")
    return out


# --- generated_tests/ tools ---

@tool
def list_generated_tests() -> str:
    """List the test files available in the workspace's generated_tests folder."""
    print("          list_generated_tests()")
    if not TESTS_DIR.exists():
        out = "(generated_tests/ does not exist yet — the user needs to run test_generator.py first)"
    else:
        names = sorted(p.name for p in TESTS_DIR.glob("*.py"))
        out = "\n".join(names) if names else "(generated_tests/ is empty)"
    print(f"          -> {out!r}")
    return out


@tool
def read_generated_test(name: str) -> str:
    """Read a test file from the workspace's generated_tests folder.

    Accepts the bare script name, the ``test_<stem>`` base, or the full filename.

    Args:
        name: The test file's filename or the source stem.
    """
    print(f"          read_generated_test(name={name!r})")
    if not TESTS_DIR.exists():
        out = "Error: generated_tests/ does not exist yet — run test_generator.py first."
        print(f"          -> {out!r}")
        return out

    available = sorted(p.name for p in TESTS_DIR.glob("*.py"))
    candidates = []
    if name.endswith(".py"):
        candidates.append(name)
    else:
        candidates.extend([f"{name}.py", f"test_{name}.py"])

    target = next((c for c in candidates if _SAFE_PY.match(c) and (TESTS_DIR / c).exists()), None)
    if target is None:
        if available:
            out = f"Error: no test file found for {name!r}. Available: {', '.join(available)}"
        else:
            out = "Error: generated_tests/ is empty."
        print(f"          -> {out!r}")
        return out

    out = (TESTS_DIR / target).read_text()
    preview = out[:80].replace("\n", " ")
    print(f"          -> {len(out)} chars: {preview}...")
    return out


# --- save tools ---
#
# Each save tool enforces its own safe-filename rules and auto-suffixes on
# collision so we never silently overwrite an existing artifact.

def _save_with_collision_suffix(folder: Path, filename: str, content: str) -> Path:
    """Write content to ``folder/filename``, auto-suffixing if a file already exists."""
    folder.mkdir(exist_ok=True)
    target = folder / filename
    if not target.exists():
        target.write_text(content)
        return target
    stem = target.stem
    ext = target.suffix
    for i in range(2, 1000):
        candidate = folder / f"{stem}_{i}{ext}"
        if not candidate.exists():
            candidate.write_text(content)
            return candidate
    overflow = folder / f"{stem}_overflow{ext}"
    overflow.write_text(content)
    return overflow


@tool
def save_to_generated(filename: str, code: str) -> str:
    """Save Python source to the workspace's generated_code/ folder.

    Use this when you've written *new* code from scratch (the Code Generator's
    domain). The filename should be a snake_case Python module ending in .py
    (e.g. ``prime_finder.py``). If a file with this name already exists, a
    numeric suffix is added so nothing gets overwritten.

    Args:
        filename: Snake_case filename ending in ``.py``.
        code: The full Python source to write.
    """
    print(f"          save_to_generated(filename={filename!r}, {len(code)} chars)")
    if not _SAFE_PY.match(filename):
        out = f"Error: unsafe filename {filename!r}. Use snake_case ending in .py."
        print(f"          -> {out}")
        return out
    path = _save_with_collision_suffix(GENERATED_DIR, filename, code)
    rel = path.relative_to(path.parent.parent)
    print(f"  [saved] {rel}")
    return f"Saved to {rel}"


@tool
def save_to_reviews(filename: str, markdown: str) -> str:
    """Save a Markdown review report to the workspace's code_reviews/ folder.

    Use this for code reviews, debugging analyses, explanations, or any
    report-style prose output (the Code Reviewer's domain). The filename
    should be snake_case ending in .md (e.g. ``prime_finder_review.md``).
    If a file with this name already exists, a numeric suffix is added.

    Args:
        filename: Snake_case filename ending in ``.md``.
        markdown: The Markdown content to save.
    """
    print(f"          save_to_reviews(filename={filename!r}, {len(markdown)} chars)")
    if not _SAFE_MD.match(filename):
        out = f"Error: unsafe filename {filename!r}. Use snake_case ending in .md."
        print(f"          -> {out}")
        return out
    path = _save_with_collision_suffix(REVIEWS_DIR, filename, markdown)
    rel = path.relative_to(path.parent.parent)
    print(f"  [saved] {rel}")
    return f"Saved to {rel}"


@tool
def save_to_refactored(filename: str, code: str) -> str:
    """Save refactored Python source to the workspace's refactored_code/ folder.

    Use this when you've improved or rewritten existing code (the Refactor
    agent's domain). The filename should be snake_case ending in .py, and
    by convention includes ``_refactored`` (e.g. ``prime_finder_refactored.py``).
    If a file with this name already exists, a numeric suffix is added.

    Args:
        filename: Snake_case filename ending in ``.py``.
        code: The full refactored Python source to write.
    """
    print(f"          save_to_refactored(filename={filename!r}, {len(code)} chars)")
    if not _SAFE_PY.match(filename):
        out = f"Error: unsafe filename {filename!r}. Use snake_case ending in .py."
        print(f"          -> {out}")
        return out
    path = _save_with_collision_suffix(REFACTORED_DIR, filename, code)
    rel = path.relative_to(path.parent.parent)
    print(f"  [saved] {rel}")
    return f"Saved to {rel}"


@tool
def save_to_tests(filename: str, code: str) -> str:
    """Save a pytest test module to the workspace's generated_tests/ folder.

    Use this when you've written tests for existing code (the Test Generator
    agent's domain). The filename should be snake_case ending in .py, and
    by pytest convention starts with ``test_`` (e.g.
    ``test_prime_finder.py``). If a file with this name already exists, a
    numeric suffix is added.

    Args:
        filename: Snake_case filename ending in ``.py``, normally starting with ``test_``.
        code: The full Python source to write.
    """
    print(f"          save_to_tests(filename={filename!r}, {len(code)} chars)")
    if not _SAFE_PY.match(filename):
        out = f"Error: unsafe filename {filename!r}. Use snake_case ending in .py."
        print(f"          -> {out}")
        return out
    path = _save_with_collision_suffix(TESTS_DIR, filename, code)
    rel = path.relative_to(path.parent.parent)
    print(f"  [saved] {rel}")
    return f"Saved to {rel}"


SYSTEM_PROMPT = """You are an expert coding assistant.

You can help with:
- **Generate**: Write new code from descriptions
- **Review**: Analyze code for bugs, security issues, and improvements
- **Refactor**: Improve code structure while preserving behavior
- **Explain**: Describe how code works in plain language
- **Debug**: Help identify and fix issues
- **Test**: Generate test cases for code

You share a workspace with four specialist agents. Each owns a folder:
- `generated_code/` — Python scripts produced by the Code Generator agent.
- `code_reviews/` — Markdown review reports produced by the Code Review agent.
- `refactored_code/` — refactored Python scripts produced by the Refactoring agent.
- `generated_tests/` — pytest test files produced by the Test Generator agent.

Read tools (use when the user mentions a script, review, refactored
version, or test by name — fetch it instead of asking them to paste it):
- list_generated_scripts() / read_generated_script(name)
- list_code_reviews() / read_code_review(name)
- list_refactored_scripts() / read_refactored_script(name)
- list_generated_tests() / read_generated_test(name)

Save tools (use by default whenever your reply produces something durable,
unless the user explicitly says not to save):
- save_to_generated(filename, code): new code you wrote from scratch.
  Filename: snake_case .py, named after what the code does
  (e.g. ``prime_finder.py``).
- save_to_reviews(filename, markdown): a review, debugging analysis, or
  explanation report. Filename: snake_case .md, usually
  ``<subject>_review.md`` (e.g. ``prime_finder_review.md``).
- save_to_refactored(filename, code): an improved or rewritten version
  of existing code. Filename: snake_case .py, by convention
  ``<original>_refactored.py``.
- save_to_tests(filename, code): pytest tests for existing code.
  Filename: snake_case .py, by pytest convention
  ``test_<subject>.py`` (e.g. ``test_prime_finder.py``).

A single turn can save to multiple folders if it makes sense — e.g. if
you generate a script *and* tests for it, save the code with
save_to_generated and the tests with save_to_tests. Don't save trivial
throwaway snippets or one-line answers.

If the user wants you to write to a specific path outside these folders,
use the general file_read / file_write tools when available.

Always:
- Explain your reasoning
- Provide working, tested solutions
- Ask clarifying questions if requirements are unclear
- Suggest best practices and improvements"""


# Streaming handler prints tokens live and announces each tool call.
# Pass callback_handler=None to suppress.
stream_handler = StreamingCallbackHandler()


def create_agent():
    """Create the coding assistant with the workspace tools (plus optional file tools)."""
    tools = [
        list_generated_scripts,
        read_generated_script,
        list_code_reviews,
        read_code_review,
        list_refactored_scripts,
        read_refactored_script,
        list_generated_tests,
        read_generated_test,
        save_to_generated,
        save_to_reviews,
        save_to_refactored,
        save_to_tests,
    ]
    if HAS_FILE_TOOLS:
        tools.extend([file_read, file_write])

    return Agent(
        model=get_model(),
        system_prompt=SYSTEM_PROMPT,
        tools=tools,
        callback_handler=stream_handler,
    )


def main():
    """Run the interactive coding assistant."""
    print("Interactive Coding Assistant")
    print("=" * 40)
    print("I can help you write, review, refactor, explain, and debug code.")
    print("By default I'll save what I produce to the right folder. Tell me")
    print("'don't save' if you only want the inline output.")
    if HAS_FILE_TOOLS:
        print("General file tools are also available — I can read and write")
        print("arbitrary paths when asked.")
    print("Type 'quit' to exit\n")

    print("Tip: You can paste multi-line code!\n")

    agent = create_agent()

    while True:
        user_input = get_multiline_input("You: ").strip()

        if user_input.lower() in ["quit", "exit", "q"]:
            print("Goodbye!")
            break

        if not user_input:
            continue

        try:
            stream_handler.reset()
            print("\nAgent: ", end="", flush=True)
            start_time = time.time()
            agent(user_input)
            elapsed = time.time() - start_time
            print(f"\n({elapsed:.1f}s)\n")
        except Exception as e:
            print(f"\nError: {e}\n")


if __name__ == "__main__":
    main()
