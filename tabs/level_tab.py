"""
Level Editor Tab — create and export custom JellyCar levels as mods.

Coordinate system: world units, Y-up (same as JellyCar physics).
Bodies are defined in normalized shape space (-0.5..0.5), then placed
as GameObjects with position + scale in world space.
"""

import math, os, struct, shutil, tempfile, json
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QSplitter, QGraphicsView,
    QGraphicsScene, QGraphicsItem, QGraphicsEllipseItem, QGraphicsLineItem,
    QGraphicsRectItem, QGraphicsPolygonItem, QGraphicsTextItem,
    QGroupBox, QLabel, QLineEdit, QPushButton, QComboBox, QCheckBox,
    QDoubleSpinBox, QSpinBox, QScrollArea, QFormLayout, QFileDialog,
    QMessageBox, QColorDialog, QListWidget, QListWidgetItem, QToolBar,
    QSizePolicy, QFrame, QSlider, QTabWidget
)
from PyQt6.QtCore import Qt, QPointF, QRectF, pyqtSignal, QLineF
from PyQt6.QtGui import (
    QPen, QBrush, QColor, QPainter, QPolygonF, QFont, QTransform,
    QPixmap, QImage
)

from utils.scenec_writer import write_scenec
from utils.mod_writer import _safe_name, _write_manifest

# ── Material names ──────────────────────────────────────────────────────────
MATERIALS = {
    0: "Ground",
    1: "Dynamic",
    2: "Car Chassis",
    3: "Car Tires",
    4: "Ice",
    5: "Items",
    6: "Balloons",
    7: "Special",
}

# ── Colours for materials in the editor ─────────────────────────────────────
MAT_COLORS = {
    0: QColor(120, 180, 120),
    1: QColor(180, 140, 80),
    2: QColor(80, 120, 200),
    3: QColor(60, 60, 60),
    4: QColor(160, 220, 255),
    5: QColor(220, 180, 60),
    6: QColor(200, 100, 200),
    7: QColor(200, 80, 80),
}

GRID_SIZE = 1.0   # world units per grid cell


# ═══════════════════════════════════════════════════════════════════════════
# Data model
# ═══════════════════════════════════════════════════════════════════════════

class BodyDef:
    """A reusable softbody shape definition (normalized -0.5..0.5 space)."""
    _counter = 0

    def __init__(self, name=None):
        BodyDef._counter += 1
        self.name = name or f"body{BodyDef._counter}"
        self.colorR = 0.5
        self.colorG = 0.8
        self.colorB = 0.5
        self.massPerPoint = 1.0
        self.edgeK = 200.0
        self.edgeDamping = 1.0
        self.isKinematic = False
        self.shapeMatching = True
        self.shapeK = 100.0
        self.shapeDamping = 10.0
        self.pressureized = False
        self.pressure = 0.0
        # points: list of (x, y) in -0.5..0.5 space
        self.points: list[tuple[float, float]] = []
        # springs: list of (pt1, pt2, k, damp)
        self.springs: list[tuple[int, int, float, float]] = []
        # polygons: list of (i0, i1, i2)
        self.polygons: list[tuple[int, int, int]] = []

    def to_dict(self):
        return {
            'name': self.name,
            'colorR': self.colorR, 'colorG': self.colorG, 'colorB': self.colorB,
            'massPerPoint': self.massPerPoint,
            'edgeK': self.edgeK, 'edgeDamping': self.edgeDamping,
            'isKinematic': self.isKinematic,
            'shapeMatching': self.shapeMatching,
            'shapeK': self.shapeK, 'shapeDamping': self.shapeDamping,
            'pressureized': self.pressureized, 'pressure': self.pressure,
            'points': [(x, y, -1.0) for (x, y) in self.points],
            'springs': list(self.springs),
            'polygons': list(self.polygons),
        }

    @classmethod
    def from_dict(cls, d: dict) -> 'BodyDef':
        b = cls(d['name'])
        b.colorR = d.get('colorR', 0.5)
        b.colorG = d.get('colorG', 0.8)
        b.colorB = d.get('colorB', 0.5)
        b.massPerPoint = d.get('massPerPoint', 1.0)
        b.edgeK = d.get('edgeK', 200.0)
        b.edgeDamping = d.get('edgeDamping', 10.0)
        b.isKinematic = d.get('isKinematic', False)
        b.shapeMatching = d.get('shapeMatching', True)
        b.shapeK = d.get('shapeK', 100.0)
        b.shapeDamping = d.get('shapeDamping', 10.0)
        b.pressureized = d.get('pressureized', False)
        b.pressure = d.get('pressure', 0.0)
        b.points = [(p[0], p[1]) for p in d.get('points', [])]
        b.springs = [tuple(s) for s in d.get('springs', [])]
        b.polygons = [tuple(p) for p in d.get('polygons', [])]
        return b


