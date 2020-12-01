from __future__ import absolute_import

import os
from builtins import object

import qgis.utils
from qgis.PyQt.QtCore import QMetaObject, QObject, QSettings, QThread, Qt, pyqtSlot
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import QAction, qApp

from .debuggerwidget import DebuggerWidget
from .debugwidget import DebugDialog

# -----------------------------------------------------------
# Copyright (C) 2015 Martin Dobias
# -----------------------------------------------------------
# Licensed under the terms of GNU GPL 2
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# ---------------------------------------------------------------------

dw = None
deferred_dw_handler = None


def show_debug_widget(debug_widget_data):
    """ Opens exception dialog with data from debug_widget_data - should be tuple (etype, value, tb). Must be called from main thread. """
    global dw
    if dw is not None:
        if dw.isVisible():
            return  # pass this exception while previous is being inspected
        else:
            dw.close()
            dw.deleteLater()
            dw = None

    dw = DebugDialog(debug_widget_data)
    dw.show()

    #  yes, all the below are required. silly qt!
    dw.raise_()
    dw.activateWindow()
    dw.setFocus()


class DeferredExceptionObject(QObject):
    """ Helper object that allows display of exceptions from worker threads: running of start_deferred() is requested from worker thread. """

    def __init__(self, parent=None):
        QObject.__init__(self, parent)
        self.debug_widget_data = None

    @pyqtSlot()
    def start_deferred(self):
        """ slot that gets run in main thread - safe to use GUI code """
        show_debug_widget(self.debug_widget_data)


def showException(etype, value, tb, msg, *args, **kwargs):
    if QThread.currentThread() == qApp.thread():
        # we can show the exception directly
        show_debug_widget((etype,value,tb))
    else:
        # we need to pass the exception details to main thread - we can't do GUI stuff here
        deferred_dw_handler.debug_widget_data = (etype,value,tb)
        QMetaObject.invokeMethod(deferred_dw_handler, "start_deferred", Qt.QueuedConnection)


def classFactory(iface):
    return FirstAidPlugin(iface)


class FirstAidPlugin(object):
    def __init__(self, iface):
        self.old_show_exception = None
        self.debugger_widget = None

    def initGui(self):
        # ReportPlugin also hooks exceptions and needs to be unloaded if active
        # so qgis.utils.showException is the QGIS native one
        report_plugin = "report"
        report_plugin_active = report_plugin in qgis.utils.active_plugins
        if report_plugin_active:
            qgis.utils.unloadPlugin(report_plugin)

        # hook to exception handling
        self.old_show_exception = qgis.utils.showException
        qgis.utils.showException = showException

        global deferred_dw_handler
        deferred_dw_handler = DeferredExceptionObject(qgis.utils.iface.mainWindow())

        icon = QIcon(os.path.join(os.path.dirname(__file__), "icons", "bug.svg"))
        self.action_debugger = QAction(icon, "Debug (Ctrl + F12)", qgis.utils.iface.mainWindow())
        self.action_debugger.setShortcut("Ctrl+F12")
        self.action_debugger.triggered.connect(self.run_debugger)
        qgis.utils.iface.addToolBarIcon(self.action_debugger)

        # If ReportPlugin was activated, load and start it again to cooperate
        if report_plugin_active:
            qgis.utils.loadPlugin(report_plugin)
            qgis.utils.startPlugin(report_plugin)

    def unload(self):

        qgis.utils.iface.removeToolBarIcon(self.action_debugger)
        del self.action_debugger

        # unhook from exception handling
        qgis.utils.showException = self.old_show_exception

        global dw
        if dw is not None:
            dw.close()
            dw.deleteLater()
            dw = None

    def run_debugger(self):
        if self.debugger_widget is None:
            self.debugger_widget = DebuggerWidget()
        else:
            self.debugger_widget.start_tracing()
        self.debugger_widget.show()
