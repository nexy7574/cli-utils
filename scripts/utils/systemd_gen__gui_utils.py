# Hello anyone reading this code
# This is my... second? ever GUI project.
# Don't take inspiration from this
# I abuse QGridLayout, and it doesn't even look that amazing
# Furthermore, the input validation here is poorer than me.
# I also wrote this while hysterical and vibing way too hard to songs that gave me way too much energy
# If this works reliably, I will start being religious
import os
import sys
import pwd
from typing import Literal
from scripts.utils.generic__size import convert_soft_data_value_to_hard_data_value, CAPACITY_REGEX_RAW

from PyQt5.QtCore import (
    Qt,
    pyqtSignal,
    QRunnable,
    QThreadPool,
    pyqtSlot,
    QMetaObject,
    QObject,
    Q_ARG,
    QRegExp,
)
# WHAT IS HALF OF THIS???
from PyQt5.QtGui import QIntValidator, QTextCursor, QRegExpValidator
from PyQt5.QtWidgets import (
    QTextEdit,
    QWidget,
    QGridLayout,
    QPushButton,
    QCheckBox,
    QMessageBox,
    QTextBrowser,
    QApplication,
    QLabel,
    QComboBox,
    QLineEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QGroupBox
)
# Why don't I just `import *`? Because I'm f*cking insane apparently.
# PyQt (Qt in general) scares me.

UNIT_TYPES = ["simple", "exec", "forking", "oneshot", "dbus", "notify", "idle"]  # I wish this code was _[0]


class RAMResourceLimitSubWidgetSubWidget(QWidget):  # who in their right mind writes a class name like this
    def __init__(self):
        super().__init__()

        layout = QGridLayout()

        min_memory_label = QLabel("Reserved RAM")
        self.min_memory_input = QLineEdit()
        self.min_memory_input.setPlaceholderText(f"e.g. 100M, 1G, 1536M (1.5G)")
        self.min_memory_input.setValidator(QRegExpValidator(QRegExp(CAPACITY_REGEX_RAW)))
        layout.addWidget(min_memory_label, 0, 0)
        layout.addWidget(self.min_memory_input, 0, 1)
        max_memory_label = QLabel("Max RAM")
        self.max_memory_input = QLineEdit()
        self.max_memory_input.setPlaceholderText(f"e.g. 100M, 1G, 1536M (1.5G)")
        self.max_memory_input.setValidator(QRegExpValidator(QRegExp(CAPACITY_REGEX_RAW)))
        layout.addWidget(max_memory_label, 1, 0)
        layout.addWidget(self.max_memory_input, 1, 1)

        pressure_memory_label = QLabel("RAM high pressure level")
        self.pressure_memory_input = QLineEdit()
        self.pressure_memory_input.setPlaceholderText(f"e.g. 100M, 1G, 1536M (1.5G)")
        self.pressure_memory_input.setValidator(QRegExpValidator(QRegExp(CAPACITY_REGEX_RAW)))
        layout.addWidget(pressure_memory_label, 2, 0)
        layout.addWidget(self.pressure_memory_input, 2, 1)

        self.setVisible(False)
        self.setLayout(layout)


class CPUResourceLimitSubWidgetSubWidget(QWidget):
    def __init__(self):
        super().__init__()

        layout = QGridLayout()

        cpu_quota_label = QLabel("CPU Quota (%, 100=1 core)")
        self.cpu_quota_input = QLineEdit()
        self.cpu_quota_input.setPlaceholderText(f"Between 1 and {100 * os.cpu_count()}")
        _validator = QIntValidator()
        _validator.setRange(1, 100 * os.cpu_count())
        self.cpu_quota_input.setValidator(_validator)
        layout.addWidget(cpu_quota_label, 0, 0)
        layout.addWidget(self.cpu_quota_input, 0, 1)

        self.setVisible(False)
        self.setLayout(layout)


