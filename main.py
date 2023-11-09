import sys
import os
from os import path

from PyQt5.QtWidgets import QApplication, QMainWindow, QFileDialog, \
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox
from PyQt5.QtCore import Qt, QEvent, QObject, QCoreApplication, QTimer
from PyQt5 import QtGui
from PyQt5.QtGui import QIcon
from PyQt5 import QtCore

import win32gui
import win32ui
import win32con

import io
import win32clipboard
from PIL import Image
import keyboard
import time
import pytesseract
import threading
import asyncio
import websockets
import cv2
import pyautogui
import numpy as np

async def send_image_and_receive_text(region):
    async with websockets.connect("ws://0.0.0.0:8765") as websocket:
        screenshot = pyautogui.screenshot(region=region)
        screenshot.save(os.path.dirname(os.path.realpath(__file__)) + "\\png.png")
        with open(os.path.dirname(os.path.realpath(__file__)) + "\\png.png", "rb") as file:
            file_data = file.read()

        await websocket.send(file_data)

        response = await websocket.recv()
        return response

class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super(MainWindow, self).__init__()

        self.mouse_relative_position_x = 0
        self.mouse_relative_position_y = 0
        self.button_window_height = 50
        self.region_x_pos = 0
        self.region_y_pos = 0
        self.region_width = 0
        self.region_height = 0
        self.screen_shoot_path = ""

        self.setWindowFlags(Qt.FramelessWindowHint)
        
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.button_window = ButtonWindow()

        self.button_window.button_close.clicked.connect(self.hide)

        self.button_window.button_save.clicked.connect(self.get_screen_region_and_open_save_file_dialog)

        self.button_window.button_clipboard.clicked.connect(self.get_screen_region_and_hide_windows)

        self.timer = QTimer(self)

        self.mouse_mode = 0

        widget_stylesheet = "QWidget#central_widget {" \
                            "border-color: rgba(255, 0, 0, 255);" \
                            "border-left-color: rgba(255, 0, 0, 255);" \
                            "border-right-color: rgba(255, 0, 0, 255);" \
                            "border-bottom-color: rgba(255, 0, 0, 255);" \
                            "border-style: dashed;" \
                            "border-top-width: 4px;" \
                            "border-left-width: 4px;" \
                            "border-right-width: 4px;" \
                            "border-bottom-width: 4px;" \
                            "border-radius: 4px;" \
                            "background-color: rgba(255, 255, 255, 2);" \
                            "}"

        self.central_widget = QWidget(self)
        self.central_widget.setStyleSheet(widget_stylesheet)
        self.central_widget.setMouseTracking(True)
        self.central_widget.installEventFilter(self)
        self.central_widget.setObjectName("central_widget")

        self.setCentralWidget(self.central_widget)

        screen_width = QApplication.primaryScreen().size().width()
        screen_height = QApplication.primaryScreen().size().height()
        self.setGeometry(int(screen_width / 2) - int(self.geometry().width() / 2),
                         int(screen_height / 2) - int(self.geometry().height() / 2),
                         400,
                         300)

        file_name = os.path.dirname(os.path.realpath(__file__)) + "\\icon.png"
        if path.exists(file_name):
            self.setWindowIcon(QIcon(file_name))

        self.setMinimumSize(100, 100)

    def hideEvent(self, event):
        self.hide()
        self.button_window.hide()

    def open_save_file_dialog(self) -> str:
        current_directory = os.path.dirname(os.path.realpath(__file__))

        # filter = "text files (*.jpg *.JPG)"
        filter = "text files (*.bmp *.BMP)"

        path_file_name = QFileDialog.getSaveFileName(self, 'Choose where to save the screen capture image',
                                                     current_directory, filter)[0]
        return path_file_name

    @QtCore.pyqtSlot()
    def get_screen_region_and_open_save_file_dialog(self) -> None:
        self.region_x_pos = self.x()
        self.region_y_pos = self.y()
        self.region_width = self.width()
        self.region_height = self.height()
        self.screen_shoot_path = self.open_save_file_dialog()
        self.hide()
        self.button_window.hide()
        self.timer.singleShot(500, self.save_screen_region_to_file_and_show_windows)

    @QtCore.pyqtSlot()
    def save_screen_region_to_file_and_show_windows(self) -> None:
        if len(self.screen_shoot_path) > 0:
            self.save_screen_region_to_file(self.region_x_pos, self.region_y_pos,
                                            self.region_width, self.region_height, self.screen_shoot_path)
        self.show()
        self.button_window.show()
        self.button_window.activateWindow()
        self.button_window.raise_()

    @staticmethod
    def save_screen_region_to_file(x: int, y: int, width: int, height: int, full_path_and_image: str):
        """
        This method save a screenshot of passed screen area. It uses the win32gui library
        to be able to grab a screen area in any of the desktops available, if more than one.
        :param x:               Upper-left corner X position of selected screen area.
        :param y:               Upper-left corner Y position of selected screen area.
        :param width:           Width of selected screen area.
        :param height:          Height of selected screen area.
        :param full_path_and_image:    Path and name of the file used to save the image.
        :return:                Nothing.
        """
        desktop_window = win32gui.GetDesktopWindow()
        window_device_context = win32gui.GetWindowDC(desktop_window)
        img_dc = win32ui.CreateDCFromHandle(window_device_context)
        mem_dc = img_dc.CreateCompatibleDC()
        screenshot = win32ui.CreateBitmap()
        screenshot.CreateCompatibleBitmap(img_dc, width, height)
        mem_dc.SelectObject(screenshot)
        mem_dc.BitBlt((0, 0), (width, height), img_dc, (x, y), win32con.SRCCOPY)
        screenshot.SaveBitmapFile(mem_dc, full_path_and_image)
        img_dc.DeleteDC()
        mem_dc.DeleteDC()
        win32gui.DeleteObject(screenshot.GetHandle())

    @staticmethod
    def copy_image_from_file_to_clipboard(full_path_and_image: str) -> None:
        image = Image.open(full_path_and_image)
        output = io.BytesIO()
        image.convert(mode="RGB").save(output, format="BMP")
        data = output.getvalue()[14:]
        output.close()
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
        win32clipboard.CloseClipboard()

    @QtCore.pyqtSlot()
    def get_screen_region_and_hide_windows(self) -> None:
        self.region_x_pos = self.x()
        self.region_y_pos = self.y()
        self.region_width = self.width()
        self.region_height = self.height()
        self.hide()
        self.button_window.hide()
        self.timer.singleShot(500, self.copy_screen_region_to_clipboard_and_show_windows)

    @QtCore.pyqtSlot()
    def copy_screen_region_to_clipboard_and_show_windows(self) -> None:
        self.copy_screen_region_to_clipboard(self.region_x_pos, self.region_y_pos,
                                             self.region_width, self.region_height)
        self.show()
        self.button_window.show()
        self.button_window.activateWindow()
        self.button_window.raise_()

    @staticmethod
    def copy_screen_region_to_clipboard(x: int, y: int, width: int, height: int) -> None:
        """
        Get an image from a screen region and put it in the clipboard as an image.
        :param x:       Region upper-left corner x coordinate.
        :param y:       Region upper-left corner y coordinate.
        :param width:   Region width dimension.
        :param height:  Region height dimension.
        :return:        None.
        """
        desktop_window = win32gui.GetDesktopWindow()
        window_device_context = win32gui.GetWindowDC(desktop_window)
        img_dc = win32ui.CreateDCFromHandle(window_device_context)
        mem_dc = img_dc.CreateCompatibleDC()
        screenshot = win32ui.CreateBitmap()
        screenshot.CreateCompatibleBitmap(img_dc, width, height)
        mem_dc.SelectObject(screenshot)
        mem_dc.BitBlt((0, 0), (width, height), img_dc, (x, y), win32con.SRCCOPY)

        bmpinfo = screenshot.GetInfo()
        bmpstr = screenshot.GetBitmapBits(True)
        screenshot_image = Image.frombuffer('RGB',
                                            (bmpinfo['bmWidth'], bmpinfo['bmHeight']),
                                            bmpstr, 'raw', 'BGRX', 0, 1)

        img_dc.DeleteDC()
        mem_dc.DeleteDC()
        win32gui.DeleteObject(screenshot.GetHandle())

        output = io.BytesIO()
        screenshot_image.convert(mode="RGB").save(output, format="BMP")
        text = asyncio.get_event_loop().run_until_complete(send_image_and_receive_text(region=(x+4, y+4, width-8, height-8)))
        #pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract'
        #text = pytesseract.image_to_string(screenshot_image)
        #data = output.getvalue()[14:]
        output.close()
        
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32clipboard.CF_UNICODETEXT, text)
        #win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
        win32clipboard.CloseClipboard()

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self.mouse_relative_position_x = event.pos().x()
            self.mouse_relative_position_y = event.pos().y()
            event.accept()
        else:
            event.ignore()

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            QApplication.setOverrideCursor(Qt.ArrowCursor)
            self.mouse_mode = 0
            event.accept()
        else:
            event.ignore()

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        """
        This method will be called every time the main window is resized.
        It is used to resize the button window to match the width of the
        main window.
        :param event: Resize event object.
        :return: Nothing.
        """
        self.button_window.setGeometry(self.x(),
                                       self.y() + self.height(),
                                       self.width(),
                                       self.button_window_height)
        QMainWindow.resizeEvent(self, event)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:

        if event.type() == QEvent.MouseMove:
            pos = event.pos()

            self.button_window.show()
            self.button_window.activateWindow()
            self.button_window.raise_()

            if event.buttons() == Qt.NoButton:
                
                if pos.x() > self.width() - 5 and pos.y() > self.height() - 5:
                    QApplication.setOverrideCursor(Qt.SizeFDiagCursor)
                elif pos.x() < 5 and pos.y() < 5:
                    QApplication.setOverrideCursor(Qt.SizeFDiagCursor)
                elif pos.x() > self.width() - 5 and pos.y() < 5:
                    QApplication.setOverrideCursor(Qt.SizeBDiagCursor)
                elif pos.x() < 5 and pos.y() > self.height() - 5:
                    QApplication.setOverrideCursor(Qt.SizeBDiagCursor)
                elif pos.x() > self.width() - 5 or pos.x() < 5:
                    QApplication.setOverrideCursor(Qt.SizeHorCursor)
                elif pos.y() > self.height() - 5 or pos.y() < 5:
                    QApplication.setOverrideCursor(Qt.SizeVerCursor)
                else:
                    QApplication.setOverrideCursor(Qt.ArrowCursor)

            if event.buttons() & Qt.LeftButton:

                if pos.x() > self.width() - 10 and pos.y() > self.height() - 10 \
                        and (self.mouse_mode == 0 or self.mouse_mode == 1):
                    self.mouse_mode = 1
                    QApplication.setOverrideCursor(Qt.SizeFDiagCursor)
                    self.setGeometry(self.x(), self.y(), pos.x(), pos.y())

                elif pos.x() < 10 and pos.y() < 10 \
                        and (self.mouse_mode == 0 or self.mouse_mode == 2):
                    self.mouse_mode = 2
                    QApplication.setOverrideCursor(Qt.SizeFDiagCursor)
                    self.setGeometry(self.x() + pos.x(), self.y() + pos.y(),
                                     self.width() - pos.x(), self.height() - pos.y())

                elif pos.x() > self.width() - 10 and pos.y() < 10 \
                        and (self.mouse_mode == 0 or self.mouse_mode == 3):
                    self.mouse_mode = 3
                    QApplication.setOverrideCursor(Qt.SizeBDiagCursor)
                    self.setGeometry(self.x(), self.y() + pos.y(),
                                     pos.x(), self.height() - pos.y())

                elif pos.x() < 10 and pos.y() > self.height() - 10 \
                        and (self.mouse_mode == 0 or self.mouse_mode == 4):
                    self.mouse_mode = 4
                    QApplication.setOverrideCursor(Qt.SizeBDiagCursor)
                    self.setGeometry(self.x() + pos.x(), self.y(),
                                     self.width() - pos.x(), pos.y())

                elif pos.x() > self.width() - 5 and 0 < pos.y() < self.height() \
                        and (self.mouse_mode == 0 or self.mouse_mode == 5):
                    self.mouse_mode = 5
                    QApplication.setOverrideCursor(Qt.SizeHorCursor)
                    self.setGeometry(self.x(), self.y(), pos.x(), self.height())

                elif pos.x() < 5 and 0 < pos.y() < self.height() \
                        and (self.mouse_mode == 0 or self.mouse_mode == 6):
                    self.mouse_mode = 6
                    QApplication.setOverrideCursor(Qt.SizeHorCursor)
                    if self.width() - pos.x() > self.minimumWidth():
                        self.setGeometry(self.x() + pos.x(), self.y(), self.width() - pos.x(), self.height())

                elif pos.y() > self.height() - 5 and 0 < pos.x() < self.width() \
                        and (self.mouse_mode == 0 or self.mouse_mode == 7):
                    self.mouse_mode = 7
                    QApplication.setOverrideCursor(Qt.SizeVerCursor)
                    self.setGeometry(self.x(), self.y(), self.width(), pos.y())

                elif pos.y() < 5 and 0 < pos.x() < self.width() \
                        and (self.mouse_mode == 0 or self.mouse_mode == 8):
                    self.mouse_mode = 8
                    QApplication.setOverrideCursor(Qt.SizeVerCursor)
                    if self.height() - pos.y() > self.minimumHeight():
                        self.setGeometry(self.x(), self.y() + pos.y(), self.width(), self.height() - pos.y())

                elif 10 < pos.x() < self.width() - 10 and 10 < pos.y() < self.height() - 10 \
                        and (self.mouse_mode == 0 or self.mouse_mode == 9):
                    self.mouse_mode = 9
                    QApplication.setOverrideCursor(Qt.SizeAllCursor)
                    self.move(event.globalPos().x() - self.mouse_relative_position_x,
                              event.globalPos().y() - self.mouse_relative_position_y)
                    self.button_window.setGeometry(self.x(),
                                                   self.y() + self.height(),
                                                   self.width(),
                                                   self.button_window_height)
                else:
                    QApplication.setOverrideCursor(Qt.ArrowCursor)

        elif event.type() == QEvent.Show:
            self.button_window.setGeometry(self.x(),
                                           self.y() + self.height(),
                                           self.width(),
                                           self.button_window_height)
            self.button_window.show()

        elif event.type() == QEvent.Hide:
            while True:
                time.sleep(0.2)
                if keyboard.is_pressed("win+alt+s"):
                    self.show()
                    self.button_window.show()
                    break
        else:
            # return super(MainWindow, self).eventFilter(watched, event)
            return False

        self.central_widget.update()
        QCoreApplication.processEvents()

        return True


