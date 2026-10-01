"""
Code Generator Agent

An agent that generates code from natural language descriptions and saves
each result to ``generated_code/<name>.py``. The other lab 5 agents
(reviewer, refactor, test) can then ``pull <name>`` to operate on what
this agent produced.

Prerequisites:
    pip install -r requirements.txt

Learning objectives:
- Understand code generation from natural language
- See how a structured response contract enables programmatic post-processing
- Practice persisting agent output so downstream agents can consume it
"""

import re
import time
from pathlib import Path
from shared.model import get_model
from shared.input_utils import get_multiline_input
from shared.streaming import StreamingCallbackHandler
from strands import Agent


# Generated files land here so the reviewer / refactor / test agents can
# pull them later by script name.
GENERATED_DIR = Path(__file__).parent / "generated_code"

# Allowlist of safe filename characters: starts with a letter, only
# letters/digits/underscores, ends in .py. Rejects path traversal.
_SAFE_NAME = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]*\.py$")


def _is_safe_filename(name: str) -> bool:
    return bool(_SAFE_NAME.match(name))


def _parse_response(text: str) -> tuple[str | None, str | None]:
    """Extract `FILENAME: foo.py` and the first python code block."""
    filename = None
    m = re.search(r"^\s*FILENAME:\s*([^\s`]+)", text, re.MULTILINE)
    if m and _is_safe_filename(m.group(1).strip()):
        filename = m.group(1).strip()

    code = None
    block = re.search(r"```(?:python|py)?\s*\n(.*?)```", text, re.DOTALL)
    if block:
        code = block.group(1).rstrip() + "\n"

    return filename, code


def _next_fallback_name() -> str:
    """Return ``generated_NNN.py`` when the agent didn't give us a usable name."""
    existing = {p.name for p in GENERATED_DIR.glob("generated_*.py")} if GENERATED_DIR.exists() else set()
    for i in range(1, 1000):
        candidate = f"generated_{i:03d}.py"
        if candidate not in existing:
            return candidate
    return "generated_overflow.py"


SYSTEM_PROMPT = """You are a code generation assistant.

When asked to write code, follow this response contract exactly so your
output can be saved as a runnable file:

1. The very first line of your response MUST be:
       FILENAME: <snake_case_name>.py
   The filename must start with a letter, contain only letters, digits,
   and underscores, and end in `.py`. Pick a name that reflects what the
   code does (e.g. `prime_finder.py`, `shopping_cart.py`).

2. Then a short explanation of your approach (1-3 sentences).

3. Then EXACTLY ONE fenced code block tagged with ```python ... ```
   containing the complete, working Python implementation. Include a
   small `if __name__ == "__main__":` demo at the bottom when it makes
   sense, so the file is immediately runnable.

4. After the code block, you may add a brief note about caveats or how
   to extend the code.

Write clean, well-documented code with appropriate error handling. Use
Python 3.10+ syntax (type hints encouraged)."""


# Streaming handler prints tokens as the model generates them so you can watch
# the code emerge live. Pass callback_handler=None to suppress.
stream_handler = StreamingCallbackHandler()

agent = Agent(
    model=get_model(),
    system_prompt=SYSTEM_PROMPT,
    callback_handler=stream_handler,
)


def _save_response(response_text: str) -> None:
    """Parse the agent's reply, save the code, and print a confirmation."""
    filename, code = _parse_response(response_text)

    if code is None:
        print("  [save] no python code block found in response — nothing saved.")
        return

    if filename is None:
        filename = _next_fallback_name()
        print(f"  [save] no FILENAME header found — using {filename}")

    GENERATED_DIR.mkdir(exist_ok=True)
    path = GENERATED_DIR / filename
    path.write_text(code)
    print(f"  [saved] {path.relative_to(path.parent.parent)}")


def main():
    """Run the code generator interactively."""
    print("Code Generator Agent")
    print("=" * 40)
    print(f"Generated files are written to: {GENERATED_DIR.name}/")
    print("Describe what code you want to generate.")
    print("Type 'quit' to exit\n")

    print("Example prompts to try:")
    print("  - Write a function that finds all prime numbers up to n")
    print("  - Create a class for a simple shopping cart with add, remove, and total")
    print("  - Write a function to validate email addresses using regex")
    print("  - Create a binary search function with type hints")
    print("\nTip: You can paste multi-line prompts!\n")

    while True:
        user_input = get_multiline_input("You: ").strip()

        if user_input.lower() in ["quit", "exit", "q"]:
            print("Goodbye!")
            break

        if not user_input:
            continue

        stream_handler.reset()
        print("\nAgent: ", end="", flush=True)
        start_time = time.time()
        response = agent(user_input)
        elapsed = time.time() - start_time

        # The streamed text is also returned as the AgentResult. Parse it
        # for the FILENAME header + code block and save to generated_code/.
        _save_response(str(response))
        print(f"  ({elapsed:.1f}s)\n")


if __name__ == "__main__":
    main()
