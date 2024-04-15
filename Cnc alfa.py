import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QGraphicsView, QGraphicsScene, QFileDialog, QGraphicsEllipseItem,QSizePolicy
from PyQt5.QtCore import Qt, QRectF, QPointF, QPoint
from PyQt5.QtGui import QWheelEvent ,QIcon, QPixmap

import svgpathtools


class CNCPlasmaWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Control CNC")
        self.setGeometry(100, 100, 800, 600)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self.layout = QHBoxLayout()
        self.central_widget.setLayout(self.layout)

        self.init_ui()

    def init_ui(self):
        #  mapa cartesiano
        self.map_view = QGraphicsView()
        self.map_scene = QGraphicsScene()
        self.map_view.setScene(self.map_scene)
        self.layout.addWidget(self.map_view)

        # Botones de control
        control_layout = QVBoxLayout()

        self.start_button = QPushButton("Iniciar")
        self.stop_button = QPushButton("Detener")
        self.emergency_button = QPushButton("Paro de emergencia")
        self.load_svg_button = QPushButton("Cargar imagen")
        self.zoom_in_button = QPushButton("Zoom +")
        self.zoom_out_button = QPushButton("Zoom -")

        control_layout.addWidget(self.start_button)
        control_layout.addWidget(self.stop_button)
        control_layout.addWidget(self.emergency_button)
        control_layout.addWidget(self.load_svg_button)
        control_layout.addWidget(self.zoom_in_button)
        control_layout.addWidget(self.zoom_out_button)

        # Botones de desplazamiento del puntero
        self.move_up_button = QPushButton("^")
        self.move_down_button = QPushButton("v")
        self.move_left_button = QPushButton("<")
        self.move_right_button = QPushButton(">")

        # Ajustar tamaño de los botones
        button_size_policy = QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.move_up_button.setSizePolicy(button_size_policy)
        self.move_down_button.setSizePolicy(button_size_policy)
        self.move_left_button.setSizePolicy(button_size_policy)
        self.move_right_button.setSizePolicy(button_size_policy)

        # Agregar los botones al layout
        control_layout.addWidget(self.move_up_button)
        h_layout = QHBoxLayout()
        h_layout.addWidget(self.move_left_button)
        h_layout.addWidget(self.move_down_button)
        h_layout.addWidget(self.move_right_button)
        control_layout.addLayout(h_layout)


        self.layout.addLayout(control_layout)

    

        #  botones a funciones
        self.start_button.clicked.connect(self.start_cnc)
        self.stop_button.clicked.connect(self.stop_cnc)
        self.emergency_button.clicked.connect(self.emergency_stop)
        self.load_svg_button.clicked.connect(self.load_svg)
        self.zoom_in_button.clicked.connect(self.zoom_in)
        self.zoom_out_button.clicked.connect(self.zoom_out)

        # Crear el puntero
        self.pointer_item = QGraphicsEllipseItem(-5, -5, 10, 10)
        self.pointer_item.setBrush(Qt.red)
        self.map_scene.addItem(self.pointer_item)
        self.pointer_pos = QPointF(0, 0)  # Posición inicial del puntero

    def move_pointer(self, dx, dy):
        new_x = self.pointer_pos.x() + dx
        new_y = self.pointer_pos.y() + dy
        self.pointer_pos.setX(new_x)
        self.pointer_pos.setY(new_y)
        self.pointer_item.setPos(self.pointer_pos)

    def start_cnc(self):
        print("Iniciando corte ...")

    def stop_cnc(self):
        print("Detener trabajo...")

    def emergency_stop(self):
        print("Paro de emergencia activado!")

    def load_svg(self):
        file_dialog = QFileDialog(self)
        file_dialog.setNameFilter("SVG archivo (*.svg)")
        file_dialog.setViewMode(QFileDialog.Detail)
        file_path, _ = file_dialog.getOpenFileName()

        if file_path:
            self.draw_svg(file_path)

    def draw_svg(self, file_path):
        self.map_scene.clear()
        paths, _ = svgpathtools.svg2paths(file_path)
        min_x = float('inf')
        min_y = float('inf')
        max_x = float('-inf')
        max_y = float('-inf')
        for path in paths:
            for segment in path:
                if isinstance(segment, svgpathtools.Line):
                    start = segment.start
                    end = segment.end
                    min_x = min(min_x, start.real, end.real)
                    max_x = max(max_x, start.real, end.real)
                    min_y = min(min_y, start.imag, end.imag)
                    max_y = max(max_y, start.imag, end.imag)
                elif isinstance(segment, svgpathtools.CubicBezier):
                    points = segment.bpoints()
                    for point in points:
                        min_x = min(min_x, point.real)
                        max_x = max(max_x, point.real)
                        min_y = min(min_y, point.imag)
                        max_y = max(max_y, point.imag)
        width = max_x - min_x
        height = max_y - min_y
        view_rect = QRectF(min_x, -max_y, width, height)
        self.map_scene.setSceneRect(view_rect)

       

        for path in paths:
            for segment in path:
                if isinstance(segment, svgpathtools.Line):
                    start = segment.start
                    end = segment.end
                    self.map_scene.addLine(start.real, -start.imag, end.real, -end.imag, pen=Qt.black)
                elif isinstance(segment, svgpathtools.CubicBezier):
                    start = segment.start
                    control1 = segment.control1
                    control2 = segment.control2
                    end = segment.end

                    num_segments = 20
                    for i in range(num_segments):
                        t0 = i / num_segments
                        t1 = (i + 1) / num_segments
                        start_point = segment.point(t0)
                        end_point = segment.point(t1)
                        self.map_scene.addLine(start_point.real, -start_point.imag, end_point.real, -end_point.imag,pen=Qt.black)

    def zoom_in(self):
        self.map_view.scale(1.1, 1.1)

    def zoom_out(self):
        self.map_view.scale(0.9, 0.9)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CNCPlasmaWindow()
    window.show()
    sys.exit(app.exec_())