class ObjectInstance:
    """A placed instance of a BodyDef in world space."""
    _counter = 0

    def __init__(self, body: BodyDef, posX=0.0, posY=0.0,
                 scaleX=5.0, scaleY=5.0, angle=0.0, material=0):
        ObjectInstance._counter += 1
        self.body = body
        self.posX = posX
        self.posY = posY
        self.scaleX = scaleX
        self.scaleY = scaleY
        self.angle = angle
        self.material = material
        self.isPlatform = False
        self.isMotor = False
        self.platformOffsetX = 0.0
        self.platformOffsetY = 0.0
        self.platformSecondsPerLoop = 4.0
        self.platformStartOffset = 0.0
        self.motorRadiansPerSecond = 1.0
        # canvas item reference
        self._item = None

    def to_dict(self):
        return {
            'name': self.body.name,
            'posX': self.posX, 'posY': self.posY,
            'angle': self.angle,
            'scaleX': self.scaleX, 'scaleY': self.scaleY,
            'material': self.material,
            'isPlatform': self.isPlatform,
            'isMotor': self.isMotor,
            'platformOffsetX': self.platformOffsetX,
            'platformOffsetY': self.platformOffsetY,
            'platformSecondsPerLoop': self.platformSecondsPerLoop,
            'platformStartOffset': self.platformStartOffset,
            'motorRadiansPerSecond': self.motorRadiansPerSecond,
        }

    @classmethod
    def from_dict(cls, d: dict, body: BodyDef) -> 'ObjectInstance':
        obj = cls(body,
                  posX=d.get('posX', 0.0), posY=d.get('posY', 0.0),
                  scaleX=d.get('scaleX', 5.0), scaleY=d.get('scaleY', 5.0),
                  angle=d.get('angle', 0.0), material=d.get('material', 0))
        obj.isPlatform = d.get('isPlatform', False)
        obj.isMotor = d.get('isMotor', False)
        obj.platformOffsetX = d.get('platformOffsetX', 0.0)
        obj.platformOffsetY = d.get('platformOffsetY', 0.0)
        obj.platformSecondsPerLoop = d.get('platformSecondsPerLoop', 4.0)
        obj.platformStartOffset = d.get('platformStartOffset', 0.0)
        obj.motorRadiansPerSecond = d.get('motorRadiansPerSecond', 1.0)
        return obj


class LevelData:
    def __init__(self):
        self.bodies: list[BodyDef] = []
        self.objects: list[ObjectInstance] = []
        self.car_x = 0.0
        self.car_y = 2.0
        self.finish_x = 50.0
        self.finish_y = 0.0
        self.fall_line = -20.0
        self.level_name = "My Level"

    def get_body(self, name: str):
        for b in self.bodies:
            if b.name == name:
                return b
        return None

    def add_body(self, b: BodyDef):
        self.bodies.append(b)

    def add_object(self, obj: ObjectInstance):
        self.objects.append(obj)

    def remove_object(self, obj: ObjectInstance):
        if obj in self.objects:
            self.objects.remove(obj)

    def is_valid(self):
        return len(self.bodies) > 0 and len(self.objects) > 0

    def to_json(self) -> str:
        return json.dumps({
            'level_name': self.level_name,
            'car_x': self.car_x, 'car_y': self.car_y,
            'finish_x': self.finish_x, 'finish_y': self.finish_y,
            'fall_line': self.fall_line,
            'bodies': [b.to_dict() for b in self.bodies],
            'objects': [o.to_dict() for o in self.objects],
        }, indent=2)

    @classmethod
    def from_json(cls, text: str) -> 'LevelData':
        d = json.loads(text)
        lv = cls()
        lv.level_name = d.get('level_name', 'My Level')
        lv.car_x = d.get('car_x', 0.0)
        lv.car_y = d.get('car_y', 2.0)
        lv.finish_x = d.get('finish_x', 50.0)
        lv.finish_y = d.get('finish_y', 0.0)
        lv.fall_line = d.get('fall_line', -20.0)
        for bd in d.get('bodies', []):
            lv.bodies.append(BodyDef.from_dict(bd))
        for od in d.get('objects', []):
            body = lv.get_body(od['name'])
            if body:
                lv.objects.append(ObjectInstance.from_dict(od, body))
        return lv


# ═══════════════════════════════════════════════════════════════════════════
# Canvas items
# ═══════════════════════════════════════════════════════════════════════════

PIXELS_PER_UNIT = 40.0   # screen pixels per world unit


def world_to_screen(wx, wy):
    """World (Y-up) → screen (Y-down) in pixels."""
    return wx * PIXELS_PER_UNIT, -wy * PIXELS_PER_UNIT


def screen_to_world(sx, sy):
    return sx / PIXELS_PER_UNIT, -sy / PIXELS_PER_UNIT


class ObjectItem(QGraphicsPolygonItem):
    """Draggable canvas item representing an ObjectInstance."""

    def __init__(self, obj: ObjectInstance, canvas: 'LevelCanvas'):
        super().__init__()
        self.obj = obj
        self.canvas = canvas
        obj._item = self
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
            QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        self._rebuild()

    def _rebuild(self):
        obj = self.obj
        body = obj.body
        color = QColor.fromRgbF(body.colorR, body.colorG, body.colorB)
        self.setBrush(QBrush(color))
        pen = QPen(color.darker(150), 1.5)
        self.setPen(pen)

        if body.points:
            poly = QPolygonF()
            for (bx, by) in body.points:
                sx = bx * obj.scaleX * PIXELS_PER_UNIT
                sy = -by * obj.scaleY * PIXELS_PER_UNIT
                poly.append(QPointF(sx, sy))
            self.setPolygon(poly)
        else:
            # fallback rectangle
            hw = obj.scaleX * 0.5 * PIXELS_PER_UNIT
            hh = obj.scaleY * 0.5 * PIXELS_PER_UNIT
            poly = QPolygonF([
                QPointF(-hw, -hh), QPointF(hw, -hh),
                QPointF(hw, hh), QPointF(-hw, hh)
            ])
            self.setPolygon(poly)

        sx, sy = world_to_screen(obj.posX, obj.posY)
        self.setPos(sx, sy)
        self.setRotation(-obj.angle)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            wx, wy = screen_to_world(value.x(), value.y())
            self.obj.posX = round(wx, 3)
            self.obj.posY = round(wy, 3)
            self.canvas.object_moved.emit(self.obj)
        return super().itemChange(change, value)

    def mouseDoubleClickEvent(self, event):
        self.canvas.object_double_clicked.emit(self.obj)
        super().mouseDoubleClickEvent(event)


