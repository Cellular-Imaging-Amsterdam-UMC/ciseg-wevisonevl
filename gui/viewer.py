"""One zoomable image canvas with independent instance-label overlays."""
import colorsys
import numpy as np
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QImage, QPainter, QPixmap
from PyQt6.QtWidgets import QGraphicsPixmapItem, QGraphicsScene, QGraphicsView

from .image_data import label_rgba, PROMPT_COLORS


def pixmap(array):
    array = np.ascontiguousarray(array, dtype=np.uint8)
    fmt = QImage.Format.Format_RGBA8888 if array.shape[-1] == 4 else QImage.Format.Format_RGB888
    return QPixmap.fromImage(QImage(array.data, array.shape[1], array.shape[0], array.strides[0], fmt).copy())


class ImageViewer(QGraphicsView):
    pixel_hovered = pyqtSignal(int, int)

    def __init__(self):
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.image_item = QGraphicsPixmapItem()
        self.scene().addItem(self.image_item)
        self.layers = {}
        self.label_arrays = {}
        self.layer_styles = {}
        self.opacity = .45
        self.labels_visible = True
        self.auto_fit = True
        self.setBackgroundBrush(Qt.GlobalColor.black)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        self.setMouseTracking(True)
        self.setMinimumSize(320, 250)

    def set_frame(self, rgb, labels):
        old_shape = (self.image_item.pixmap().height(), self.image_item.pixmap().width())
        for item in self.layers.values():
            self.scene().removeItem(item)
        self.layers.clear()
        self.label_arrays = labels
        self.image_item.setPixmap(pixmap(rgb))
        self.scene().setSceneRect(self.image_item.boundingRect())
        self.ensure_distinct_prompt_colors(labels)
        for index, (name, plane) in enumerate(labels.items()):
            item = QGraphicsPixmapItem(pixmap(label_rgba(plane, index, **self.layer_style(name))))
            item.setOpacity(self.opacity)
            item.setVisible(self.labels_visible)
            item.setZValue(index+1)
            self.scene().addItem(item)
            self.layers[name] = item
        if self.auto_fit or old_shape != rgb.shape[:2]:
            self.fit_image()

    def layer_style(self, name):
        if name not in self.layer_styles:
            self.layer_styles[name] = {'mode': 'single', 'color': PROMPT_COLORS[len(self.layer_styles) % len(PROMPT_COLORS)]}
        return dict(self.layer_styles[name])

    def set_layer_style(self, name, *, mode=None, color=None):
        style = self.layer_style(name)
        if mode is not None:style['mode'] = mode
        if color is not None:style['color'] = color
        # Validate even when the layer is not currently displayed.
        label_rgba(np.zeros((1, 1), np.uint32), mode='single', color=style['color'])
        label_rgba(np.zeros((1, 1), np.uint32), **style)
        self.layer_styles[name] = style
        changed = {name} | self.ensure_distinct_prompt_colors(self.layers, preferred=name)
        for changed_name in changed & self.layers.keys():
            index = list(self.layers).index(changed_name)
            self.layers[changed_name].setPixmap(pixmap(label_rgba(self.label_arrays[changed_name], index, **self.layer_style(changed_name))))

    def ensure_distinct_prompt_colors(self, names, preferred=None):
        """Keep visible single-color prompts distinct, including restored preferences."""
        ordered = list(names)
        if preferred in ordered:
            ordered.remove(preferred); ordered.insert(0, preferred)
        used, changed = set(), set()
        for name in ordered:
            style = self.layer_style(name)
            if style['mode'] != 'single':continue
            color = style['color'].lower()
            if color in used:
                color = next((candidate for candidate in PROMPT_COLORS if candidate not in used), None)
                if color is None:
                    index = len(used)
                    while color is None or color in used:
                        rgb = colorsys.hsv_to_rgb((index*.61803398875) % 1, .7, 1)
                        color = '#%02x%02x%02x' % tuple(round(c*255) for c in rgb)
                        index += 1
                style['color'] = color
                self.layer_styles[name] = style
                changed.add(name)
            used.add(color)
        return changed

    def clear_frame(self):
        for item in self.layers.values():
            self.scene().removeItem(item)
        self.layers.clear()
        self.label_arrays.clear()
        self.image_item.setPixmap(QPixmap())

    def fit_image(self):
        if not self.image_item.pixmap().isNull():
            self.fitInView(self.image_item.boundingRect(), Qt.AspectRatioMode.KeepAspectRatio)
        self.auto_fit = True

    def actual_size(self):
        self.resetTransform()
        self.auto_fit = False

    def set_opacity(self, value):
        self.opacity = value / 100
        for item in self.layers.values():
            item.setOpacity(self.opacity)

    def wheelEvent(self, event):
        current = self.transform().m11()
        factor = 1.2 if event.angleDelta().y() > 0 else 1/1.2
        if .01 <= current*factor <= 128:
            self.scale(factor, factor)
            self.auto_fit = False
        event.accept()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.auto_fit:
            self.fit_image()

    def mouseMoveEvent(self, event):
        point = self.mapToScene(event.position().toPoint())
        self.pixel_hovered.emit(int(np.floor(point.x())), int(np.floor(point.y())))
        super().mouseMoveEvent(event)
