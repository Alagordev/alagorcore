from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QTableWidget, QTableWidgetItem, QHeaderView,
    QProgressBar, QLineEdit, QDialog, QTextEdit, QSizePolicy,
    QAbstractItemView, QComboBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QColor

# ── Stat Card ────────────────────────────────────────────────────────────────
class StatCard(QWidget):
    def __init__(self, label, value="—", color=None, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(4)

        self.val_lbl = QLabel(str(value))
        self.val_lbl.setObjectName("statValue")
        if color:
            self.val_lbl.setStyleSheet(f"color: {color};")

        self.lbl = QLabel(label.upper())
        self.lbl.setObjectName("statLabel")

        lay.addWidget(self.val_lbl)
        lay.addWidget(self.lbl)

    def set_value(self, v, color=None):
        self.val_lbl.setText(str(v))
        if color:
            self.val_lbl.setStyleSheet(f"color: {color};")

# ── Section Header ────────────────────────────────────────────────────────────
class SectionHeader(QWidget):
    def __init__(self, title, subtitle="", parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 8)
        lay.setSpacing(2)
        t = QLabel(title)
        t.setObjectName("pageTitle")
        lay.addWidget(t)
        if subtitle:
            s = QLabel(subtitle)
            s.setObjectName("subText")
            lay.addWidget(s)

# ── Divider ───────────────────────────────────────────────────────────────────
class Divider(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("divider")
        self.setFrameShape(QFrame.Shape.HLine)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(1)

# ── Status Badge ──────────────────────────────────────────────────────────────
class StatusBadge(QLabel):
    COLORS = {
        "running":  ("#2ecc71", "#0d2b1a"),
        "stopped":  ("#e74c3c", "#2b0d0d"),
        "disabled": ("#888888", "#1a1a1a"),
        "enabled":  ("#2ecc71", "#0d2b1a"),
        "ok":       ("#2ecc71", "#0d2b1a"),
        "warn":     ("#f39c12", "#2b1f0d"),
        "error":    ("#e74c3c", "#2b0d0d"),
        "info":     ("#3498db", "#0d1e2b"),
        "paused":   ("#f39c12", "#2b1f0d"),
        "ready":    ("#3498db", "#0d1e2b"),
    }

    def __init__(self, text, parent=None):
        super().__init__(parent)
        self.set_status(text)
        self.setFixedHeight(20)

    def set_status(self, text):
        self.setText(text.upper())
        key = text.lower()
        fg, bg = self.COLORS.get(key, ("#888888","#1a1a1a"))
        self.setStyleSheet(
            f"background:{bg}; color:{fg}; border:1px solid {fg};"
            f"border-radius:3px; padding:1px 6px; font-size:10px; font-weight:bold;"
        )

# ── Smart Table ───────────────────────────────────────────────────────────────
class SmartTable(QTableWidget):
    row_selected = pyqtSignal(int)

    def __init__(self, columns: list, parent=None):
        super().__init__(parent)
        self.setColumnCount(len(columns))
        self.setHorizontalHeaderLabels(columns)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setAlternatingRowColors(False)
        self.setSortingEnabled(True)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setStretchLastSection(True)
        self.setShowGrid(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.itemSelectionChanged.connect(self._on_select)

    def _on_select(self):
        rows = self.selectionModel().selectedRows()
        if rows:
            self.row_selected.emit(rows[0].row())

    def set_item(self, row, col, text, align=Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft):
        item = QTableWidgetItem(str(text))
        item.setTextAlignment(align)
        self.setItem(row, col, item)

    def add_row(self, values: list):
        r = self.rowCount()
        self.insertRow(r)
        for c, v in enumerate(values):
            self.set_item(r, c, v)
        return r

    def clear_rows(self):
        self.setRowCount(0)

    def filter_rows(self, text: str):
        text = text.lower()
        for r in range(self.rowCount()):
            match = False
            for c in range(self.columnCount()):
                item = self.item(r, c)
                if item and text in item.text().lower():
                    match = True
                    break
            self.setRowHidden(r, not match)

# ── Search Bar ────────────────────────────────────────────────────────────────
class SearchBar(QLineEdit):
    def __init__(self, placeholder="Search...", parent=None):
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        self.setFixedHeight(34)
        self.setMinimumWidth(200)

# ── Action Bar ────────────────────────────────────────────────────────────────
class ActionBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._lay = QHBoxLayout(self)
        self._lay.setContentsMargins(0, 8, 0, 8)
        self._lay.setSpacing(8)

    def add_button(self, text, obj_name="flatBtn", callback=None, tooltip=""):
        btn = QPushButton(text)
        btn.setObjectName(obj_name)
        if callback:
            btn.clicked.connect(callback)
        if tooltip:
            btn.setToolTip(tooltip)
        self._lay.addWidget(btn)
        return btn

    def add_stretch(self):
        self._lay.addStretch()

    def add_widget(self, w):
        self._lay.addWidget(w)

# ── Confirm Dialog ────────────────────────────────────────────────────────────
class ConfirmDialog(QDialog):
    def __init__(self, title, message, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(360)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 24, 24, 16)
        lay.setSpacing(16)

        msg = QLabel(message)
        msg.setWordWrap(True)
        msg.setObjectName("sectionTitle")
        lay.addWidget(msg)

        btns = QHBoxLayout()
        btns.setSpacing(8)
        btns.addStretch()

        cancel = QPushButton("Cancel")
        cancel.setObjectName("flatBtn")
        cancel.clicked.connect(self.reject)

        confirm = QPushButton("Confirm")
        confirm.setObjectName("dangerBtn")
        confirm.clicked.connect(self.accept)

        btns.addWidget(cancel)
        btns.addWidget(confirm)
        lay.addLayout(btns)

# ── Toggle Switch ─────────────────────────────────────────────────────────────
class ToggleSwitch(QWidget):
    toggled = pyqtSignal(bool)

    def __init__(self, checked=False, parent=None):
        super().__init__(parent)
        self._checked = checked
        self.setFixedSize(44, 24)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def isChecked(self): return self._checked

    def setChecked(self, val):
        self._checked = val
        self.update()

    def mousePressEvent(self, e):
        self._checked = not self._checked
        self.toggled.emit(self._checked)
        self.update()

    def paintEvent(self, e):
        from PyQt6.QtGui import QPainter, QBrush, QPen, QColor
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._checked:
            p.setBrush(QBrush(QColor("#e05c2a")))
        else:
            p.setBrush(QBrush(QColor("#444444")))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(0, 2, 44, 20, 10, 10)
        p.setBrush(QBrush(QColor("#ffffff")))
        x = 22 if self._checked else 2
        p.drawEllipse(x, 2, 20, 20)

# ── Progress Row ──────────────────────────────────────────────────────────────
class ProgressRow(QWidget):
    def __init__(self, label, value=0, max_val=100, color="#e05c2a", parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 2, 0, 2)
        lay.setSpacing(10)

        self.lbl = QLabel(label)
        self.lbl.setFixedWidth(120)
        self.lbl.setObjectName("subText")

        self.bar = QProgressBar()
        self.bar.setMaximum(max_val)
        self.bar.setValue(value)
        self.bar.setFixedHeight(8)
        self.bar.setTextVisible(False)
        self.bar.setStyleSheet(
            f"QProgressBar {{background:#2a2a2a;border:none;border-radius:4px;}}"
            f"QProgressBar::chunk {{background:{color};border-radius:4px;}}"
        )

        self.val_lbl = QLabel(f"{value}%")
        self.val_lbl.setFixedWidth(40)
        self.val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.val_lbl.setObjectName("subText")

        lay.addWidget(self.lbl)
        lay.addWidget(self.bar)
        lay.addWidget(self.val_lbl)

    def set_value(self, v):
        self.bar.setValue(int(v))
        self.val_lbl.setText(f"{v:.1f}%")

# ── Tweak Row ─────────────────────────────────────────────────────────────────
class TweakRow(QWidget):
    changed = pyqtSignal(bool)

    def __init__(self, title, description, checked=False, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setMinimumHeight(60)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(12)

        info = QVBoxLayout()
        info.setSpacing(2)
        t = QLabel(title)
        t.setObjectName("sectionTitle")
        d = QLabel(description)
        d.setObjectName("subText")
        d.setWordWrap(True)
        info.addWidget(t)
        info.addWidget(d)

        self.toggle = ToggleSwitch(checked=checked)
        self.toggle.toggled.connect(self.changed)

        lay.addLayout(info, 1)
        lay.addWidget(self.toggle)

    def is_checked(self): return self.toggle.isChecked()
    def set_checked(self, v): self.toggle.setChecked(v)

# ── Info Row ─────────────────────────────────────────────────────────────────
class InfoRow(QWidget):
    def __init__(self, label, value, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 4, 0, 4)
        lay.setSpacing(12)
        lbl = QLabel(label)
        lbl.setObjectName("subText")
        lbl.setFixedWidth(160)
        val = QLabel(str(value))
        val.setObjectName("sectionTitle")
        val.setWordWrap(True)
        lay.addWidget(lbl)
        lay.addWidget(val, 1)

# ── Card Widget ───────────────────────────────────────────────────────────────
class Card(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(16, 14, 16, 14)
        self._lay.setSpacing(8)

    def layout(self): return self._lay
    def add(self, w): self._lay.addWidget(w)
    def add_layout(self, l): self._lay.addLayout(l)
