from cfgfmt.formatter import FormatOptions, format_text

def test_format_text_runs():
    raw = 'bind "w" "+forward"\n'
    fr = format_text(raw, options=FormatOptions())
    assert fr.out_text.endswith("\n")
    assert fr.out_text.replace(" ", "") == raw.replace(" ", "")
