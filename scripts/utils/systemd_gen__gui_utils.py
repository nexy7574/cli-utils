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
import logging
from typing import Literal, Dict
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

logger = logging.getLogger(__name__)

UNIT_TYPES = ["simple", "exec", "forking", "oneshot", "dbus", "notify", "idle"]  # I wish this code was _[0]


def do_set_state_for(source: QCheckBox, target: QWidget):
    def inner(_):
        button_is_checked = is_checked(source)
        logger.debug(f"Setting {target!r} to be {'in' if not button_is_checked else ''}visible.")
        target.setVisible(button_is_checked)

    # noinspection PyUnresolvedReferences
    source.stateChanged.connect(inner)


def is_checked(source: QCheckBox, *, full: bool = False) -> bool:
    if not full:
        return source.checkState() != Qt.Unchecked
    else:
        return source.checkState() == Qt.Checked


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

        self._old_width = 600
        self.setVisible(False)
        self.setLayout(layout)

    def setVisible(self, visible: bool) -> None:
        super().setVisible(visible)
        if visible:
            if self.width() < 300:
                logger.info("Resizing window to at least 600px")
                self._old_width = self.width()
                self.window().resize(600, self.height())
        else:
            logger.info(f"Resizing window back to its original {self._old_width}x{self.height()}")
            self.window().resize(self._old_width, self.height())

    def get_machine_values(self) -> Dict[str, int | None]:
        """Parses input into machine-readable values. In this case, it converts all human inputs to bytes or None."""
        values =  {
            "min_ram": self.min_memory_input.text() or None,
            "max_ram": self.max_memory_input.text() or None,
            "pressure_ram": self.pressure_memory_input.text() or None
        }
        for k, v in values.items():
            if v is not None:
                try:
                    values[k] = convert_soft_data_value_to_hard_data_value(v, "M")
                except (ValueError, ZeroDivisionError, OverflowError) as e:
                    logger.error(f"Failed to convert input for {k!r}: {v}.", exc_info=e)
                    QMessageBox.critical(
                        self,
                        "Failed to convert values",
                        f"Failed to parse value {v!r} (for key {k!r}) into megabytes: {e}\n\n"
                        f"Review your inputs and try again."
                    )
                    raise RuntimeError("Failed to convert. Do not abort.")
                else:
                    logger.info(f"Converted {v} into {values[k]} for key {k}.")
        return values


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

        do_set_state_for(self.enable_cpu_limiting_box, self.cpu_resource_sub)
        do_set_state_for(self.enable_ram_limiting_box, self.ram_resource_sub)

        layout.addWidget(self.enable_cpu_limiting_box, 0, 0)
        layout.addWidget(self.cpu_resource_sub, 0, 1)
        layout.addWidget(self.enable_ram_limiting_box, 1, 0)
        layout.addWidget(self.ram_resource_sub, 2, 0)

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
        # self.resize(1280, 720)
        # self.resize(800, 600)

        layout = QGridLayout()

        url_label = QLabel("Unit name")
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Alphanumeric and -_ allowed")
        self.name_input.setValidator(QRegExpValidator(QRegExp(r"^[a-zA-Z0-9_-]+$")))
        layout.addWidget(url_label, 0, 0)
        layout.addWidget(self.name_input, 0, 1, 1, 2)

        description_label = QLabel("Unit human name")
        self.description_input = QLineEdit()
        self.description_input.setPlaceholderText("0-64 characters")
        self.description_input.setValidator(QRegExpValidator(QRegExp(r"^.{0,64}$")))
        layout.addWidget(description_label, 1, 0)
        layout.addWidget(self.description_input, 1, 1, 1, 2)

        unit_type_label = QLabel("Unit type")
        self.unit_type_input = QComboBox()
        self.unit_type_input.addItems(UNIT_TYPES)
        layout.addWidget(unit_type_label, 2, 0)
        layout.addWidget(self.unit_type_input, 2, 1, 1, 2)

        run_as_user_label = QLabel("Run as user")
        self.run_as_user_input = QComboBox()
        self.run_as_user_input.addItems(
            [f"{x.pw_name}{f' ({x.pw_gecos})' if getattr(x, 'pw_gecos', None) else ''}" for x in ALL_USERS]
        )
        layout.addWidget(run_as_user_label, 3, 0)
        layout.addWidget(self.run_as_user_input, 3, 1, 1, 2)

        # We will add the checkboxes on one row
        self.restart_on_exit = QCheckBox("Restart on exit")
        self.requires_network = QCheckBox("Wait for network")
        self.resource_limiting = QCheckBox("Resource limiting")
        layout.addWidget(self.restart_on_exit, 4, 0)
        layout.addWidget(self.requires_network, 4, 1)
        layout.addWidget(self.resource_limiting, 4, 2)

        # And add the widgets next to those checkboxes if needed
        self.max_restarts_input = QLineEdit("10")
        self.max_restarts_input.setPlaceholderText("Max restarts before systemd stops re-starting the failing unit")
        self.max_restarts_input.setValidator(QIntValidator(0, 2000000000))
        self.max_restarts_input.setVisible(False)
        layout.addWidget(self.max_restarts_input, 5, 0, 1, 1, Qt.AlignHCenter)

        self.resource_limit_sub_widget = ResourceLimitSubWidget()
        self.resource_limit_sub_widget.setVisible(False)
        layout.addWidget(self.resource_limit_sub_widget, 5, 2, Qt.AlignBottom)

        do_set_state_for(self.restart_on_exit, self.max_restarts_input)
        do_set_state_for(self.resource_limiting, self.resource_limit_sub_widget)

        if os.getenv("DEV") is not None:
            self.print_debug_info_button = QPushButton("Print debug info to console")
            # noinspection PyUnresolvedReferences
            self.print_debug_info_button.clicked.connect(self.print_debug_info)
            layout.addWidget(self.print_debug_info_button)
            layout.setAlignment(self.print_debug_info_button, Qt.AlignBottom)

        layout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        self.setLayout(layout)

    def print_debug_info(self):
        lines = [
            "=== Debug info: ===",
            f"Name: {self.name_input.text()!r}",
            f"Description: {self.description_input.text()!r}",
            f"Type: {self.unit_type_input.itemText(self.unit_type_input.currentIndex())!r}",
            f"User: {self.run_as_user_input.itemText(self.run_as_user_input.currentIndex())!r}",
            f"Restart on exit: {self.restart_on_exit.checkState() == Qt.Checked}",
            f"| Max restarts: {self.max_restarts_input.text()!r}",
            f"Requires network: {self.requires_network.checkState() == Qt.Checked}",
            f"Resource Limiting: {self.resource_limiting.checkState() == Qt.Checked}",
            f"| CPU Limiting enabled: {self.resource_limit_sub_widget.enable_cpu_limiting_box.checkState() == Qt.Checked}",
            f"| | CPU Limit: {self.resource_limit_sub_widget.cpu_resource_sub.cpu_quota_input.text()}%",
            f"| RAM Limiting enabled: {self.resource_limit_sub_widget.enable_ram_limiting_box.checkState() == Qt.Checked}",
            f"| | parsed data: {self.resource_limit_sub_widget.ram_resource_sub.get_machine_values()!r}"
        ]
        for line in lines:
            print(line)
            logger.debug(line)
        QMessageBox.information(
            self,
            "Check your console",
            "Debug logs have been outputted to both the log file and the parent terminal."
        )

    def get_data(self) -> dict | None:
        # We also need to perform validation here too.
        def show_validation_error(text: str):
            QMessageBox.critical(
                self,
                "Validation error",
                text
            )

        name = self.name_input.text()
        description = self.description_input.text()
        unit_type = self.unit_type_input.itemText(self.unit_type_input.currentIndex())
        user = self.run_as_user_input.itemText(self.run_as_user_input.currentIndex())
        restart_on_exit = self.restart_on_exit.checkState() == Qt.Checked
        max_restarts = self.max_restarts_input.text()
        requires_network = self.requires_network.checkState() == Qt.Checked
        resource_limiting = self.resource_limiting.checkState() == Qt.Checked
        cpu_limiting = self.resource_limit_sub_widget.enable_cpu_limiting_box.checkState() == Qt.Checked
        cpu_limit = self.resource_limit_sub_widget.cpu_resource_sub.cpu_quota_input.text()
        ram_limiting = self.resource_limit_sub_widget.enable_ram_limiting_box.checkState() == Qt.Checked
        ram_limit = self.resource_limit_sub_widget.ram_resource_sub.get_machine_values()

        if not name:
            show_validation_error("You must specify a name for the unit")
            return
        if not description:
            show_validation_error("You must specify a human name for the unit")
            return

        if restart_on_exit:
            if not max_restarts:
                show_validation_error(
                    "You must specify a maximum number of restarts before systemd stops re-starting the unit"
                )
                return
            if not max_restarts.isdigit():
                show_validation_error("The maximum number of restarts must be a number")
                return
            if int(max_restarts) <= 0:
                show_validation_error("The maximum number of restarts must be greater than 0")
                return

        if cpu_limiting:
            _max = os.cpu_count() * 100
            if not cpu_limit:
                show_validation_error("You must specify a CPU quota")
                return
            if not cpu_limit.isdigit():
                show_validation_error("The CPU quota must be a number")
                return
            if int(cpu_limit) <= 0:
                show_validation_error("The CPU quota must be greater than 0")
                return
            if int(cpu_limit) > _max:
                show_validation_error(f"The CPU quota must be less than or equal to {_max}")
                return


class WindowController(QObject):
    # This is about the only sane class in this file
    def __init__(self):
        super().__init__()
        self.win = None

    def start(self):
        self.win = FirstQuestions()
        if os.getenv("DEV") is None or not os.getenv("DEV").isdigit():
            QMessageBox.critical(
                self.win,
                "Incomplete program",
                "This GUI is not ready yet and currently doesn't actually do anything, apart from look promising."
            )
        else:
            # set up logger to go to a file
            log_levels = {
                "1": "DEBUG",
                "2": "INFO",
                "3": "WARNING",
                "4": "ERROR",
                "5": "CRITICAL"
            }
            logging.basicConfig(
                filename="gui.debug.log",
                filemode="w",
                level=getattr(logging, log_levels[os.environ["DEV"]])
            )
            global logger
            logger = logging
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
