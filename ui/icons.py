from PySide6.QtCore import QByteArray, QSize, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

_SVG_PATHS: dict[str, str] = {
    "file-plus": (
        '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>'
        '<polyline points="14 2 14 8 20 8"/>'
        '<line x1="12" y1="18" x2="12" y2="12"/>'
        '<line x1="9" y1="15" x2="15" y2="15"/>'
    ),
    "folder-plus": (
        '<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>'
        '<line x1="12" y1="11" x2="12" y2="17"/>'
        '<line x1="9" y1="14" x2="15" y2="14"/>'
    ),
    "folder": '<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>',
    "save": (
        '<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/>'
        '<polyline points="17 21 17 13 7 13 7 21"/>'
        '<polyline points="7 3 7 8 15 8"/>'
    ),
    "trash": (
        '<polyline points="3 6 5 6 21 6"/>'
        '<path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>'
        '<line x1="10" y1="11" x2="10" y2="17"/>'
        '<line x1="14" y1="11" x2="14" y2="17"/>'
    ),
    "image": (
        '<rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>'
        '<circle cx="8.5" cy="8.5" r="1.5"/>'
        '<polyline points="21 15 16 10 5 21"/>'
    ),
    "fingerprint": (
        '<path d="M2 12C2 6.5 6.5 2 12 2a10 10 0 0 1 8 4"/>'
        '<path d="M5 19.5C5.5 18 6 15 6 12c0-.7.12-1.37.34-2"/>'
        '<path d="M17.29 21.02c.12-.6.43-2.3.5-3.02"/>'
        '<path d="M12 10a2 2 0 0 0-2 2c0 1.02-.1 2.51-.26 4"/>'
        '<path d="M8.65 22c.21-.66.45-1.32.57-2"/>'
        '<path d="M14 13.12c0 2.38 0 6.38-1 8.88"/>'
        '<path d="M2 16h.01"/>'
        '<path d="M21.8 16c.2-2 .131-5.354 0-6"/>'
        '<path d="M9 6.8a6 6 0 0 1 9 5.2c0 .47 0 1.17-.02 2"/>'
    ),
    "mic": (
        '<path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>'
        '<path d="M19 10v2a7 7 0 0 1-14 0v-2"/>'
        '<line x1="12" y1="19" x2="12" y2="23"/>'
        '<line x1="8" y1="23" x2="16" y2="23"/>'
    ),
    "sliders": (
        '<line x1="4" y1="21" x2="4" y2="14"/>'
        '<line x1="4" y1="10" x2="4" y2="3"/>'
        '<line x1="12" y1="21" x2="12" y2="12"/>'
        '<line x1="12" y1="8" x2="12" y2="3"/>'
        '<line x1="20" y1="21" x2="20" y2="16"/>'
        '<line x1="20" y1="12" x2="20" y2="3"/>'
        '<line x1="1" y1="14" x2="7" y2="14"/>'
        '<line x1="9" y1="8" x2="15" y2="8"/>'
        '<line x1="17" y1="16" x2="23" y2="16"/>'
    ),
    "film": (
        '<rect x="2" y="2" width="20" height="20" rx="2.18" ry="2.18"/>'
        '<line x1="7" y1="2" x2="7" y2="22"/>'
        '<line x1="17" y1="2" x2="17" y2="22"/>'
        '<line x1="2" y1="12" x2="22" y2="12"/>'
        '<line x1="2" y1="7" x2="7" y2="7"/>'
        '<line x1="2" y1="17" x2="7" y2="17"/>'
        '<line x1="17" y1="17" x2="22" y2="17"/>'
        '<line x1="17" y1="7" x2="22" y2="7"/>'
    ),
    "edit": (
        '<path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>'
        '<path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>'
    ),
    "hash": (
        '<line x1="4" y1="9" x2="20" y2="9"/>'
        '<line x1="4" y1="15" x2="20" y2="15"/>'
        '<line x1="10" y1="3" x2="8" y2="21"/>'
        '<line x1="16" y1="3" x2="14" y2="21"/>'
    ),
    "search": '<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>',
    "tag": (
        '<path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/>'
        '<line x1="7" y1="7" x2="7.01" y2="7"/>'
    ),
    "list": (
        '<line x1="8" y1="6" x2="21" y2="6"/>'
        '<line x1="8" y1="12" x2="21" y2="12"/>'
        '<line x1="8" y1="18" x2="21" y2="18"/>'
        '<line x1="3" y1="6" x2="3.01" y2="6"/>'
        '<line x1="3" y1="12" x2="3.01" y2="12"/>'
        '<line x1="3" y1="18" x2="3.01" y2="18"/>'
    ),
    "cpu": (
        '<rect x="4" y="4" width="16" height="16" rx="2" ry="2"/>'
        '<rect x="9" y="9" width="6" height="6"/>'
        '<line x1="9" y1="1" x2="9" y2="4"/>'
        '<line x1="15" y1="1" x2="15" y2="4"/>'
        '<line x1="9" y1="20" x2="9" y2="23"/>'
        '<line x1="15" y1="20" x2="15" y2="23"/>'
        '<line x1="20" y1="9" x2="23" y2="9"/>'
        '<line x1="20" y1="14" x2="23" y2="14"/>'
        '<line x1="1" y1="9" x2="4" y2="9"/>'
        '<line x1="1" y1="14" x2="4" y2="14"/>'
    ),
    "plus": '<line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>',
    "rotate-ccw": '<polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/>',
    "camera": (
        '<path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/>'
        '<circle cx="12" cy="13" r="4"/>'
    ),
    "globe": (
        '<circle cx="12" cy="12" r="10"/>'
        '<line x1="2" y1="12" x2="22" y2="12"/>'
        '<path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>'
    ),
    "download": (
        '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>'
        '<polyline points="7 10 12 15 17 10"/>'
        '<line x1="12" y1="15" x2="12" y2="3"/>'
    ),
    "x": '<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>',
    "disc": '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="3"/>',
    "check": '<polyline points="20 6 9 17 4 12"/>',
    "alert-circle": (
        '<circle cx="12" cy="12" r="10"/>'
        '<line x1="12" y1="8" x2="12" y2="12"/>'
        '<line x1="12" y1="16" x2="12.01" y2="16"/>'
    ),
    "stop": '<rect x="5" y="5" width="14" height="14" rx="2" ry="2"/>',
}