class MarkerItem(QGraphicsEllipseItem):
    """Car spawn or finish marker."""

    def __init__(self, label: str, color: QColor, canvas: 'LevelCanvas', marker_type: str):
        r = 12
        super().__init__(-r, -r, r*2, r*2)
        self.marker_type = marker_type
        self.canvas = canvas
        self.setBrush(QBrush(color))
        self.setPen(QPen(color.darker(150), 2))
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
            QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        txt = QGraphicsTextItem(label, self)
        txt.setDefaultTextColor(Qt.GlobalColor.white)
        txt.setFont(QFont("Arial", 7, QFont.Weight.Bold))
        txt.setPos(-10, -8)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            wx, wy = screen_to_world(value.x(), value.y())
            self.canvas.marker_moved.emit(self.marker_type, wx, wy)
        return super().itemChange(change, value)


# ═══════════════════════════════════════════════════════════════════════════
# Canvas (QGraphicsView)
# ═══════════════════════════════════════════════════════════════════════════

class LevelCanvas(QGraphicsView):
    object_moved = pyqtSignal(object)
    object_double_clicked = pyqtSignal(object)
    marker_moved = pyqtSignal(str, float, float)
    canvas_clicked = pyqtSignal(float, float)   # world coords

    def __init__(self):
        self._scene = QGraphicsScene()
        super().__init__(self._scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setBackgroundBrush(QBrush(QColor(30, 30, 40)))
        self._draw_grid()
        self._car_marker = None
        self._finish_marker = None
        self._fall_line = None
        self._placing_mode = None   # None | 'object'
        self._pending_body = None

    # ── Grid ────────────────────────────────────────────────────────────────
    def _draw_grid(self):
        pen_minor = QPen(QColor(50, 50, 60), 0.5)
        pen_major = QPen(QColor(70, 70, 85), 1.0)
        pen_axis  = QPen(QColor(100, 100, 120), 1.5)
        extent = 300
        for i in range(-extent, extent + 1):
            pen = pen_axis if i == 0 else (pen_major if i % 5 == 0 else pen_minor)
            sx, _ = world_to_screen(i, 0)
            self._scene.addLine(sx, -extent * PIXELS_PER_UNIT,
                                 sx,  extent * PIXELS_PER_UNIT, pen)
            _, sy = world_to_screen(0, i)
            self._scene.addLine(-extent * PIXELS_PER_UNIT, sy,
                                  extent * PIXELS_PER_UNIT, sy, pen)

    # ── Markers ─────────────────────────────────────────────────────────────
    def set_car_marker(self, wx, wy):
        if self._car_marker:
            self._scene.removeItem(self._car_marker)
        self._car_marker = MarkerItem("CAR", QColor(80, 200, 80), self, 'car')
        sx, sy = world_to_screen(wx, wy)
        self._car_marker.setPos(sx, sy)
        self._scene.addItem(self._car_marker)

    def set_finish_marker(self, wx, wy):
        if self._finish_marker:
            self._scene.removeItem(self._finish_marker)
        self._finish_marker = MarkerItem("END", QColor(255, 180, 0), self, 'finish')
        sx, sy = world_to_screen(wx, wy)
        self._finish_marker.setPos(sx, sy)
        self._scene.addItem(self._finish_marker)

    def set_fall_line(self, wy):
        if self._fall_line:
            self._scene.removeItem(self._fall_line)
        pen = QPen(QColor(200, 60, 60), 1.5, Qt.PenStyle.DashLine)
        _, sy = world_to_screen(0, wy)
        self._fall_line = self._scene.addLine(
            -300 * PIXELS_PER_UNIT, sy, 300 * PIXELS_PER_UNIT, sy, pen)

    # ── Object items ─────────────────────────────────────────────────────────
    def add_object_item(self, obj: ObjectInstance) -> ObjectItem:
        item = ObjectItem(obj, self)
        self._scene.addItem(item)
        return item

    def remove_object_item(self, obj: ObjectInstance):
        if obj._item:
            self._scene.removeItem(obj._item)
            obj._item = None

    def refresh_object_item(self, obj: ObjectInstance):
        if obj._item:
            obj._item._rebuild()

    # ── Placing mode ─────────────────────────────────────────────────────────
    def start_placing(self, body: BodyDef):
        self._placing_mode = 'object'
        self._pending_body = body
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def cancel_placing(self):
        self._placing_mode = None
        self._pending_body = None
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def mousePressEvent(self, event):
        if self._placing_mode == 'object' and event.button() == Qt.MouseButton.LeftButton:
            sp = self.mapToScene(event.pos())
            wx, wy = screen_to_world(sp.x(), sp.y())
            self.canvas_clicked.emit(wx, wy)
            self.cancel_placing()
            return
        super().mousePressEvent(event)

    # ── Zoom ─────────────────────────────────────────────────────────────────
    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)

    def fit_view(self):
        self.fitInView(QRectF(-5 * PIXELS_PER_UNIT, -15 * PIXELS_PER_UNIT,
                               60 * PIXELS_PER_UNIT, 25 * PIXELS_PER_UNIT),
                       Qt.AspectRatioMode.KeepAspectRatio)

    def render_thumbnail(self, width=256, height=128) -> QImage:
        img = QImage(width, height, QImage.Format.Format_ARGB32)
        img.fill(QColor(30, 30, 40))
        painter = QPainter(img)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._scene.render(painter)
        painter.end()
        return img


# ═══════════════════════════════════════════════════════════════════════════
# Body shape presets
# ═══════════════════════════════════════════════════════════════════════════

