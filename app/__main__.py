#!/usr/bin/env python3

import sys
import os
import zmq
import time
from PyQt5 import QtWidgets as W, QtCore as C, QtGui as G
from app.bus import Pub, Push
from app.background import Background


class View(W.QMainWindow):
    def __init__(self):
        super().__init__()

        self.context = zmq.Context(1)

        self.command = Push(self.context, 'command')
        self.model = Model(self.context)
        self.control = Control(self.model)

        self.setGeometry(500, 200, 400, 300)
        self.setWindowTitle('Qt + ZMQ Test')
        self.setup_layout()
        self.setup_model_event_handler()
        self.setup_control_event_handler()

        self.show()
    
    def setup_layout(self):
        vbox = W.QVBoxLayout()
        vbox.setAlignment(C.Qt.AlignTop)

        self.state_label = W.QLabel()
        self.state_label.setText(self.model.state)
        vbox.addWidget(self.state_label)

        self.buttons = []
        for state in ('A', 'B', 'C'):
            button = W.QPushButton(state)
            button.clicked.connect(self.on_set_state)
            vbox.addWidget(button)
            self.buttons.append(button)

        base = W.QWidget(self)
        base.setLayout(vbox)
        self.setCentralWidget(base)

    def setup_model_event_handler(self):
        self.model_event_handler = ModelEventHandler.as_thread(
            self.model.event.subscriber('state', 'system', 'error'))
        self.model_event_handler.message.connect(self.on_message)
        self.model_event_handler.error.connect(self.on_error)

    def setup_control_event_handler(self):
        self.control_event_handler = ControlEventHandler.as_thread(self.control, self.command.puller())
        self.control_event_handler.enable.connect(self.on_enable)

    def on_set_state(self):
        new_state = self.sender().text()
        self.command.send({'command': 'set_state', 'state': new_state})

    def on_message(self, state):
        self.state_label.setText(state)
    
    def on_error(self, message):
        W.QMessageBox.information(self, 'Error', message)
    
    def on_enable(self, enabled):
        for button in self.buttons:
            button.setEnabled(enabled)

    def closeEvent(self, event):
        self.model.send_system('quit')
        self.command.send({'command': 'quit'})


class ModelEventHandler(Background):
    message = C.pyqtSignal(str)
    error = C.pyqtSignal(str)

    def on_state(self, message):
        self.message.emit(message)
    
    def on_system(self, message):
        if message == 'quit':
            self.running = False
            self.quit_and_wait()

    def on_error(self, message):
        self.error.emit(message)


class ControlEventHandler(Background):
    enable = C.pyqtSignal(bool)

    def __init__(self, control, *args):
        super().__init__(*args)

        self.control = control
        self.running = True
    
    def on_message(self, message):
        if message['command'] == 'set_state':
            self.enable.emit(False)
            try:
                self.control.set_state(message['state'])
            except ValueError as e:
                self.control.model.send_error(str(e))
            finally:
                self.enable.emit(True)
        elif message['command'] == 'quit':
            self.running = False


class Control:
    def __init__(self, model):
        self.model = model
    
    def set_state(self, new_state):
        old_state = self.model.state
        print("set_state", new_state)

        time.sleep(1)

        if (old_state, new_state) == ('A', 'B'):
            self.model.state = new_state
        elif (old_state, new_state) == ('B', 'C'):
            self.model.state = new_state
        elif (old_state, new_state) == ('C', 'A'):
            self.model.state = new_state
        else:
            raise ValueError(f'Invalid transition: {old_state} -> {new_state}')


class Model:
    def __init__(self, zmq_context: zmq.Context):
        self._state = 'A'
        self.event = Pub(zmq_context, 'events')
    
    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, new_state):
        self._state = new_state
        self.event.send('state', self._state)
    
    def send_system(self, message):
        self.event.send('system', message)
    
    def send_error(self, message):
        self.event.send('error', message)


if __name__ == '__main__':
    app = W.QApplication(sys.argv)
    if len(sys.argv) > 1:
        main = View()
    else:
        main = View()
    sys.exit(app.exec_())