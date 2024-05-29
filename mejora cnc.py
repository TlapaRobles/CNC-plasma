import sys
from PyQt5.QtWidgets import QMainWindow, QLabel, QVBoxLayout, QWidget, QPushButton, QHBoxLayout, QTextEdit, QGroupBox, QGridLayout, QGraphicsView, QGraphicsScene, QFileDialog, QAction, QApplication, QMessageBox, QDialog, QFormLayout, QLineEdit, QDialogButtonBox
from PyQt5.QtCore import Qt, QTimer, QPointF
from PyQt5.QtSvg import QGraphicsSvgItem
from PyQt5.QtGui import QGraphicsEllipseItem
from xml.dom import minidom
import re
import RPi.GPIO as GPIO
import threading

# Configuración de los pines GPIO para el eje X
XDir = 6
XStepPin = 13
XEnable = 5

# Configuración de los pines GPIO para el eje Y
YDir = 16
YStepPin = 20
YEnable = 21

# Configuración del pin GPIO para el relé
RelayPin = 27

STEP_DELAY = 0.001  # Constantes de tiempo para el paso del motor

# Dimensiones de la mesa de trabajo en cm
WORK_AREA_WIDTH = 90
WORK_AREA_HEIGHT = 50

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LinuxCNC-like Interface")
        self.setGeometry(100, 100, 1000, 800)
        
        # Inicializar GPIO
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        self.motor_initialize(XDir, XStepPin, XEnable)
        self.motor_initialize(YDir, YStepPin, YEnable)
        
        # Configurar el pin del relé
        GPIO.setup(RelayPin, GPIO.OUT)
        GPIO.output(RelayPin, GPIO.LOW)  # Inicialmente apagado
        
        # Crear widgets principales
        self.status_label = QLabel("Status: Ready")
        self.status_label.setAlignment(Qt.AlignCenter)
        
        self.control_button_start = QPushButton("Start")
        self.control_button_start.clicked.connect(self.on_start_button_clicked)
        
        self.control_button_stop = QPushButton("Stop")
        self.control_button_stop.clicked.connect(self.on_stop_button_clicked)
        
        self.control_button_pause = QPushButton("Pause")
        self.control_button_pause.clicked.connect(self.on_pause_button_clicked)
        
        self.coordinates_display = QTextEdit()
        self.coordinates_display.setReadOnly(True)
        self.coordinates_display.setText("Coordinates:\nX: 0.0\nY: 0.0\nZ: 0.0")
        
        self.message_display = QTextEdit()
        self.message_display.setReadOnly(True)
        self.message_display.setText("Messages:\nSystem ready.")
        
        # Simulación de coordenadas
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_coordinates)
        
        # Placeholder para visualización gráfica
        self.graphics_view = QGraphicsView()
        self.scene = QGraphicsScene()
        self.graphics_view.setScene(self.scene)
        self.svg_item = None  # Para almacenar el elemento SVG
        
        # Puntero que se mueve
        self.pointer = QGraphicsEllipseItem(-5, -5, 10, 10)
        self.pointer.setBrush(Qt.red)
        self.scene.addItem(self.pointer)
        self.pointer.setZValue(1)  # Asegurarse de que el puntero esté por encima del SVG
        self.path_points = []  # Lista de puntos del camino
        self.current_point_index = 0
        
        # Layout de control
        control_layout = QHBoxLayout()
        control_layout.addWidget(self.control_button_start)
        control_layout.addWidget(self.control_button_pause)
        control_layout.addWidget(self.control_button_stop)
        
        # Grupo de control
        control_group = QGroupBox("Control")
        control_group.setLayout(control_layout)
        
        # Layout de visualización de coordenadas y mensajes
        display_layout = QVBoxLayout()
        display_layout.addWidget(QLabel("Coordinates"))
        display_layout.addWidget(self.coordinates_display)
        display_layout.addWidget(QLabel("Messages"))
        display_layout.addWidget(self.message_display)
        
        # Layout de visualización gráfica
        graphics_layout = QVBoxLayout()
        graphics_layout.addWidget(QLabel("Graphical View"))
        graphics_layout.addWidget(self.graphics_view)
        
        # Layout principal
        main_layout = QGridLayout()
        main_layout.addWidget(self.status_label, 0, 0, 1, 2)
        main_layout.addWidget(control_group, 1, 0, 1, 2)
        main_layout.addLayout(display_layout, 2, 0)
        main_layout.addLayout(graphics_layout, 2, 1)
        
        # Configurar el widget central
        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)
        
        # Añadir acción para cargar SVG
        open_svg_action = QAction('Load SVG', self)
        open_svg_action.triggered.connect(self.load_svg)
        self.menuBar().addAction(open_svg_action)
        
        # Añadir acción para editar SVG
        edit_svg_action = QAction('Edit SVG', self)
        edit_svg_action.triggered.connect(self.edit_svg)
        self.menuBar().addAction(edit_svg_action)
        
        # Evento de teclado
        self.setFocusPolicy(Qt.StrongFocus)
        
    def motor_initialize(self, dir_pin, step_pin, en_pin):
        GPIO.setup(dir_pin, GPIO.OUT)
        GPIO.setup(step_pin, GPIO.OUT)
        GPIO.setup(en_pin, GPIO.OUT)
        GPIO.output(en_pin, GPIO.LOW)  # Activa el motor

    def pulse_motor(self, dir_pin, step_pin, direction, steps, delay):
        GPIO.output(dir_pin, direction)
        
        def send_pulse(step_pin, delay, steps_left):
            if steps_left > 0:
                GPIO.output(step_pin, GPIO.HIGH)
                threading.Timer(delay, GPIO.output, [step_pin, GPIO.LOW]).start()
                threading.Timer(delay * 2, send_pulse, [step_pin, delay, steps_left - 1]).start()
        
        send_pulse(step_pin, delay, steps)
    
    def on_start_button_clicked(self):
        self.status_label.setText("Status: Running")
        self.message_display.append("System started.")
        self.timer.start(100)
        GPIO.output(RelayPin, GPIO.HIGH)  # Encender el relé
        
    def on_stop_button_clicked(self):
        self.status_label.setText("Status: Stopped")
        self.message_display.append("System stopped.")
        self.timer.stop()
        GPIO.output(RelayPin, GPIO.LOW)  # Apagar el relé
        
    def on_pause_button_clicked(self):
        self.status_label.setText("Status: Paused")
        self.message_display.append("System paused.")
        self.timer.stop()
        GPIO.output(RelayPin, GPIO.LOW)  # Apagar el relé
        
    def update_coordinates(self):
        if self.current_point_index < len(self.path_points):
            point = self.path_points[self.current_point_index]
            x, y = point.x(), point.y()
            self.coordinates_display.setText(f"Coordinates:\nX: {x}\nY: {y}\nZ: 0.0")
            self.message_display.append(f"Coordinates updated: X={x}, Y={y}, Z=0.0")
            print(f"Moving pointer to: X={x}, Y={y}")  # Debug: imprimir la posición del puntero
            self.pointer.setPos(point)

            # Controlar los motores según las coordenadas
            steps_x = int(x * 100)  # Convertir cm a pasos (ajustar según la resolución de tu sistema)
            direction_x = GPIO.HIGH if steps_x > 0 else GPIO.LOW
            self.pulse_motor(XDir, XStepPin, direction_x, abs(steps_x), STEP_DELAY)
            
            steps_y = int(y * 100)  # Convertir cm a pasos (ajustar según la resolución de tu sistema)
            direction_y = GPIO.HIGH if steps_y > 0 else GPIO.LOW
            self.pulse_motor(YDir, YStepPin, direction_y, abs(steps_y), STEP_DELAY)
            
            self.current_point_index += 1
        else:
            self.timer.stop()
            GPIO.output(RelayPin, GPIO.LOW)  # Apagar el relé al terminar
    
    def load_svg(self):
        options = QFileDialog.Options()
        file_name, _ = QFileDialog.getOpenFileName(self, "Load SVG", "", "SVG Files (*.svg);;All Files (*)", options=options)
        if file_name:
            # Verificar dimensiones del SVG antes de cargarlo
            if not self.check_svg_dimensions(file_name):
                QMessageBox.warning(self, "Error", "SVG file exceeds work area dimensions (90 cm x 50 cm).")
                return

            if self.svg_item:
                self.scene.removeItem(self.svg_item)
            self.svg_item = QGraphicsSvgItem(file_name)
            self.scene.addItem(self.svg_item)
            self.svg_item.setZValue(0)  # Asegurarse de que el SVG esté por debajo del puntero
            self.message_display.append(f"SVG loaded: {file_name}")
            self.extract_path_points(file_name)
    
    def check_svg_dimensions(self, file_name):
        doc = minidom.parse(file_name)
        svg_element = doc.getElementsByTagName('svg')[0]
        width = svg_element.getAttribute('width')
        height = svg_element.getAttribute('height')
        width = float(width.replace('cm', ''))
        height = float(height.replace('cm', ''))
        doc.unlink()
        return width <= WORK_AREA_WIDTH and height <= WORK_AREA_HEIGHT

    def extract_path_points(self, file_name):
        doc = minidom.parse(file_name)
        path_strings = [path.getAttribute('d') for path in doc.getElementsByTagName('path')]
        for path_string in path_strings:
            print(f"Path string: {path_string}")  # Debug: imprimir el string del camino
            self.parse_path(path_string)
        doc.unlink()
        self.message_display.append(f"Extracted {len(self.path_points)} points from the SVG.")
    
    def parse_path(self, path_string):
        path_commands = re.findall(r'[MmLlHhVvCcSsQqTtAaZz]|-?\d*\.?\d+|-?\d+', path_string)
        current_pos = QPointF(0, 0)
        start_pos = QPointF(0, 0)
        index = 0
        while index < len(path_commands):
            command = path_commands[index]
            if command in 'Mm':
                x = float(path_commands[index + 1])
                y = float(path_commands[index + 2])
                if command == 'm':
                    x += current_pos.x()
                    y += current_pos.y()
                if self.is_within_work_area(x, y):
                    current_pos = QPointF(x, y)
                    start_pos = current_pos
                    self.path_points.append(current_pos)
                index += 3
            elif command in 'Ll':
                x = float(path_commands[index + 1])
                y = float(path_commands[index + 2])
                if command == 'l':
                    x += current_pos.x()
                    y += current_pos.y()
                if self.is_within_work_area(x, y):
                    current_pos = QPointF(x, y)
                    self.path_points.append(current_pos)
                index += 3
            elif command in 'Hh':
                x = float(path_commands[index + 1])
                if command == 'h':
                    x += current_pos.x()
                if self.is_within_work_area(x, current_pos.y()):
                    current_pos.setX(x)
                    self.path_points.append(QPointF(current_pos.x(), current_pos.y()))
                index += 2
            elif command in 'Vv':
                y = float(path_commands[index + 1])
                if command == 'v':
                    y += current_pos.y()
                if self.is_within_work_area(current_pos.x(), y):
                    current_pos.setY(y)
                    self.path_points.append(QPointF(current_pos.x(), current_pos.y()))
                index += 2
            elif command in 'Cc':
                index += 7
            elif command in 'Ss':
                index += 5
            elif command in 'Qq':
                index += 5
            elif command in 'Tt':
                index += 3
            elif command in 'Aa':
                index += 8
            elif command in 'Zz':
                current_pos = start_pos
                if self.is_within_work_area(current_pos.x(), current_pos.y()):
                    self.path_points.append(current_pos)
                index += 1
            else:
                index += 1

    def is_within_work_area(self, x, y):
        if x < 0 or x > WORK_AREA_WIDTH or y < 0 or y > WORK_AREA_HEIGHT:
            self.message_display.append(f"Point ({x}, {y}) is out of work area bounds.")
            return False
        return True

    def edit_svg(self):
        options = QFileDialog.Options()
        file_name, _ = QFileDialog.getOpenFileName(self, "Edit SVG", "", "SVG Files (*.svg);;All Files (*)", options=options)
        if file_name:
            self.edit_svg_dialog(file_name)
    
    def edit_svg_dialog(self, file_name):
        dialog = QDialog(self)
        dialog.setWindowTitle("Edit SVG")
        
        layout = QFormLayout(dialog)
        
        width_edit = QLineEdit(dialog)
        height_edit = QLineEdit(dialog)
        x_edit = QLineEdit(dialog)
        y_edit = QLineEdit(dialog)
        
        layout.addRow("Width (cm):", width_edit)
        layout.addRow("Height (cm):", height_edit)
        layout.addRow("Start X (cm):", x_edit)
        layout.addRow("Start Y (cm):", y_edit)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal, dialog)
        buttons.accepted.connect(lambda: self.apply_svg_edits(file_name, width_edit.text(), height_edit.text(), x_edit.text(), y_edit.text()))
        buttons.rejected.connect(dialog.reject)
        
        layout.addWidget(buttons)
        
        dialog.setLayout(layout)
        dialog.exec_()

    def apply_svg_edits(self, file_name, width, height, start_x, start_y):
        doc = minidom.parse(file_name)
        svg_element = doc.getElementsByTagName('svg')[0]
        
        # Ajustar dimensiones del SVG
        if width:
            svg_element.setAttribute('width', f"{width}cm")
        if height:
            svg_element.setAttribute('height', f"{height}cm")
        
        # Ajustar punto de inicio
        for path in svg_element.getElementsByTagName('path'):
            path.setAttribute('transform', f"translate({start_x},{start_y})")
        
        with open(file_name, 'w') as f:
            doc.writexml(f)
        
        doc.unlink()
        
        self.message_display.append(f"SVG edited and saved: {file_name}")
        self.load_svg()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Left:
            self.move_motor(XDir, XStepPin, GPIO.LOW, 1)
        elif event.key() == Qt.Key_Right:
            self.move_motor(XDir, XStepPin, GPIO.HIGH, 1)
        elif event.key() == Qt.Key_Up:
            self.move_motor(YDir, YStepPin, GPIO.HIGH, 1)
        elif event.key() == Qt.Key_Down:
            self.move_motor(YDir, YStepPin, GPIO.LOW, 1)
        event.accept()
    
    def move_motor(self, dir_pin, step_pin, direction, steps):
        self.pulse_motor(dir_pin, step_pin, direction, steps, STEP_DELAY)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
