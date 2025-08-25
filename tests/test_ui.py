import os, sys, pytest
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
if not os.environ.get('DISPLAY'):
    pytest.skip('No display', allow_module_level=True)

from ui.main_window import MainWindow


def test_mainwindow_initialization():
    app = MainWindow()
    try:
        assert app.platform_var.get() == "Unknown"
        assert "AtCoder" in app.scrapers
    finally:
        app.root.destroy()


def test_toggle_theme():
    app = MainWindow()
    try:
        initial = app.dark_mode
        app._toggle_theme()
        assert app.dark_mode != initial
    finally:
        app.root.destroy()
