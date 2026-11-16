import re
from pathlib import Path

import apps

KEYBOARD = re.compile(r"""["']reply_markup["']|reply_markup\s*=|inline_keyboard|InlineKeyboard""")


def test_no_production_code_builds_an_inline_keyboard():
    root = Path(apps.__file__).resolve().parent
    offenders = [
        str(path.relative_to(root))
        for path in root.rglob("*.py")
        if "migrations" not in path.parts and KEYBOARD.search(path.read_text(encoding="utf-8"))
    ]
    assert offenders == []