class ResourceLimitSubWidget(QWidget):
    def __init__(self):
        super().__init__()

        layout = QGridLayout()

        self.cpu_resource_sub = CPUResourceLimitSubWidgetSubWidget()
        self.ram_resource_sub = RAMResourceLimitSubWidgetSubWidget()

        self.enable_cpu_limiting_box = QCheckBox("Enable CPU limits")
        self.enable_ram_limiting_box = QCheckBox("Enable RAM limits")

        # noinspection PyUnresolvedReferences
        self.enable_cpu_limiting_box.stateChanged.connect(
            lambda state: self.cpu_resource_sub.setVisible(state == Qt.Checked)
        )
        # noinspection PyUnresolvedReferences
        self.enable_ram_limiting_box.stateChanged.connect(
            lambda state: self.ram_resource_sub.setVisible(state == Qt.Checked)
        )

        layout.addWidget(self.enable_cpu_limiting_box, 0, 0)
        layout.addWidget(self.cpu_resource_sub, 0, 1)
        layout.addWidget(self.enable_ram_limiting_box, 1, 0)
        layout.addWidget(self.ram_resource_sub, 1, 1)

        self.setLayout(layout)


class FirstQuestions(QWidget):
    def __init__(self):
        super().__init__()
        # Beware: bullshit ahead
        ALL_USERS = pwd.getpwall()
        self.opts = {
            "name": None,
            "description": None,
            "unit_type": None,
            "restart_on_exit": None,
            "requires_network": None,
            "user": None
        }

        self.setWindowTitle("SystemD Unit Generator")
        self.resize(1280, 720)

        layout = QGridLayout()

        url_label = QLabel("Unit name")
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Alphanumeric and -_ allowed")
        self.name_input.setValidator(QRegExpValidator(QRegExp(r"^[a-zA-Z0-9_-]+$")))
        layout.addWidget(url_label, 0, 0)
        layout.addWidget(self.name_input, 0, 1)

        description_label = QLabel("Unit human name")
        self.description_input = QLineEdit()
        self.description_input.setPlaceholderText("0-64 characters")
        self.description_input.setValidator(QRegExpValidator(QRegExp(r"^.{0,64}$")))
        layout.addWidget(description_label, 1, 0)
        layout.addWidget(self.description_input, 1, 1)

        unit_type_label = QLabel("Unit type")
        self.unit_type_input = QComboBox()
        self.unit_type_input.addItems(UNIT_TYPES)
        layout.addWidget(unit_type_label, 2, 0)
        layout.addWidget(self.unit_type_input, 2, 1)

        run_as_user_label = QLabel("Run as user")
        self.run_as_user_input = QComboBox()
        self.run_as_user_input.addItems(
            [f"{x.pw_name}{f' ({x.pw_gecos})' if getattr(x, 'pw_gecos', None) else ''}" for x in ALL_USERS]
        )
        layout.addWidget(run_as_user_label, 3, 0)
        layout.addWidget(self.run_as_user_input, 3, 1)

        # We will add the checkboxes on one row
        restart_on_exit = QCheckBox("Restart on exit")
        requires_network = QCheckBox("Wait for network")
        resource_limiting = QCheckBox("Resource limiting")
        layout.addWidget(restart_on_exit, 4, 0)
        layout.addWidget(requires_network, 5, 0)
        layout.addWidget(resource_limiting, 6, 0)

        # .connect is 100% a function, PyCharm
        # noinspection PyUnresolvedReferences
        restart_on_exit.stateChanged.connect(lambda state: self.max_restarts_input.setVisible(state == Qt.Checked))
        # noinspection PyUnresolvedReferences
        resource_limiting.stateChanged.connect(
            lambda state: self.resource_limit_sub_widget.setVisible(state == Qt.Checked)
        )

        # And add the widgets next to those checkboxes if needed
        self.max_restarts_input = QLineEdit("10")
        self.max_restarts_input.setVisible(False)
        layout.addWidget(self.max_restarts_input, 4, 1)

        self.resource_limit_sub_widget = ResourceLimitSubWidget()
        self.resource_limit_sub_widget.setVisible(False)
        layout.addWidget(self.resource_limit_sub_widget, 6, 1, Qt.AlignBottom)

        layout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        self.setLayout(layout)


class WindowController(QObject):
    # This is about the only sane class in this file
    def __init__(self):
        super().__init__()
        self.win = None

    def start(self):
        self.win = FirstQuestions()
        QMessageBox.critical(
            self.win,
            "Incomplete program",
            "This GUI is not ready yet and currently doesn't actually do anything, apart from look promising."
        )
        # 24/02/23 21:47 - First Questions? isn't this basically the entire app?
        self.win.show()


def gui_main():
    # ngl I stole this from my first project, don't ask me how it works, I'll just tell you "it executes sequentially"
    app = QApplication(sys.argv)
    controller = WindowController()
    controller.start()
    sys.exit(app.exec_())


if __name__ == "__main__":  # for testing
    gui_main()