class ButtonWindow(QWidget):
    def __init__(self) -> None:
        super(ButtonWindow, self).__init__()

        
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.SubWindow)
        self.setAttribute(Qt.WA_TranslucentBackground)

        widget_stylesheet = "QWidget#button_window {" \
                            "background-color: rgba(255, 255, 255, 2);" \
                            "}"

        button_stylesheet = "QPushButton {" \
                            "color: rgb(255, 255, 255);" \
                            "font: 75 10pt FreeSans;" \
                            "background-color: rgba(6, 104, 249, 255);" \
                            "border-top-color: rgba(151, 222, 247, 255);" \
                            "border-left-color: rgba(151, 222, 247, 255);" \
                            "border-right-color: rgba(4, 57, 135, 255);" \
                            "border-bottom-color: rgba(4, 57, 135,255);" \
                            "border-style: inset;" \
                            "border-top-width: 2px;" \
                            "border-left-width: 2px;" \
                            "border-right-width: 3px;" \
                            "border-bottom-width: 3px;" \
                            "border-radius: 5px;" \
                            "}"

        self.button_save = QPushButton("Save to File")
        self.button_save.setFixedSize(85, 30)
        self.button_save.setMouseTracking(True)
        self.button_save.installEventFilter(self)

        self.button_clipboard = QPushButton("Copy to Clipboard")
        self.button_clipboard.setFixedSize(100, 30)
        self.button_clipboard.setMouseTracking(True)
        self.button_clipboard.installEventFilter(self)
        # self.button_clipboard.setStyleSheet(button_stylesheet)

        self.button_close = QPushButton("Close")
        self.button_close.setFixedSize(85, 30)
        self.button_close.setMouseTracking(True)
        self.button_close.installEventFilter(self)
        # self.button_close.setStyleSheet(button_stylesheet)

        horizontal_layout = QHBoxLayout()
        horizontal_layout.addStretch(1)
        horizontal_layout.addWidget(self.button_save)
        horizontal_layout.addStretch(1)
        horizontal_layout.addWidget(self.button_clipboard)
        horizontal_layout.addStretch(1)
        horizontal_layout.addWidget(self.button_close)
        horizontal_layout.addStretch(1)

        vert_layout = QVBoxLayout()
        vert_layout.addStretch(1)
        vert_layout.addLayout(horizontal_layout)
        vert_layout.addStretch(1)

        self.setLayout(vert_layout)
        self.setStyleSheet(widget_stylesheet)
        self.setObjectName("button_window")

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.MouseMove:
            QApplication.setOverrideCursor(Qt.ArrowCursor)
            return True
        else:
            return False


def main():
    app = QApplication([])
    window = MainWindow()
    window.show()
    window.hide()
    
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