def _make_rect_body(name, colorR=0.5, colorG=0.8, colorB=0.5,
                    massPerPoint=0.0, edgeK=100.0, edgeDamping=10.0,
                    isKinematic=False, shapeMatching=True,
                    shapeK=100.0, shapeDamping=10.0,
                    add_cross_springs=False) -> BodyDef:
    """Rectangle in normalized space with triangulated polygons."""
    b = BodyDef(name)
    b.colorR, b.colorG, b.colorB = colorR, colorG, colorB
    b.massPerPoint = massPerPoint
    b.edgeK, b.edgeDamping = edgeK, edgeDamping
    b.isKinematic = isKinematic
    b.shapeMatching, b.shapeK, b.shapeDamping = shapeMatching, shapeK, shapeDamping
    # 4 corners CCW (matches game's winding convention): BL(0), TL(1), TR(2), BR(3)
    b.points = [(-0.5, -0.5), (-0.5, 0.5), (0.5, 0.5), (0.5, -0.5)]
    b.polygons = [(0, 1, 2), (0, 2, 3)]
    # Cross springs prevent penetration for dynamic/kinematic bodies
    if add_cross_springs:
        b.springs = [(0, 2, edgeK, edgeDamping), (1, 3, edgeK, edgeDamping)]
    return b


def _make_circle_body(name, segments=12, colorR=0.8, colorG=0.5, colorB=0.2,
                      massPerPoint=1.0, edgeK=1000.0, edgeDamping=10.0,
                      pressureized=True, pressure=40.0) -> BodyDef:
    """Circle approximated with N segments."""
    b = BodyDef(name)
    b.colorR, b.colorG, b.colorB = colorR, colorG, colorB
    b.massPerPoint = massPerPoint
    b.edgeK, b.edgeDamping = edgeK, edgeDamping
    b.pressureized = pressureized
    b.pressure = pressure
    b.shapeMatching = False
    pts = []
    for i in range(segments):
        a = 2 * math.pi * i / segments
        pts.append((0.5 * math.cos(a), 0.5 * math.sin(a)))
    b.points = pts
    # fan triangulation from center — but center isn't a point, use edge triangles
    for i in range(segments):
        b.polygons.append((i, (i + 1) % segments, 0))
    return b


SHAPE_PRESETS = {
    "Rectangle (Ground)": lambda name: _make_rect_body(
        name, colorR=0.5, colorG=1.0, colorB=1.0,
        massPerPoint=0.0, edgeK=100.0, edgeDamping=10.0, isKinematic=False,
        shapeMatching=True, shapeK=100.0, shapeDamping=10.0,
        add_cross_springs=False),
    "Rectangle (Dynamic)": lambda name: _make_rect_body(
        name, colorR=1.0, colorG=0.8, colorB=0.2,
        massPerPoint=1.0, edgeK=2000.0, edgeDamping=15.0, isKinematic=False,
        shapeMatching=True, shapeK=1000.0, shapeDamping=15.0,
        add_cross_springs=True),
    "Rectangle (Platform)": lambda name: _make_rect_body(
        name, colorR=0.5, colorG=0.5, colorB=1.0,
        massPerPoint=1.0, edgeK=8000.0, edgeDamping=15.0, isKinematic=True,
        shapeMatching=True, shapeK=5000.0, shapeDamping=15.0,
        add_cross_springs=True),
    "Circle (Bouncy)": lambda name: _make_circle_body(
        name, pressureized=True, pressure=40.0, massPerPoint=1.0),
    "Circle (Solid)": lambda name: _make_circle_body(
        name, pressureized=False, pressure=0.0, massPerPoint=1.0),
}


# ═══════════════════════════════════════════════════════════════════════════
# Property panel
# ═══════════════════════════════════════════════════════════════════════════

class _SpinF(QDoubleSpinBox):
    def __init__(self, val=0.0, lo=-9999.0, hi=9999.0, step=0.1, decimals=3):
        super().__init__()
        self.setRange(lo, hi)
        self.setSingleStep(step)
        self.setDecimals(decimals)
        self.setValue(val)
        self.setFixedWidth(90)


