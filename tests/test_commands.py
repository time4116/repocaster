from repocaster.commands import parse_podcast_command


def test_parse_default_podcast_command():
    command = parse_podcast_command("/podcast")
    assert command is not None
    assert command.mode == "architecture"
    assert command.focus is None


def test_parse_focus_command():
    command = parse_podcast_command('/podcast focus "how LangChain is used"')
    assert command is not None
    assert command.mode == "focus"
    assert command.focus == "how LangChain is used"


def test_ignore_non_podcast_comment():
    assert parse_podcast_command("looks good") is None
