"""Shared pytest hooks."""


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Say plainly when the browser check did not run.

    A bare "s" in the progress line is easy to miss, and that skip covers the only
    check of the review page's JavaScript.
    """
    skipped = [r for r in terminalreporter.stats.get("skipped", [])
               if "playwright" in str(getattr(r, "longrepr", ""))]
    if skipped:
        terminalreporter.write_line(
            "coverage note: the review page's JavaScript was not executed "
            "(no playwright). See references/qa-page.md for the setup."
        )