ICON_NAMES: tuple[str, ...] = tuple(_SVG_PATHS.keys())
_ICON_CACHE: dict[tuple[str, str, int], QIcon] = {}
_PIXMAP_CACHE: dict[tuple[str, str, int], QPixmap] = {}


def get_pixmap(name: str, color: str = "#cbd5e1", size: int = 16) -> QPixmap:
    key = (name, color, size)
    if key in _PIXMAP_CACHE:
        return _PIXMAP_CACHE[key]

    body = _SVG_PATHS.get(name, _SVG_PATHS["disc"])
    svg_xml = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 24 24" fill="none" stroke="{color}" '
        f'stroke-width="1.85" stroke-linecap="round" stroke-linejoin="round">'
        f"{body}</svg>"
    )
    renderer = QSvgRenderer(QByteArray(svg_xml.encode("utf-8")))
    pixmap = QPixmap(QSize(size, size))
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter)
    painter.end()

    _PIXMAP_CACHE[key] = pixmap
    return pixmap


def get_icon(name: str, color: str = "#cbd5e1", size: int = 16) -> QIcon:
    key = (name, color, size)
    if key in _ICON_CACHE:
        return _ICON_CACHE[key]

    icon = QIcon()
    normal_pix = get_pixmap(name, color, size)
    disabled_pix = get_pixmap(name, "#475569", size)
    active_pix = get_pixmap(name, "#ffffff", size)
    icon.addPixmap(normal_pix, QIcon.Mode.Normal, QIcon.State.Off)
    icon.addPixmap(disabled_pix, QIcon.Mode.Disabled, QIcon.State.Off)
    icon.addPixmap(active_pix, QIcon.Mode.Active, QIcon.State.Off)

    _ICON_CACHE[key] = icon
    return icon
