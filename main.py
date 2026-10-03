import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from database.storage import Storage
from browser.engine import ProfileManager
from browser import omni
from ui import brand
from ui import icons
from ui.main_window import MainWindow

ROOT = Path(__file__).resolve().parent


def main() -> int:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName(brand.NAME)
    app.setOrganizationName(brand.NAME)
    app.setWindowIcon(brand.app_icon())

    icons.sync_assets(ROOT / "assets" / "icons")

    storage = Storage()
    profiles = ProfileManager(app)
    window = MainWindow(storage, profiles)
    window.show()

    # `python main.py https://example.com` opens the address(es) given
    for arg in sys.argv[1:]:
        res = omni.resolve(arg, omni.engine_url(storage.get_setting(
            "search_engine", omni.DEFAULT_ENGINE)))
        if res is not None and res.kind in ("url", "internal"):
            window.manager.new_tab(res.url)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
