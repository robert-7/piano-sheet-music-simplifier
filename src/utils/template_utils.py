from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment
from jinja2 import FileSystemLoader
from jinja2 import StrictUndefined

def _env_for(base_dir: Path) -> Environment:
    """
    Returns a Jinja2 environment configured to load templates from base_dir.
    Uses StrictUndefined to fail fast on missing variables.
    """
    loader = FileSystemLoader(str(base_dir))
    env = Environment(
        loader=loader,
        autoescape=False,          # plain-text system prompts
        undefined=StrictUndefined, # fail fast on missing vars
        trim_blocks=False,         # <-- keep your newlines
        lstrip_blocks=False,       # <-- keep your leading spaces
        keep_trailing_newline=True # optional: stable trailing newline
        # newline_sequence="\n",   # optional: normalize to LF
    )
    return env


def render_template_file(template_path: Path, context: dict[str, Any]) -> str:
    """
    Render a template file with the provided context.

    Args:
        template_path: Absolute or relative path to the template file.
        context: Variables to render into the template.

    Returns:
        Rendered string.
    """
    template_path = template_path.resolve()
    env = _env_for(template_path.parent)
    template = env.get_template(template_path.name)
    return template.render(**context)