class ObjectPropertiesPanel(QWidget):
    """Shows/edits properties of the selected ObjectInstance."""
    changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._obj: ObjectInstance | None = None
        self._building = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        self._title = QLabel("No selection")
        self._title.setStyleSheet("font-weight: bold; color: #aaa;")
        layout.addWidget(self._title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        self._form = QFormLayout(inner)
        self._form.setSpacing(4)
        scroll.setWidget(inner)
        layout.addWidget(scroll)

        # Transform
        self._posX = _SpinF()
        self._posY = _SpinF()
        self._angle = _SpinF(lo=-360, hi=360, step=1.0, decimals=1)
        self._scaleX = _SpinF(1.0, 0.01, 500.0, 0.5)
        self._scaleY = _SpinF(1.0, 0.01, 500.0, 0.5)
        self._form.addRow("Pos X:", self._posX)
        self._form.addRow("Pos Y:", self._posY)
        self._form.addRow("Angle:", self._angle)
        self._form.addRow("Scale X:", self._scaleX)
        self._form.addRow("Scale Y:", self._scaleY)

        # Body physics (affects the BodyDef)
        self._isKinematic = QCheckBox("Kinematic (platform/motor only)")
        self._form.addRow("", self._isKinematic)
        self._massPerPoint = _SpinF(1.0, 0.0, 100.0, 0.1, decimals=2)
        self._form.addRow("Mass/Point:", self._massPerPoint)

        # Material
        self._material = QComboBox()
        for k, v in MATERIALS.items():
            self._material.addItem(v, k)
        self._form.addRow("Material:", self._material)

        # Platform
        self._isPlatform = QCheckBox("Is Platform")
        self._form.addRow("", self._isPlatform)
        self._platOffX = _SpinF()
        self._platOffY = _SpinF()
        self._platSecs = _SpinF(4.0, 0.1, 60.0, 0.5)
        self._platStart = _SpinF(0.0, 0.0, 1.0, 0.05)
        self._form.addRow("Plat Offset X:", self._platOffX)
        self._form.addRow("Plat Offset Y:", self._platOffY)
        self._form.addRow("Plat Secs:", self._platSecs)
        self._form.addRow("Plat Start:", self._platStart)

        # Motor
        self._isMotor = QCheckBox("Is Motor")
        self._form.addRow("", self._isMotor)
        self._motorRPS = _SpinF(1.0, -100.0, 100.0, 0.1)
        self._form.addRow("Motor RPS:", self._motorRPS)

        # Body color
        self._colorBtn = QPushButton("Body Color")
        self._colorBtn.clicked.connect(self._pick_color)
        self._form.addRow("", self._colorBtn)

        # Wire up signals
        for w in [self._posX, self._posY, self._angle, self._scaleX, self._scaleY,
                  self._platOffX, self._platOffY, self._platSecs, self._platStart,
                  self._motorRPS, self._massPerPoint]:
            w.valueChanged.connect(self._on_change)
        self._material.currentIndexChanged.connect(self._on_change)
        self._isPlatform.toggled.connect(self._on_change)
        self._isMotor.toggled.connect(self._on_change)
        self._isKinematic.toggled.connect(self._on_change)

        self.setEnabled(False)

    def load(self, obj: ObjectInstance):
        self._obj = obj
        self._building = True
        self._title.setText(f"Object: {obj.body.name}")
        self._posX.setValue(obj.posX)
        self._posY.setValue(obj.posY)
        self._angle.setValue(obj.angle)
        self._scaleX.setValue(obj.scaleX)
        self._scaleY.setValue(obj.scaleY)
        idx = self._material.findData(obj.material)
        self._material.setCurrentIndex(idx if idx >= 0 else 0)
        self._isKinematic.setChecked(obj.body.isKinematic)
        self._massPerPoint.setValue(obj.body.massPerPoint)
        self._isPlatform.setChecked(obj.isPlatform)
        self._isMotor.setChecked(obj.isMotor)
        self._platOffX.setValue(obj.platformOffsetX)
        self._platOffY.setValue(obj.platformOffsetY)
        self._platSecs.setValue(obj.platformSecondsPerLoop)
        self._platStart.setValue(obj.platformStartOffset)
        self._motorRPS.setValue(obj.motorRadiansPerSecond)
        self._building = False
        self.setEnabled(True)

    def clear(self):
        self._obj = None
        self._title.setText("No selection")
        self.setEnabled(False)

    def _on_change(self):
        if self._building or self._obj is None:
            return
        o = self._obj
        o.posX = self._posX.value()
        o.posY = self._posY.value()
        o.angle = self._angle.value()
        o.scaleX = self._scaleX.value()
        o.scaleY = self._scaleY.value()
        o.body.isKinematic = self._isKinematic.isChecked()
        o.body.massPerPoint = self._massPerPoint.value()
        o.material = self._material.currentData()
        o.isPlatform = self._isPlatform.isChecked()
        o.isMotor = self._isMotor.isChecked()
        o.platformOffsetX = self._platOffX.value()
        o.platformOffsetY = self._platOffY.value()
        o.platformSecondsPerLoop = self._platSecs.value()
        o.platformStartOffset = self._platStart.value()
        o.motorRadiansPerSecond = self._motorRPS.value()
        self.changed.emit()

    def _pick_color(self):
        if self._obj is None:
            return
        b = self._obj.body
        init = QColor.fromRgbF(b.colorR, b.colorG, b.colorB)
        c = QColorDialog.getColor(init, self, "Body Color")
        if c.isValid():
            b.colorR = c.redF()
            b.colorG = c.greenF()
            b.colorB = c.blueF()
            self.changed.emit()


# ═══════════════════════════════════════════════════════════════════════════
# Main Level Tab
# ═══════════════════════════════════════════════════════════════════════════

class LevelTab(QWidget):
    def __init__(self):
        super().__init__()
        self._level = LevelData()
        self._selected_obj: ObjectInstance | None = None
        self._custom_thumb_path: str | None = None
        self._patch_folder: str | None = None

        # Restore persisted paths (default: unset)
        from PyQt6.QtCore import QSettings
        self._settings = QSettings("JellyModTool", "LevelEditor")
        self._output_dir = self._settings.value("output_dir", "") or ""

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter)

        # ── Left: canvas ────────────────────────────────────────────────────
        canvas_widget = QWidget()
        cv_layout = QVBoxLayout(canvas_widget)
        cv_layout.setContentsMargins(0, 0, 0, 0)
        cv_layout.setSpacing(2)

        self._canvas = LevelCanvas()

        toolbar = self._build_toolbar()
        cv_layout.addWidget(toolbar)
        cv_layout.addWidget(self._canvas)
        splitter.addWidget(canvas_widget)

        # ── Right: panels ────────────────────────────────────────────────────
        right = QWidget()
        right.setFixedWidth(280)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(4, 4, 4, 4)
        right_layout.setSpacing(6)

        # Level settings
        settings_box = QGroupBox("Level Settings")
        sf = QFormLayout(settings_box)
        sf.setSpacing(4)
        self._level_name = QLineEdit(self._level.level_name)
        self._level_name.textChanged.connect(lambda t: setattr(self._level, 'level_name', t))
        sf.addRow("Name:", self._level_name)

        self._car_x = _SpinF(self._level.car_x)
        self._car_y = _SpinF(self._level.car_y)
        self._finish_x = _SpinF(self._level.finish_x)
        self._finish_y = _SpinF(self._level.finish_y)
        self._fall_line = _SpinF(self._level.fall_line, -500, 0)
        sf.addRow("Car X:", self._car_x)
        sf.addRow("Car Y:", self._car_y)
        sf.addRow("Finish X:", self._finish_x)
        sf.addRow("Finish Y:", self._finish_y)
        sf.addRow("Fall Line:", self._fall_line)

        self._car_x.valueChanged.connect(self._on_level_settings_changed)
        self._car_y.valueChanged.connect(self._on_level_settings_changed)
        self._finish_x.valueChanged.connect(self._on_level_settings_changed)
        self._finish_y.valueChanged.connect(self._on_level_settings_changed)
        self._fall_line.valueChanged.connect(self._on_level_settings_changed)

        right_layout.addWidget(settings_box)

        # Add shape
        shape_box = QGroupBox("Add Shape")
        sl = QVBoxLayout(shape_box)
        sl.setSpacing(4)
        self._shape_combo = QComboBox()
        for name in SHAPE_PRESETS:
            self._shape_combo.addItem(name)
        sl.addWidget(self._shape_combo)
        add_btn = QPushButton("Place on Canvas")
        add_btn.clicked.connect(self._start_placing)
        sl.addWidget(add_btn)
        right_layout.addWidget(shape_box)

        # Object list
        obj_box = QGroupBox("Objects")
        ol = QVBoxLayout(obj_box)
        ol.setSpacing(4)
        self._obj_list = QListWidget()
        self._obj_list.setMaximumHeight(120)
        self._obj_list.currentRowChanged.connect(self._on_obj_list_select)
        ol.addWidget(self._obj_list)
        del_btn = QPushButton("Delete Selected")
        del_btn.clicked.connect(self._delete_selected)
        ol.addWidget(del_btn)
        right_layout.addWidget(obj_box)

        # Properties
        prop_box = QGroupBox("Properties")
        pl = QVBoxLayout(prop_box)
        pl.setContentsMargins(0, 0, 0, 0)
        self._props = ObjectPropertiesPanel()
        self._props.changed.connect(self._on_props_changed)
        pl.addWidget(self._props)
        right_layout.addWidget(prop_box)

        # Output dir + export
        out_box = QGroupBox("Export")
        el = QVBoxLayout(out_box)
        el.setSpacing(4)
        dir_row = QHBoxLayout()
        self._out_dir_label = QLabel(self._output_dir if self._output_dir else "not set")
        self._out_dir_label.setStyleSheet("color:#888; font-size:11px;")
        self._out_dir_label.setWordWrap(True)
        dir_row.addWidget(self._out_dir_label)
        browse_btn = QPushButton("…")
        browse_btn.setFixedWidth(28)
        browse_btn.clicked.connect(self._browse_output)
        dir_row.addWidget(browse_btn)
        el.addLayout(dir_row)

        # Thumbnail preview + import
        thumb_row = QHBoxLayout()
        self._thumb_preview = QLabel()
        self._thumb_preview.setFixedSize(128, 64)
        self._thumb_preview.setStyleSheet("background:#111; border:1px solid #444;")
        self._thumb_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thumb_preview.setText("auto")
        thumb_row.addWidget(self._thumb_preview)
        thumb_btns = QVBoxLayout()
        import_thumb_btn = QPushButton("Import Image…")
        import_thumb_btn.clicked.connect(self._import_thumbnail)
        thumb_btns.addWidget(import_thumb_btn)
        clear_thumb_btn = QPushButton("Use Auto")
        clear_thumb_btn.clicked.connect(self._clear_thumbnail)
        thumb_btns.addWidget(clear_thumb_btn)
        thumb_row.addLayout(thumb_btns)
        el.addLayout(thumb_row)

        export_btn = QPushButton("Export Level Mod")
        export_btn.clicked.connect(self._export)
        el.addWidget(export_btn)

        # Add image to existing mod
        el.addWidget(QLabel("Add preview to existing mod:"))
        patch_row = QHBoxLayout()
        self._patch_folder = self._settings.value("patch_folder", "") or None
        self._patch_dir_label = QLabel(
            os.path.basename(self._patch_folder) if self._patch_folder else "no folder selected"
        )
        self._patch_dir_label.setStyleSheet("color:#888; font-size:11px;")
        self._patch_dir_label.setWordWrap(True)
        patch_row.addWidget(self._patch_dir_label)
        patch_browse_btn = QPushButton("…")
        patch_browse_btn.setFixedWidth(28)
        patch_browse_btn.clicked.connect(self._browse_patch_folder)
        patch_row.addWidget(patch_browse_btn)
        el.addLayout(patch_row)
        patch_btn = QPushButton("Copy Preview to Mod Folder")
        patch_btn.clicked.connect(self._patch_existing_mod)
        el.addWidget(patch_btn)

        right_layout.addWidget(out_box)

        right_layout.addStretch()
        splitter.addWidget(right)
        splitter.setSizes([700, 280])

        # Wire canvas signals
        self._canvas.object_moved.connect(self._on_object_moved)
        self._canvas.object_double_clicked.connect(self._on_obj_double_click)
        self._canvas.marker_moved.connect(self._on_marker_moved)
        self._canvas.canvas_clicked.connect(self._on_canvas_clicked)

        # Init canvas markers
        self._canvas.set_car_marker(self._level.car_x, self._level.car_y)
        self._canvas.set_finish_marker(self._level.finish_x, self._level.finish_y)
        self._canvas.set_fall_line(self._level.fall_line)
        self._canvas.fit_view()

    # ── Toolbar ──────────────────────────────────────────────────────────────
    def _build_toolbar(self):
        bar = QToolBar()
        bar.setStyleSheet("QToolBar { background: #222; border: none; spacing: 4px; }")

        select_btn = QPushButton("✥ Select")
        select_btn.setCheckable(True)
        select_btn.setChecked(True)
        select_btn.clicked.connect(lambda: self._canvas.cancel_placing())
        bar.addWidget(select_btn)

        fit_btn = QPushButton("⊡ Fit View")
        fit_btn.clicked.connect(self._canvas.fit_view)
        bar.addWidget(fit_btn)

        bar.addSeparator()

        new_btn = QPushButton("🗋 New")
        new_btn.clicked.connect(self._new_level)
        bar.addWidget(new_btn)

        save_btn = QPushButton("💾 Save")
        save_btn.clicked.connect(self._save_level)
        bar.addWidget(save_btn)

        load_btn = QPushButton("📂 Open")
        load_btn.clicked.connect(self._load_level)
        bar.addWidget(load_btn)

        bar.addSeparator()

        hint = QLabel("  Scroll to zoom · Drag to pan · Double-click to select")
        hint.setStyleSheet("color: #666; font-size: 11px;")
        bar.addWidget(hint)

        return bar

    # ── Slots ────────────────────────────────────────────────────────────────
    def _on_level_settings_changed(self):
        self._level.car_x = self._car_x.value()
        self._level.car_y = self._car_y.value()
        self._level.finish_x = self._finish_x.value()
        self._level.finish_y = self._finish_y.value()
        self._level.fall_line = self._fall_line.value()
        self._canvas.set_car_marker(self._level.car_x, self._level.car_y)
        self._canvas.set_finish_marker(self._level.finish_x, self._level.finish_y)
        self._canvas.set_fall_line(self._level.fall_line)

    def _start_placing(self):
        preset_name = self._shape_combo.currentText()
        factory = SHAPE_PRESETS[preset_name]
        # Generate a unique body name
        base = preset_name.split()[0].lower()
        idx = sum(1 for b in self._level.bodies if b.name.startswith(base))
        body_name = f"{base}{idx + 1}"
        body = factory(body_name)
        self._level.add_body(body)
        self._canvas.start_placing(body)

    def _on_canvas_clicked(self, wx, wy):
        body = self._canvas._pending_body
        if body is None:
            return
        obj = ObjectInstance(body, posX=round(wx, 2), posY=round(wy, 2))
        self._level.add_object(obj)
        self._canvas.add_object_item(obj)
        self._refresh_obj_list()
        self._select_object(obj)

    def _on_object_moved(self, obj: ObjectInstance):
        if self._selected_obj is obj:
            self._props._building = True
            self._props._posX.setValue(obj.posX)
            self._props._posY.setValue(obj.posY)
            self._props._building = False

    def _on_obj_double_click(self, obj: ObjectInstance):
        self._select_object(obj)

    def _on_marker_moved(self, marker_type: str, wx: float, wy: float):
        if marker_type == 'car':
            self._level.car_x = round(wx, 2)
            self._level.car_y = round(wy, 2)
            self._car_x.blockSignals(True)
            self._car_y.blockSignals(True)
            self._car_x.setValue(self._level.car_x)
            self._car_y.setValue(self._level.car_y)
            self._car_x.blockSignals(False)
            self._car_y.blockSignals(False)
        elif marker_type == 'finish':
            self._level.finish_x = round(wx, 2)
            self._level.finish_y = round(wy, 2)
            self._finish_x.blockSignals(True)
            self._finish_y.blockSignals(True)
            self._finish_x.setValue(self._level.finish_x)
            self._finish_y.setValue(self._level.finish_y)
            self._finish_x.blockSignals(False)
            self._finish_y.blockSignals(False)

    def _on_obj_list_select(self, row):
        if row < 0 or row >= len(self._level.objects):
            self._props.clear()
            self._selected_obj = None
            return
        obj = self._level.objects[row]
        self._select_object(obj)

    def _on_props_changed(self):
        if self._selected_obj:
            self._canvas.refresh_object_item(self._selected_obj)

    def _select_object(self, obj: ObjectInstance):
        self._selected_obj = obj
        self._props.load(obj)
        # Sync list selection
        idx = self._level.objects.index(obj)
        self._obj_list.blockSignals(True)
        self._obj_list.setCurrentRow(idx)
        self._obj_list.blockSignals(False)

    def _delete_selected(self):
        if self._selected_obj is None:
            return
        self._canvas.remove_object_item(self._selected_obj)
        self._level.remove_object(self._selected_obj)
        self._selected_obj = None
        self._props.clear()
        self._refresh_obj_list()

    def _refresh_obj_list(self):
        self._obj_list.clear()
        for obj in self._level.objects:
            self._obj_list.addItem(f"{obj.body.name} @ ({obj.posX:.1f}, {obj.posY:.1f})")

    # ── Save / Load ──────────────────────────────────────────────────────────
    def _new_level(self):
        if self._level.objects:
            r = QMessageBox.question(self, "New Level",
                "Discard current level and start fresh?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if r != QMessageBox.StandardButton.Yes:
                return
        self._load_level_data(LevelData())

    def _save_level(self):
        start = self._settings.value("last_save_dir", os.path.expanduser("~")) or os.path.expanduser("~")
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Level", start, "JellyMod Level (*.jlvl)")
        if not path:
            return
        if not path.endswith(".jlvl"):
            path += ".jlvl"
        with open(path, 'w', encoding='utf-8') as f:
            f.write(self._level.to_json())
        self._settings.setValue("last_save_dir", os.path.dirname(path))

    def _load_level(self):
        start = self._settings.value("last_save_dir", os.path.expanduser("~")) or os.path.expanduser("~")
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Level", start, "JellyMod Level (*.jlvl)")
        if not path:
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                lv = LevelData.from_json(f.read())
        except Exception as e:
            QMessageBox.critical(self, "Open Level", f"Failed to load:\n{e}")
            return
        self._settings.setValue("last_save_dir", os.path.dirname(path))
        self._load_level_data(lv)

    def _load_level_data(self, lv: LevelData):
        """Replace the current editor state with a new LevelData."""
        # Clear canvas
        for obj in list(self._level.objects):
            self._canvas.remove_object_item(obj)
        self._selected_obj = None
        self._props.clear()
        self._custom_thumb_path = None
        self._thumb_preview.clear()
        self._thumb_preview.setText("auto")

        self._level = lv

        # Rebuild canvas
        for obj in self._level.objects:
            self._canvas.add_object_item(obj)

        # Sync level settings UI
        self._level_name.blockSignals(True)
        self._level_name.setText(lv.level_name)
        self._level_name.blockSignals(False)
        self._car_x.blockSignals(True);  self._car_x.setValue(lv.car_x);   self._car_x.blockSignals(False)
        self._car_y.blockSignals(True);  self._car_y.setValue(lv.car_y);   self._car_y.blockSignals(False)
        self._finish_x.blockSignals(True); self._finish_x.setValue(lv.finish_x); self._finish_x.blockSignals(False)
        self._finish_y.blockSignals(True); self._finish_y.setValue(lv.finish_y); self._finish_y.blockSignals(False)
        self._fall_line.blockSignals(True); self._fall_line.setValue(lv.fall_line); self._fall_line.blockSignals(False)

        self._canvas.set_car_marker(lv.car_x, lv.car_y)
        self._canvas.set_finish_marker(lv.finish_x, lv.finish_y)
        self._canvas.set_fall_line(lv.fall_line)
        self._refresh_obj_list()
        self._canvas.fit_view()

    def _browse_output(self):
        start = self._output_dir or os.path.expanduser("~")
        d = QFileDialog.getExistingDirectory(self, "Output Directory", start)
        if d:
            self._output_dir = d
            self._settings.setValue("output_dir", d)
            self._out_dir_label.setText(d)

    def _import_thumbnail(self):
        start = os.path.dirname(self._custom_thumb_path) if self._custom_thumb_path else \
                self._settings.value("last_thumb_dir", os.path.expanduser("~")) or os.path.expanduser("~")
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Thumbnail", start,
            "Images (*.png *.jpg *.jpeg *.bmp *.webp)")
        if not path:
            return
        self._custom_thumb_path = path
        self._settings.setValue("last_thumb_dir", os.path.dirname(path))
        pix = QPixmap(path).scaled(
            128, 64,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation)
        self._thumb_preview.setPixmap(pix)
        self._thumb_preview.setText("")

    def _clear_thumbnail(self):
        self._custom_thumb_path = None
        self._thumb_preview.clear()
        self._thumb_preview.setText("auto")

    def _browse_patch_folder(self):
        start = self._patch_folder or self._output_dir or os.path.expanduser("~")
        d = QFileDialog.getExistingDirectory(
            self, "Select Existing Mod Folder", start)
        if d:
            self._patch_folder = d
            self._settings.setValue("patch_folder", d)
            self._patch_dir_label.setText(os.path.basename(d))

    def _patch_existing_mod(self):
        if not self._patch_folder:
            QMessageBox.warning(self, "Patch Mod", "Select a mod folder first.")
            return
        if not self._custom_thumb_path:
            QMessageBox.warning(self, "Patch Mod", "Import a preview image first.")
            return
        dest = os.path.join(self._patch_folder, "thumb.png")
        shutil.copy2(self._custom_thumb_path, dest)
        QMessageBox.information(self, "Patch Mod",
            f"Preview image copied to:\n{dest}\n\nThe game will pick it up automatically.")

    # ── Export ───────────────────────────────────────────────────────────────
    def _export(self):
        lv = self._level
        if not lv.level_name.strip():
            QMessageBox.warning(self, "Export", "Please enter a level name.")
            return
        if not lv.objects:
            QMessageBox.warning(self, "Export", "Add at least one object to the level.")
            return

        # Collect only bodies that are actually used
        used_names = {o.body.name for o in lv.objects}
        used_bodies = [b for b in lv.bodies if b.name in used_names]

        if not used_bodies:
            QMessageBox.warning(self, "Export", "No valid body definitions found.")
            return

        if not self._output_dir:
            d = QFileDialog.getExistingDirectory(self, "Choose Output Directory", os.path.expanduser("~"))
            if not d:
                return
            self._output_dir = d
            self._settings.setValue("output_dir", d)
            self._out_dir_label.setText(d)

        folder = os.path.join(self._output_dir, _safe_name(lv.level_name))
        os.makedirs(folder, exist_ok=True)

        # Write .scenec
        scenec_path = os.path.join(folder, "level.scenec")
        write_scenec(
            scenec_path,
            bodies=[b.to_dict() for b in used_bodies],
            objects=[o.to_dict() for o in lv.objects],
            car_name="car_and_truck",
            car_x=lv.car_x, car_y=lv.car_y,
            finish_x=lv.finish_x, finish_y=lv.finish_y,
            fall_line=lv.fall_line,
        )

        # Thumbnail — use imported image if set, otherwise render canvas
        thumb_path = os.path.join(folder, "thumb.png")
        if self._custom_thumb_path:
            shutil.copy2(self._custom_thumb_path, thumb_path)
        else:
            img = self._canvas.render_thumbnail(256, 128)
            img.save(thumb_path)

        # mod.xml
        _write_manifest(folder, {
            "type": "level",
            "name": lv.level_name,
            "file": "level.scenec",
            "thumb": "thumb.png",
        })

        QMessageBox.information(self, "Export", f"Level mod exported to:\n{folder}")
