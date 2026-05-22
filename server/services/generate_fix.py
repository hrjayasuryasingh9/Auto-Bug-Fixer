import json
from server.utils.ai import get_client
from server.utils.logger import logger

WINDOW = 40  # lines before and after the error line

SYSTEM_PROMPT = """You are an expert frontend debugging AI.

Your task:
1. Analyze the error
2. Understand root cause
3. Fix the issue safely
4. Avoid breaking existing functionality
5. Add defensive handling where required
6. Return ONLY the updated code snippet — nothing else

Do not:
- Refactor unrelated code
- Change formatting unnecessarily
- Remove existing functionality
- Add explanations or markdown"""


def extract_window(file_content: str, line_number: int) -> tuple[str, int, int]:
    """Return (snippet, start_line, end_line) — 1-indexed, inclusive."""
    lines = file_content.splitlines()
    total = len(lines)
    idx = max(0, line_number - 1)          # convert to 0-indexed
    start = max(0, idx - WINDOW)
    end = min(total - 1, idx + WINDOW)
    snippet = "\n".join(lines[start : end + 1])
    return snippet, start + 1, end + 1     # back to 1-indexed


def apply_window(file_content: str, fixed_snippet: str, start_line: int, end_line: int) -> str:
    """Splice fixed_snippet back into file_content at [start_line, end_line] (1-indexed)."""
    lines = file_content.splitlines()
    fixed_lines = fixed_snippet.splitlines()
    result = lines[: start_line - 1] + fixed_lines + lines[end_line:]
    return "\n".join(result)


async def generate_fix(
    error_data: dict,
    file_content: str,
    file_path: str,
    api_key: str,
) -> str:
    logger.info(f"[ai] Generating fix for {file_path}")

    line_number = error_data.get("line_number")
    use_window = line_number is not None

    if use_window:
        snippet, start_line, end_line = extract_window(file_content, line_number)
        total_lines = len(file_content.splitlines())
        logger.info(
            f"[ai] Sending window lines {start_line}–{end_line} "
            f"({end_line - start_line + 1} of {total_lines} lines)"
        )
        code_context = (
            f"FILE: {file_path}\n"
            f"SHOWING LINES {start_line}–{end_line} (error at line {line_number}):\n\n"
            f"{snippet}"
        )
        rules_extra = "- Return only the fixed version of the provided snippet, not the full file"
    else:
        snippet = file_content
        start_line = end_line = None
        code_context = f"FILE: {file_path}\n\n{file_content}"
        rules_extra = "- Return the full updated file"

    # Send only the fields that help Claude — drop heavy/irrelevant fields
    lean_error = {
        k: error_data[k]
        for k in ("message", "stack", "line_number", "column_number", "url")
        if k in error_data
    }

    prompt = f"""Fix the following frontend runtime error safely.

ERROR:
{json.dumps(lean_error, indent=2)}

CODE:
{code_context}

RULES:
- {rules_extra}
- Do not break existing functionality
- Add fallback/optional chaining where needed
- Avoid syntax errors"""

    client = get_client(api_key)
    message = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    fixed_snippet: str = message.content[0].text
    logger.info(
        f"[ai] Fix received — "
        f"input: {message.usage.input_tokens} tokens, "
        f"output: {message.usage.output_tokens} tokens"
    )

    if use_window and start_line is not None and end_line is not None:
        return apply_window(file_content, fixed_snippet, start_line, end_line)

    return fixed_snippet
