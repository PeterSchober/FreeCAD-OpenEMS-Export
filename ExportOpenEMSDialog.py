from PySide import QtGui, QtCore, QtWidgets
from PySide.QtCore import Slot
import os, sys
import re
import random
import numpy as np
import math

#import needed local classes
import sys
import traceback

APP_CONTEXT = "None"

try:
	import FreeCAD
	version = FreeCAD.Version()
	versionNum = int(version[0])+int(version[1])*0.1+int(version[2])*0.01
	print(versionNum)
	if versionNum >= 1.0:
		import webbrowser
	else:
		import WebGui
		
	import KiCADImporterToolDialog	#import for KiCAD Import Tool
	APP_CONTEXT = "FreeCAD"
except ImportError:
	pass

try:
	import bpy
	import uuid
	APP_CONTEXT = "Blender"
except ImportError:
	pass

print(f"APP_CONTEXT set to {APP_CONTEXT}")

#
#	Blender special things as that python is quite not giving paths as should be
#
APP_DIR = ''
if APP_CONTEXT == 'Blender':
	#
	#	This here is because Blender pyhton is not providing right info about paths in __file__ when running from editor
	#
	import webbrowser

	if hasattr(bpy.context, 'space_data') and bpy.context.space_data != None and bpy.context.space_data.type == "TEXT_EDITOR":
		#this is when this file is run inside blender in text editor
		APP_DIR = os.path.dirname(bpy.context.space_data.text.filepath)
	else:
		APP_DIR = os.path.dirname(__file__)

	print(f"SCRIPT_DIR: {APP_DIR}")
	sys.path.append(APP_DIR)
else:
	APP_DIR = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
path_to_ui = os.path.join(APP_DIR, "ui", "dialog.ui")

from utilsOpenEMS.SettingsItem.SettingsItem import SettingsItem
from utilsOpenEMS.SettingsItem.PortSettingsItem import PortSettingsItem
from utilsOpenEMS.SettingsItem.ProbeSettingsItem import ProbeSettingsItem
from utilsOpenEMS.SettingsItem.ExcitationSettingsItem import ExcitationSettingsItem
from utilsOpenEMS.SettingsItem.LumpedPartSettingsItem import LumpedPartSettingsItem
from utilsOpenEMS.SettingsItem.MaterialSettingsItem import MaterialSettingsItem
from utilsOpenEMS.SettingsItem.SimulationSettingsItem import SimulationSettingsItem
from utilsOpenEMS.SettingsItem.GridSettingsItem import GridSettingsItem
from utilsOpenEMS.SettingsItem.FreeCADSettingsItem import FreeCADSettingsItem

from utilsOpenEMS.ScriptLinesGenerator.OctaveScriptLinesGenerator import OctaveScriptLinesGenerator
from utilsOpenEMS.ScriptLinesGenerator.PythonScriptLinesGenerator import PythonScriptLinesGenerator

from utilsOpenEMS.ScriptLinesGenerator.OctaveScriptLinesGenerator2 import OctaveScriptLinesGenerator2	#EXPERIMENTAL JUST FOR DEBUGGING TILL MOVE TO RELEASE
from utilsOpenEMS.ScriptLinesGenerator.PythonScriptLinesGenerator2 import PythonScriptLinesGenerator2	#EXPERIMENTAL JUST FOR DEBUGGING TILL MOVE TO RELEASE

from utilsOpenEMS.GuiHelpers.GuiHelpers import GuiHelpers
from utilsOpenEMS.GuiHelpers.FactoryCadInterface import FactoryCadInterface

from utilsOpenEMS.GuiHelpers.GuiSignals import GuiSignals

from utilsOpenEMS.SaveLoad.IniFile0v1 import IniFile0v1

# UI file (use Qt Designer to modify)
from utilsOpenEMS.GlobalFunctions.GlobalFunctions import _bool, _r

#
# Main GUI panel class
#
class ExportOpenEMSDialog(QtCore.QObject):

	def finished(self):
		"""
		Finish observing CAD signals for add/remove/rename.
		:return: None
		"""
		if self.cadInterfaceType == "FreeCAD":
			self.observer.endObservation()
			self.observer = None
			print("FreeCAD observer terminated.")

			#if KiCAD import tool is opened close it
			if hasattr(self, "KiCADImportTool"):
				self.KiCADImportTool.close()
				del self.KiCADImportTool
				print("Kicad Import Tool closed")

		elif self.cadInterfaceType == "Blender":
			print(f"Thread killed.")

	def eventFilter(self, object, event):
		if event.type() == QtCore.QEvent.Close:
			self.finished()
		elif event.type() == QtCore.QEvent.WindowActivate and self.cadInterfaceType == "Blender":
			self.blenderWindowActivatedHandler()
		return super(ExportOpenEMSDialog, self).eventFilter(object, event)

	def __init__(self):
		QtCore.QObject.__init__(self)

		self.APP_DIR = APP_DIR

		#
		#	Directory for generated .m file for openEMS
		#		- by default set to None, that means simulation file should be generated into current directory
		#
		self.simulationOutputDir = None

		#
		# LOCAL OPENEMS OBJECT
		#
		self.cadHelpers = FactoryCadInterface.createHelper(self.APP_DIR)

		#
		# Change current path to script file folder
		#
		os.chdir(APP_DIR)

		# this will create a Qt widget from our ui file
		self.form = self.cadHelpers.loadUI(path_to_ui, self)
		# self.form.finished.connect(self.finished) # QDialog event
		self.form.installEventFilter(self)

		# add a statusBar widget (comment to revert to QMessageBox if there are any problems)
		self.statusBar = QtWidgets.QStatusBar()
		self.statusBar.setStyleSheet("QStatusBar{border-top: 1px outset grey;}")
		self.form.dialogVertLayout.addWidget(self.statusBar)

		#
		#	FONT SIZE whoole GUI
		#
		#self.form.setStyleSheet(".QLabel{font-size: 25pt;}")

		#
		# instantiate script generators using this dialog form
		#
		#self.octaveScriptGenerator = OctaveScriptLinesGenerator(self.form, statusBar = self.statusBar)

		# EXPERIMENTAL using settings to short code and move auxiliary logic for diferent sutff into settings classes
		# to be able do in python code generatr same stuff as in octave
		self.octaveScriptGenerator = OctaveScriptLinesGenerator2(self.form, statusBar=self.statusBar)
		self.pythonScriptGenerator = PythonScriptLinesGenerator2(self.form, statusBar = self.statusBar)

		self.scriptGenerator = self.octaveScriptGenerator #variable which store current script generator
		#self.scriptGenerator2 = OctaveScriptLinesGenerator2(self.form, statusBar=self.statusBar)
		#self.scriptGenerator3 = PythonScriptLinesGenerator2(self.form, statusBar=self.statusBar)

		#
		#	Connect function to change script generator
		#
		self.form.radioButton_octaveType.clicked.connect(self.radioButtonOutputScriptsTypeClicked)
		self.form.radioButton_pythonType.clicked.connect(self.radioButtonOutputScriptsTypeClicked)

		#
		# GUI helpers function like display message box and so
		#
		self.guiHelpers = GuiHelpers(self.form, statusBar = self.statusBar, APP_DIR=APP_DIR)
		self.guiSignals = GuiSignals()

		#
		# INI file object to used for save/load operation
		#
		self.simulationSettingsFile = IniFile0v1(self.form, statusBar = self.statusBar, guiSignals = self.guiSignals, APP_DIR = APP_DIR)

		#
		# TOP LEVEL ITEMS / Category Items (excitation, grid, materials, ...)
		#
		self.guiHelpers.initRightColumnTopLevelItems()

		#select first item
		topItem = self.form.objectAssignmentRightTreeWidget.itemAt(0,0)
		self.form.objectAssignmentRightTreeWidget.setCurrentItem(topItem)

		self.form.moveLeftButton.clicked.connect(self.onMoveLeft)
		self.form.moveRightButton.clicked.connect(self.onMoveRight)

		#########################################################################################################
		#	Left Column - FreeCAD objects list
		#########################################################################################################

		self.internalObjectNameLabelList = {}

		self.initLeftColumnTopLevelItems()
		self.form.objectAssignmentLeftTreeWidget.itemDoubleClicked.connect(self.objectAssignmentLeftTreeWidgetItemDoubleClicked)
		self.form.objectAssignmentLeftTreeWidget.itemSelectionChanged.connect(self.objectAssignmentLeftTreeWidgetItemSelectionChanged)

		#########################################################################################################
		#	RIGHT COLUMN - Simulation Object Assignment
		#########################################################################################################

		self.form.objectAssignmentRightTreeWidget.itemSelectionChanged.connect(self.objectAssignmentRightTreeWidgetItemSelectionChanged)

		self.form.objectAssignmentRightTreeWidget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
		self.form.objectAssignmentRightTreeWidget.customContextMenuRequested.connect(self.objectAssignmentRightTreeWidgetContextClicked)
		self.form.objectAssignmentRightTreeWidget.itemDoubleClicked.connect(self.objectAssignmentRightTreeWidgetItemDoubleClicked)

		#########################################################################################################
		#########################################################################################################
		#########################################################################################################

		#
		# SETTINGS FOR BUTTONS CLICK, functions assignments
		#
		self.form.gridSettingsAddButton.clicked.connect(self.gridSettingsAddButtonClicked)
		self.form.gridSettingsRemoveButton.clicked.connect(self.gridSettingsRemoveButtonClicked)
		self.form.gridSettingsUpdateButton.clicked.connect(self.gridSettingsUpdateButtonClicked)

		self.form.materialSettingsAddButton.clicked.connect(self.materialSettingsAddButtonClicked)
		self.form.materialSettingsRemoveButton.clicked.connect(self.materialSettingsRemoveButtonClicked)
		self.form.materialSettingsUpdateButton.clicked.connect(self.materialSettingsUpdateButtonClicked)
		self.guiSignals.materialsChanged.connect(self.materialsChanged)

		self.form.excitationSettingsAddButton.clicked.connect(self.excitationSettingsAddButtonClicked)
		self.form.excitationSettingsRemoveButton.clicked.connect(self.excitationSettingsRemoveButtonClicked)
		self.form.excitationSettingsUpdateButton.clicked.connect(self.excitationSettingsUpdateButtonClicked)

		self.form.portSettingsAddButton.clicked.connect(self.portSettingsAddButtonClicked)
		self.form.portSettingsRemoveButton.clicked.connect(self.portSettingsRemoveButtonClicked)
		self.form.portSettingsUpdateButton.clicked.connect(self.portSettingsUpdateButtonClicked)
		self.guiSignals.portsChanged.connect(self.portsChanged)

		self.form.lumpedPartSettingsAddButton.clicked.connect(self.lumpedPartSettingsAddButtonClicked)
		self.form.lumpedPartSettingsRemoveButton.clicked.connect(self.lumpedPartSettingsRemoveButtonClicked)
		self.form.lumpedPartSettingsUpdateButton.clicked.connect(self.lumpedPartSettingsUpdateButtonClicked)

		self.form.probeSettingsAddButton.clicked.connect(self.probeSettingsAddButtonClicked)
		self.form.probeSettingsRemoveButton.clicked.connect(self.probeSettingsRemoveButtonClicked)
		self.form.probeSettingsUpdateButton.clicked.connect(self.probeSettingsUpdateButtonClicked)
		self.guiSignals.probesChanged.connect(self.probesChanged)

		#
		# Handle function for grid radio buttons click
		#
		self.form.userDefinedRadioButton.clicked.connect(self.userDefinedRadioButtonClicked)
		self.form.fixedCountRadioButton.clicked.connect(self.fixedCountRadioButtonClicked)
		self.form.fixedDistanceRadioButton.clicked.connect(self.fixedDistanceRadioButtonClicked)
		self.form.smoothMeshRadioButton.clicked.connect(self.smoothMeshRadioButtonClicked)

		# Handle function for MATERIAL RADIO BUTTONS
		self.form.materialUserDefinedRadioButton.toggled.connect(self.materialUserDeinedRadioButtonToggled)
		self.form.materialConductingSheetRadioButton.toggled.connect(self.materialConductingSheetRadioButtonToggled)

		#
		# Clicked on "Generate OpenEMS Script"
		#
		self.form.generateOpenEMSScriptButton.clicked.connect(self.generateOpenEMSScriptButtonClicked)

		#
		# Clicked on BUTTONS FOR OBJECT PRIORITIES
		#
		self.form.moveupPriorityButton.clicked.connect(self.moveupPriorityButtonClicked)
		self.form.movedownPriorityButton.clicked.connect(self.movedownPriorityButtonClicked)

		#
		# Clicked on BUTTONS FOR MESH PRIORITIES
		#
		self.form.moveupMeshPriorityButton.clicked.connect(self.moveupPriorityMeshButtonClicked)
		self.form.movedownMeshPriorityButton.clicked.connect(self.movedownPriorityMeshButtonClicked)

		#
		#	Octave/Matlab script generating buttons handlers
		#
		self.form.eraseAuxGridButton.clicked.connect(self.eraseAuxGridButtonClicked)														# Clicked on "Erase aux Grid"
		self.form.abortSimulationButton.clicked.connect(lambda: self.abortSimulationButtonClicked(self.simulationOutputDir))													# Clicked on "Write ABORT Simulation File"
		self.form.drawS11Button.clicked.connect(self.drawS11ButtonClicked)			# Clicked on "Write Draw S11 Script"
		self.form.drawS21Button.clicked.connect(self.drawS21ButtonClicked)			# Clicked on "Write Draw S21 Script"
		self.form.writeNf2ffButton.clicked.connect(self.writeNf2ffButtonClicked)	# Clicked on "Write NF2FF"

		#
		# GRID
		#	- button "Display gridlines...."
		#	- button "Create userdef..."
		#	- select rectangular or cylindrical grid
		#
		self.form.createUserdefGridLinesFromCurrentButton.clicked.connect(self.createUserdefGridLinesFromCurrentButtonClicked)
		self.form.displayXYGridLinesInModelButton.clicked.connect(self.displayXYGridLinesInModelButtonClicked)
		self.form.gridRectangularRadio.toggled.connect(self.gridCoordsTypeChoosed)
		self.form.gridCylindricalRadio.toggled.connect(self.gridCoordsTypeChoosed)

		self.form.gridXEnable.stateChanged.connect(lambda:[
			element.setEnabled(True)
			if self.form.gridXEnable.checkState() == QtCore.Qt.Checked else
			element.setEnabled(False)
			for element in [self.form.fixedCountXNumberInput, self.form.fixedDistanceXNumberInput, self.form.smoothMeshXMaxRes]
		])

		self.form.gridYEnable.stateChanged.connect(lambda:[
			element.setEnabled(True)
			if self.form.gridYEnable.checkState() == QtCore.Qt.Checked else
			element.setEnabled(False)
			for element in [self.form.fixedCountYNumberInput, self.form.fixedDistanceYNumberInput, self.form.smoothMeshYMaxRes]
		])

		self.form.gridZEnable.stateChanged.connect(lambda:[
			element.setEnabled(True)
			if self.form.gridZEnable.checkState() == QtCore.Qt.Checked else
			element.setEnabled(False)
			for element in [self.form.fixedCountZNumberInput, self.form.fixedDistanceZNumberInput, self.form.smoothMeshZMaxRes]
		])

		# grid offset gui form enable/disable
		self.form.gridXEnable.stateChanged.connect(lambda:[
			element.setEnabled(True)
			if self.form.gridXEnable.checkState() == QtCore.Qt.Checked and self.form.gridGenerateLinesInsideCheckbox.checkState() == QtCore.Qt.Checked else
			element.setEnabled(False)
			for element in [self.form.gridOffsetX]
		])
		self.form.gridYEnable.stateChanged.connect(lambda:[
			element.setEnabled(True)
			if self.form.gridYEnable.checkState() == QtCore.Qt.Checked and self.form.gridGenerateLinesInsideCheckbox.checkState() == QtCore.Qt.Checked else
			element.setEnabled(False)
			for element in [self.form.gridOffsetY]
		])
		self.form.gridZEnable.stateChanged.connect(lambda:[
			element.setEnabled(True)
			if self.form.gridZEnable.checkState() == QtCore.Qt.Checked and self.form.gridGenerateLinesInsideCheckbox.checkState() == QtCore.Qt.Checked else
			element.setEnabled(False)
			for element in [self.form.gridOffsetZ]
		])
		self.form.gridGenerateLinesInsideCheckbox.stateChanged.connect(self.gridGenerateLinesInsideCheckboxToggle)

		self.guiSignals.gridCoordsTypeChanged.connect(self.gridCoordsTypeChanged)

		#
		# Material, Grid, Excitation, ... item changed handler functions.
		#
		self.form.materialSettingsTreeView.currentItemChanged.connect(self.materialTreeWidgetItemChanged)
		self.form.excitationSettingsTreeView.currentItemChanged.connect(self.excitationTreeWidgetItemChanged)
		self.form.gridSettingsTreeView.currentItemChanged.connect(self.gridTreeWidgetItemChanged)
		self.form.portSettingsTreeView.currentItemChanged.connect(self.portTreeWidgetItemChanged)
		self.form.lumpedPartTreeView.currentItemChanged.connect(self.lumpedPartTreeWidgetItemChanged)
		self.form.probeSettingsTreeView.currentItemChanged.connect(self.probeTreeWidgetItemChanged)

		#
		# PORT tab settings events handlers
		#
		self.form.lumpedPortRadioButton.toggled.connect(self.portSettingsTypeChoosed)
		self.form.microstripPortRadioButton.toggled.connect(self.portSettingsTypeChoosed)
		self.form.circularWaveguidePortRadioButton.toggled.connect(self.portSettingsTypeChoosed)
		self.form.rectangularWaveguidePortRadioButton.toggled.connect(self.portSettingsTypeChoosed)
		self.form.coaxialPortRadioButton.toggled.connect(self.portSettingsTypeChoosed)
		self.form.coplanarPortRadioButton.toggled.connect(self.portSettingsTypeChoosed)
		self.form.striplinePortRadioButton.toggled.connect(self.portSettingsTypeChoosed)
		self.form.curvePortRadioButton.toggled.connect(self.portSettingsTypeChoosed)

		self.form.microstripPortDirection.activated.connect(self.microstripPortDirectionOnChange)
		self.form.striplinePortDirection.activated.connect(self.striplinePortDirectionOnChange)
		self.form.coplanarPortDirection.activated.connect(self.coplanarPortDirectionOnChange)

		self.form.lumpedPortInfinitResistance.stateChanged.connect(lambda: [
			element.setEnabled(False) if self.form.lumpedPortInfinitResistance.isChecked() else element.setEnabled(True)
			for element in [self.form.lumpedPortResistanceValue, self.form.lumpedPortResistanceUnits]
		])

		self.form.microstripPortDirection.activated.emit(0)	#emit signal to fill connected combobox or whatever with right values after startup, ie. when user start GUI there is no change
															# and combobox with propagation direction left with all possibilities

		self.form.coplanarPortDirection.activated.emit(0)	#emit signal to fill connected combobox or whatever with right values after startup, ie. when user start GUI there is no change
															# and combobox with propagation direction left with all possibilities

		self.form.striplinePortDirection.activated.emit(0)	#emit signal to fill connected combobox or whatever with right values after startup, ie. when user start GUI there is no change
															# and combobox with propagation direction left with all possibilities

		################################################################################################################
		#	PROBE TAB -> DUMPBOX TAB UI EVENT HANDLERS
		################################################################################################################

		self.form.probeProbeRadioButton.toggled.connect(self.probeSettingsTypeChoosed)
		self.form.dumpboxProbeRadioButton.toggled.connect(self.probeSettingsTypeChoosed)
		self.form.etDumpProbeRadioButton.toggled.connect(self.probeSettingsTypeChoosed)
		self.form.htDumpProbeRadioButton.toggled.connect(self.probeSettingsTypeChoosed)
		self.form.nf2ffBoxProbeRadioButton.toggled.connect(self.probeSettingsTypeChoosed)

		self.form.probeProbeFrequencyAddButton.clicked.connect(self.probeProbeFrequencyAddButtonClicked)
		self.form.probeProbeFrequencyRemoveButton.clicked.connect(self.probeProbeFrequencyRemoveButtonClicked)
		self.form.probeProbeDomain.currentIndexChanged.connect(lambda:[
			element.setEnabled(True)
			if self.form.probeProbeDomain.currentText() == "frequency" else
			element.setEnabled(False)
			for element in [self.form.probeProbeFrequencyInput, self.form.probeProbeFrequencyUnits, self.form.probeProbeFrequencyList, self.form.probeProbeFrequencyAddButton, self.form.probeProbeFrequencyRemoveButton]
		])

		self.form.dumpboxProbeFrequencyAddButton.clicked.connect(self.dumpboxProbeFrequencyAddButtonClicked)
		self.form.dumpboxProbeFrequencyRemoveButton.clicked.connect(self.dumpboxProbeFrequencyRemoveButtonClicked)
		self.form.dumpboxProbeDomain.currentIndexChanged.connect(self.dumpboxProbeDomainChanged)					#enable/disable frequency settings for probe based on domain, also change filetype for domains

		################################################################################################################
		#	SIMULATION TAB boundary condition change handlers, minimal spacing handler enable/disable spinboxes
		################################################################################################################

		#SIMULATION Boundary Conditions change event mapping
		self.form.BCxmin.currentIndexChanged.connect(self.BCxminCurrentIndexChanged)
		self.form.BCxmax.currentIndexChanged.connect(self.BCxmaxCurrentIndexChanged)
		self.form.BCymin.currentIndexChanged.connect(self.BCyminCurrentIndexChanged)
		self.form.BCymax.currentIndexChanged.connect(self.BCymaxCurrentIndexChanged)
		self.form.BCzmin.currentIndexChanged.connect(self.BCzminCurrentIndexChanged)
		self.form.BCzmax.currentIndexChanged.connect(self.BCzmaxCurrentIndexChanged)

		self.form.genParamMinGridSpacingEnable.stateChanged.connect(lambda:
			[element.setEnabled(True) for element in [self.form.genParamMinGridSpacingX, self.form.genParamMinGridSpacingY, self.form.genParamMinGridSpacingZ]]
			if self.form.genParamMinGridSpacingEnable.isChecked() else
			[element.setEnabled(False) for element in [self.form.genParamMinGridSpacingX, self.form.genParamMinGridSpacingY, self.form.genParamMinGridSpacingZ]]
		)

		####################################################################################################
		# GUI SAVE/LOAD from file
		####################################################################################################
		self.form.saveToFileSettingsButton.clicked.connect(self.saveToFileSettingsButtonClicked)
		self.form.loadFromFileSettingsButton.clicked.connect(self.loadFromFileSettingsButtonClicked)

		#
		# FILTER LEFT COLUMN ITEMS
		#
		self.form.objectAssignmentFilterLeft.returnPressed.connect(self.applyObjectAssignmentFilter)

		# MinDecrement changed
		self.form.simParamsMinDecrement.valueChanged.connect(self.simParamsMinDecrementValueChanged)

		### Other Initialization

		# initialize dB preview label with converted value
		self.simParamsMinDecrementValueChanged(self.form.simParamsMinDecrement.value())

		#
		#	KiCAD Importer Tool
		#
		self.form.KiCADImportButton.clicked.connect(self.KiCADImportButtonClicked)

		self.cadInterfaceType = APP_CONTEXT
		print("Creating document handlers")
		if APP_CONTEXT == "FreeCAD":
			try:
				self.form.KiCADImportButton.setEnabled(True)	#enable KiCAD Importer Tool, it's JUST FOR FreeCAD

				# create observer instance
				from utilsOpenEMS.GuiHelpers.FreeCADDocObserver import FreeCADDocObserver
				self.observer = FreeCADDocObserver()
				self.observer.objectCreated += self.freecadObjectCreated
				self.observer.objectChanged += self.freecadObjectChanged
				self.observer.objectDeleted += self.freecadBeforeObjectDeleted
				self.observer.startObservation()

			except:
				self.cadHelpers.printError("Cannot create FreeCAD observer, there is no connection to CAD program signals.")
				pass

			# connect signal for button to display help page
			try:
				self.form.buttonOpenHelpPage.clicked.connect(self.openFreeCADWebGuiHelp)
			except Exception as e:
				self.cadHelpers.printError("Error to connect signal for button to display help.")
				self.cadHelpers.printError(e)

		elif APP_CONTEXT == "Blender":
			#
			#	No handlers registered for Blender since there is no suitable one, add/remove/rename objects is handeld in
			#	event process when window is focuse objects are re-evaluated.
			#

			# connect signal for button to display help page
			try:
				self.form.buttonOpenHelpPage.clicked.connect(self.openBlenderWebGuiHelp)
			except Exception as e:
				self.cadHelpers.printError("Error to connect signal for button to display help.")
				self.cadHelpers.printError(e)

		#
		#	GUI font size change
		#
		self.form.guiFontSizeCombobox.currentIndexChanged.connect(lambda: self.form.setStyleSheet(f"font: {self.form.guiFontSizeCombobox.currentText()} \"{self.form.guiFontFamilyCombobox.currentText()}\";"))
		self.form.guiFontFamilyCombobox.currentIndexChanged.connect(lambda: self.form.setStyleSheet(f"font: {self.form.guiFontSizeCombobox.currentText()} \"{self.form.guiFontFamilyCombobox.currentText()}\";"))

		#
		#	add default PEC material
		#
		self.materialAddPEC()

		#
		#	Simulation items (grid, material, excitation, port, lumped part) renamed signal connect
		#
		self.guiSignals.gridRenamed.connect(self.gridRenamed)
		self.guiSignals.gridTypeChangedToSmoothMesh.connect(self.gridTypeChangedToSmoothMesh)
		self.guiSignals.gridTypeChangedFromSmoothMesh.connect(self.gridTypeChangedFromSmoothMesh)

		self.guiSignals.materialRenamed.connect(self.materialRenamed)
		self.guiSignals.excitationRenamed.connect(self.excitationRenamed)
		self.guiSignals.portRenamed.connect(self.portRenamed)
		self.guiSignals.lumpedPartRenamed.connect(self.lumpedPartRenamed)
		self.guiSignals.probeRenamed.connect(self.probeRenamed)

		print(f"----> init finished")

	def KiCADImportButtonClicked(self):
		# if KiCAD import tool is not created create new one
		if not hasattr(self, "KiCADImportTool"):
			self.KiCADImportTool = KiCADImporterToolDialog.KiCADImporterToolDialog()

		self.KiCADImportTool.show()

	def openFreeCADWebGuiHelp(self):
		"""
		Open index help html webpage inside freecad window.
		:return:
		"""
		if versionNum >= 1.0:
			webbrowser.open(f"{os.path.dirname(__file__)}\\documentation\\help\\index.html")
		else:
			WebGui.openBrowser(f"{os.path.dirname(__file__)}\\documentation\\help\\index.html")

	def openBlenderWebGuiHelp(self):
		"""
		Open index help html webpage in OS webbrowser.
		:return:
		"""
		webbrowser.open(f"{os.path.dirname(__file__)}\\documentation\\help\\index.html", new=2)

	def freecadObjectCreated(self, obj):
		print("freecadObjectCreated :{} ('{}')".format(obj.FullName, obj.Label))
		# A new object has been created. Only the list of available objects needs to be updated.
		filterStr = self.form.objectAssignmentFilterLeft.text()
		self.initLeftColumnTopLevelItems(filterStr)


	def freecadObjectChanged(self, obj, prop, enableReInitLeftColumn=True):
		print("freecadObjectChanged :{} ('{}') property changed: {}".format(obj.FullName, obj.Label, prop))

		#property label was changes, object was renamed in freecad
		if prop == 'Label':
			# The label (displayed name) of an object has changed.
			# (TODO) Update all mentions in the ObjectAssigments panel.

			#
			#	Rename items in right column where objects are assigned to categories
			#
			itemsWithOriginalLabel = self.form.objectAssignmentRightTreeWidget.findItems(self.internalObjectNameLabelList[obj.Name], QtCore.Qt.MatchExactly | QtCore.Qt.MatchFlag.MatchRecursive)
			print(f"RIGHT ASSIGNMENT WIDGET found {len(itemsWithOriginalLabel)}")
			for itemToRename in itemsWithOriginalLabel:
				reResult = re.search("([A-Za-z]*)SettingsItem'", str(type(itemToRename.data(0, QtCore.Qt.UserRole))))
				if (reResult.group(1).lower() == "freecad"):
					itemToRename.setText(0, obj.Label)

			#
			#	Renames items in priority list and mesh priority list, names there are like:
			#		Material, some name, objectName
			#							 so this object name from end must be replace by new name
			#
			itemsWithOriginalLabel = []
			itemsWithOriginalLabel += self.form.objectAssignmentPriorityTreeView.findItems(self.internalObjectNameLabelList[obj.Name], QtCore.Qt.MatchEndsWith | QtCore.Qt.MatchFlag.MatchRecursive)
			itemsWithOriginalLabel += self.form.meshPriorityTreeView.findItems(self.internalObjectNameLabelList[obj.Name], QtCore.Qt.MatchEndsWith | QtCore.Qt.MatchFlag.MatchRecursive)
			print(f"OBJECT PRIORITIES found {len(itemsWithOriginalLabel)}")
			for itemToRename in itemsWithOriginalLabel:
				newLabel = itemToRename.text(0)
				newLabel = newLabel[:-len(self.internalObjectNameLabelList[obj.Name])] + obj.Label
				itemToRename.setText(0, newLabel)

			#
			#	TinitLeftCOlumnToLevelItems refill internalObjectNameLabelList, so when working in bulk this reinit must be supressed till last item
			#
			if enableReInitLeftColumn:
				filterStr = self.form.objectAssignmentFilterLeft.text()
				self.initLeftColumnTopLevelItems(filterStr)

	def freecadBeforeObjectDeleted(self,obj):
		# event is generated before object is being removed, so observing instances have to
		# (TODO) un-list the object without drawing upon the FreeCAD objects list, and
		# (TODO) propagate changes to prevent corruption.
		#    Simple approach: delete dependent entries.
		#    Advanced: remember and gray out deleted objects to allow settings to be restored when
		#    the user brings the object back with Redo.
		print("freecadObjectDeleted :{} ('{}')".format(obj.FullName, obj.Label))

		#
		#	Rename items in right column where objects are assigned to categories
		#
		itemsWithOriginalLabel = self.form.objectAssignmentRightTreeWidget.findItems(obj.Label, QtCore.Qt.MatchExactly | QtCore.Qt.MatchFlag.MatchRecursive)
		for itemToRename in itemsWithOriginalLabel:
			reResult = re.search("([A-Za-z]*)SettingsItem'", str(type(itemToRename.data(0, QtCore.Qt.UserRole))))
			if (reResult.group(1).lower() == "freecad"):
				itemToRename.parent().removeChild(itemToRename)

		#
		#	Renames items in priority list and mesh priority list, names there are like:
		#		Material, some name, objectName
		#							 so this object name from end must be replace by new name
		#
		itemsWithOriginalLabel = self.form.objectAssignmentPriorityTreeView.findItems(obj.Label, QtCore.Qt.MatchEndsWith | QtCore.Qt.MatchFlag.MatchRecursive)
		for itemToRename in itemsWithOriginalLabel:
			self.form.objectAssignmentPriorityTreeView.invisibleRootItem().removeChild(itemToRename)

		itemsWithOriginalLabel = self.form.meshPriorityTreeView.findItems(obj.Label, QtCore.Qt.MatchEndsWith | QtCore.Qt.MatchFlag.MatchRecursive)
		for itemToRename in itemsWithOriginalLabel:
			self.form.meshPriorityTreeView.invisibleRootItem().removeChild(itemToRename)

		#
		#	Remove from left widget object because this is running before delete so if init function for left widget would be executed object will be still there
		#
		itemsWithOriginalLabel = self.form.objectAssignmentLeftTreeWidget.findItems(obj.Label, QtCore.Qt.MatchEndsWith | QtCore.Qt.MatchFlag.MatchRecursive)
		for itemToRename in itemsWithOriginalLabel:
			self.form.meshPriorityTreeView.invisibleRootItem().removeChild(itemToRename)

		# remove object label from internal list
		del self.internalObjectNameLabelList[obj.Name]

	def blenderWindowActivatedHandler(self):
		"""
		Iterates over bpy.data.object (THIS IS IMPORTANT IT'S DATA NOT CONTEXT.SCENE.OBJECTS) and assign unique id into freeCadId if is not defined.
		:return: None
		"""
		currentObjectsList_Id_Name = {}
		currentObjectsList_Name_Id = {}

		newObjects_Name_Id = {}
		deletedObjects_Id_Name = {}
		renamedObjects_Id_Name = {}

		for obj in bpy.data.objects:
			if not "freeCadId" in obj.keys():
				obj['freeCadId'] = str(uuid.uuid4())
				print(f"assigned uuid for {obj.name}: {obj['freeCadId']}")
			currentObjectsList_Id_Name[obj['freeCadId']] = obj.name  # stores names under object id to detect later renamed objects
			currentObjectsList_Name_Id[obj.name] = obj['freeCadId']  # stores names under object id to detect later renamed objects

		if not hasattr(self, 'previousObjectsList_Id_Name') or len(self.previousObjectsList_Name_Id) == 0:
			#
			#	These two dict are for blender to react on add/remove/rename object events, since there are no appropriate signals
			#	from blender there is update for everytime user make addon window active and this dict store values to compare
			#	current object names and ids to previous values.
			#
			self.previousObjectsList_Id_Name = currentObjectsList_Id_Name
			self.previousObjectsList_Name_Id = currentObjectsList_Name_Id

			#
			#	Since when these list are created means addon was just run up and here first ID were generated if they werent there so
			#	internal list for objects which is created during initLetfColumn is not populated, so now repopulate it and internal
			#	list will have right values of name, id
			#
			self.initLeftColumnTopLevelItems(self.form.objectAssignmentFilterLeft.text())
		else:
			newObjects_Name_Id = dict([(key,value) for key,value in currentObjectsList_Name_Id.items() if value not in self.previousObjectsList_Name_Id.values()])
			deletedObjects_Id_Name = dict([(key,value) for key,value in self.previousObjectsList_Id_Name.items() if key not in currentObjectsList_Id_Name.keys()])
			renamedObjects_Id_Name = dict([(key,value) for key,value in currentObjectsList_Id_Name.items() if key in self.previousObjectsList_Id_Name.keys() and key in currentObjectsList_Id_Name.keys() and self.previousObjectsList_Id_Name[key] != currentObjectsList_Id_Name[key]])

			print(f"new objects: {newObjects_Name_Id}")
			print(f"deleted objects: {deletedObjects_Id_Name}")
			print(f"renamed objects: {renamedObjects_Id_Name}")

		class BlenderToCadObject:
			def __init__(self, label, idStr):
				self.Label = label
				self.FullName = label
				self.Name = idStr

		#
		#	Operation must be handled in this order to made it correctly:
		#		rename, delete, new
		#
		if len(renamedObjects_Id_Name) > 0:
			for id,name in renamedObjects_Id_Name.items():
				self.freecadObjectChanged(BlenderToCadObject(name, id), 'Label', enableReInitLeftColumn=False)

			#reinit left column due it was supressed during bulk renaming
			self.initLeftColumnTopLevelItems(self.form.objectAssignmentFilterLeft.text())

		if len(deletedObjects_Id_Name) > 0:
			for id,name in deletedObjects_Id_Name.items():
				self.freecadBeforeObjectDeleted(BlenderToCadObject(name, id))

		if len(newObjects_Name_Id) > 0:
			for name,id in newObjects_Name_Id.items():
				self.freecadObjectCreated(BlenderToCadObject(name, id))

		self.previousObjectsList_Id_Name = currentObjectsList_Id_Name
		self.previousObjectsList_Name_Id = currentObjectsList_Name_Id

	def simParamsMinDecrementValueChanged(self, newValue):
		if newValue == 0:
			s = '( -inf dB )'
		else:
			s = '( ' + str(np.round(10 * np.log10(newValue), decimals=2)) + ' dB )'
		self.form.simParamsMinDecrementdBLabel.setText(s)

	def BCxminCurrentIndexChanged(self, index):
		self.form.PMLxmincells.setEnabled(self.form.BCxmin.currentText() == "PML")

	def BCxmaxCurrentIndexChanged(self, index):
		self.form.PMLxmaxcells.setEnabled(self.form.BCxmax.currentText() == "PML")

	def BCyminCurrentIndexChanged(self, index):
		self.form.PMLymincells.setEnabled(self.form.BCymin.currentText() == "PML")

	def BCymaxCurrentIndexChanged(self, index):
		self.form.PMLymaxcells.setEnabled(self.form.BCymax.currentText() == "PML")

	def BCzminCurrentIndexChanged(self, index):
		self.form.PMLzmincells.setEnabled(self.form.BCzmin.currentText() == "PML")

	def BCzmaxCurrentIndexChanged(self, index):
		self.form.PMLzmaxcells.setEnabled(self.form.BCzmax.currentText() == "PML")

	def eraseAuxGridButtonClicked(self):
		print("--> Start removing auxiliary gridlines from 3D view.")
		auxGridLines = self.cadHelpers.getObjects()
		for gridLine in auxGridLines:
			print("--> Removing " + gridLine.Label + " from 3D view.")
			if "auxGridLine" in gridLine.Label:
				self.cadHelpers.removeObject(gridLine.Name)
		print("--> End removing auxiliary gridlines from 3D view.")

	def createUserdefGridLinesFromCurrentButtonClicked(self):
		"""
		print("--> Start creating user defined grid from 3D model.")
		allObjects = self.cadHelpers.getObjects()
		gridLineListX = []
		gridLineListY = []
		gridLineListZ = []
		for gridLine in allObjects:
			if "auxGridLine" in gridLine.Label:
				gridLineDirection = abs(gridLine.End - gridLine.Start)
				if (gridLineDirection[0] > 0):
					gridLineListX.append(gridLine)


		print("Discovered " + str(len(gridLineList)) + " gridlines in model.")
		print("--> End creating user defined grid from 3D model.")
		"""
		self.guiHelpers.displayMessage("createUserdefGridLinesFromCurrentButtonClicked")

	def displayXYGridLinesInModelButtonClicked(self):
		print('displayXYGridLinesInModelButtonClicked: start draw whole XY grid for each object')

		gridCategory = self.form.objectAssignmentRightTreeWidget.findItems("Grid", QtCore.Qt.MatchFixedString)[0]
		for gridItemIndex in range(gridCategory.childCount()):
			for objIndex in range(gridCategory.child(gridItemIndex).childCount()):
				currItem = gridCategory.child(gridItemIndex).child(objIndex)
				print(currItem.text(0))
				self.objectDrawGrid(currItem)

	def updateComboboxWithAllowedItems(self, comboboxRef, sourceCategory="", allowedTypes=[], isActive=None):
		currentItemText = comboboxRef.currentText()
		comboboxRef.clear()

		currentIndex = 0
		addedItemCounter = 0
		for k in range(0, self.form.objectAssignmentRightTreeWidget.topLevelItemCount()):
			if (self.form.objectAssignmentRightTreeWidget.topLevelItem(k).text(0) == sourceCategory):
				for l in range(0, self.form.objectAssignmentRightTreeWidget.topLevelItem(k).childCount()):
					itemSettings = self.form.objectAssignmentRightTreeWidget.topLevelItem(k).child(l).data(0, QtCore.Qt.UserRole)

					#Check if item is applicable to be added into combobox
					if ((len(allowedTypes) == 0 or itemSettings.type in allowedTypes) and (isActive == None or (hasattr(itemSettings, 'isActive') and itemSettings.isActive == isActive))):
						if (self.form.objectAssignmentRightTreeWidget.topLevelItem(k).child(l).childCount() > 0):

							#iterate through each added object into port category and generate name for it in format "[category name] - [assigned object label]"
							for m in range(0, self.form.objectAssignmentRightTreeWidget.topLevelItem(k).child(l).childCount()):
								subNewItemText = self.form.objectAssignmentRightTreeWidget.topLevelItem(k).child(l).text(0)
								subNewItemText += " - "
								subNewItemText += self.form.objectAssignmentRightTreeWidget.topLevelItem(k).child(l).child(m).text(0)
								comboboxRef.addItem(subNewItemText)
								if (subNewItemText == currentItemText):
									currentIndex = addedItemCounter
								addedItemCounter += 1
						"""
						else:
							newItemText = self.form.objectAssignmentRightTreeWidget.topLevelItem(k).child(l).text(0)
							comboboxRef.addItem(newItemText)
							if (newItemText == currentItemText):
								currentIndex = addedItemCounter
							addedItemCounter += 1
						"""

		comboboxRef.setCurrentIndex(currentIndex)

	def updateObjectAssignmentRightTreeWidgetItemData(self, groupName, itemName, data):
		updatedItems = self.form.objectAssignmentRightTreeWidget.findItems(
			itemName,
			QtCore.Qt.MatchExactly | QtCore.Qt.MatchFlag.MatchRecursive
			)

		#there can be more items in right column which has same name, like air under MAterials and Grid, so always is needed to compare if parent
		#is same as parent from update function when this was called to update new settings
		for item in updatedItems:
			if item.parent().text(0) == groupName:
				item.setData(0, QtCore.Qt.UserRole, data)

	def renameObjectAssignmentRightTreeWidgetItem(self, groupName, itemOldName, itemNewName):
		updatedItems = self.form.objectAssignmentRightTreeWidget.findItems(
			itemOldName,
			QtCore.Qt.MatchExactly | QtCore.Qt.MatchFlag.MatchRecursive
			)

		#there can be more items in right column which has same name, like air under MAterials and Grid, so always is needed to compare if parent
		#is same as parent from update function when this was called to update new settings
		for item in updatedItems:
			if item.parent().text(0) == groupName:
				item.setText(0, itemNewName)

	def renameObjectAssignmentPriorityTreeViewItem(self, groupName, itemOldName, itemNewName):
		searchStr = groupName + ", " + itemOldName
		updatedItems = self.form.objectAssignmentPriorityTreeView.findItems(
			searchStr,
			QtCore.Qt.MatchStartsWith
			)

		for item in updatedItems:
			newName = groupName + ", " + itemNewName + ", " + item.text(0)[len(searchStr)+2:]	#must take end of mesh priority item name, means length of searchStr + len(", ")
			self.cadHelpers.printWarning(f"Updating {item.text(0)} -> {newName}")
			item.setText(0, newName)

	def renameMeshPriorityTreeViewItem(self, itemOldName, itemNewName):
		searchStr = "Grid, " + itemOldName
		updatedItems = self.form.meshPriorityTreeView.findItems(
			searchStr,
			QtCore.Qt.MatchStartsWith
			)

		for item in updatedItems:
			newName = "Grid, " + itemNewName + ", " + item.text(0)[len(searchStr)+2:]	#must take end of mesh priority item name, means length of searchStr + len(", ")
			self.cadHelpers.printWarning(f"Updating {item.text(0)} -> {newName}")
			item.setText(0, newName)

	def renameTreeViewItem(self, treeViewRef, itemOldName, itemNewName):
		"""
		Renames item in tree view to new name. String search must match exactly.
		:param treeViewRef: Reference to tree view widget
		:param itemOldName: Old item name.
		:param itemNewName: New item name.
		:return:
		"""
		updatedItems = treeViewRef.findItems(
			itemOldName,
			QtCore.Qt.MatchExactly
			)

		for item in updatedItems:
			item.setText(0, itemNewName)

	def objectAssignmentRightTreeWidgetItemSelectionChanged(self):
		currItem = self.form.objectAssignmentRightTreeWidget.currentItem()
		currItemLabel = None

		#check if there is some current item due this function is trigered also during deleting all items in right assignment widget and then currItem is None
		if currItem:
			currItemLabel = currItem.text(0)

		if (currItemLabel):
			self.cadHelpers.clearSelection()
			self.cadHelpers.selectObjectByLabel(currItemLabel)

	def objectAssignmentLeftTreeWidgetItemSelectionChanged(self):
		currItem = self.form.objectAssignmentLeftTreeWidget.currentItem()
		currItemLabel = None

		#check if there is some current item due this function is trigered also during deleting all items in right assignment widget and then currItem is None
		if currItem:
			currItemLabel = currItem.text(0)

		if (currItemLabel):
			self.cadHelpers.clearSelection()
			self.cadHelpers.selectObjectByLabel(currItemLabel)

	def objectAssignmentRightTreeWidgetContextClicked(self, event):
		self.objAssignCtxMenu = QtWidgets.QMenu(self.form.objectAssignmentRightTreeWidget)
		action_expand   = self.objAssignCtxMenu.addAction("Expand all")
		actioN_collapse = self.objAssignCtxMenu.addAction("Collapse all")
		menu_action = self.objAssignCtxMenu.exec_(self.form.objectAssignmentRightTreeWidget.mapToGlobal(event))
		if menu_action is not None:
			if menu_action == action_expand:
				self.form.objectAssignmentRightTreeWidget.expandAll()
			if menu_action == actioN_collapse:
				self.form.objectAssignmentRightTreeWidget.collapseAll()

	#
	#	Handler for DOUBLE CLICK on grid item in FreeCAD objects list
	#
	def objectAssignmentLeftTreeWidgetItemDoubleClicked(self):
		self.onMoveRight()

	#
	#	Handler for DOUBLE CLICK on grid item in object assignment list
	#
	def objectAssignmentRightTreeWidgetItemDoubleClicked(self):
		currItem = self.form.objectAssignmentRightTreeWidget.currentItem()
		self.objectDrawGrid(currItem)

	#
	#	Draw auxiliary grid in FreeCAD 3D view
	#
	def objectDrawGrid(self, currItem):
		#
		#	Drawing auxiliary object grid for meshing.
		#
		#		example how to draw line for grid: self.cadHelpers.drawDraftLine("gridXY", [-78.0, -138.0, 0.0], [5.0, -101.0, 0.0])

		currSetting = currItem.data(0, QtCore.Qt.UserRole)
		genScript = ""

		#	must be selected FreeCAD object which is child of grid item which gridlines will be draw
		gridObj =  self.cadHelpers.getObjectsByLabel(currItem.text(0))
		if ("FreeCADSettingItem" in currSetting.type):
			if ("GridSettingsItem" in currItem.parent().data(0, QtCore.Qt.UserRole).__class__.__name__):
				currSetting = currItem.parent().data(0, QtCore.Qt.UserRole)
			else:
				self.guiHelpers.displayMessage('Cannot draw grid for non-grid item object.')
				return
		else:
			self.guiHelpers.displayMessage('Cannot draw grid for object group.')
			return

		bbCoords = gridObj[0].Shape.BoundBox

		print("Start drawing aux grid for: " + currSetting.name)
		print("Enabled coords: " + str(currSetting.xenabled) + " " + str(currSetting.yenabled) + " " + str(currSetting.zenabled))

		#getting model boundaries to draw gridlines properly
		modelMinX, modelMinY, modelMinZ, modelMaxX, modelMaxY, modelMaxZ = self.cadHelpers.getModelBoundaryBox(self.form.objectAssignmentRightTreeWidget)

		#don't know why I put here this axis list code snippet probably to include case if there are some auxiliary axis but now seems useless
		#THERE IS QUESTION IN WHICH PLANE GRID SHOULD BE DRAWN IF in XY, XZ or YZ
		currGridAxis = self.form.auxGridAxis.currentText().lower()
		print("Aux grid axis: " + currGridAxis)

		refUnit = currSetting.getSettingsUnitAsNumber()
		#refUnit = 1
		print("Current object grid units set as number to: refUnit: " + str(refUnit))

		"""
		axisList = collections.deque(['x', 'y', 'z'])
		while axisList[0] != currGridAxis:
			axisList.rotate()
		"""

		if (currSetting.coordsType == 'cylindrical' and currGridAxis == "z"):

			if (currSetting.getType() == 'Fixed Distance'):
				#need to be done for this case
				pass

			elif (currSetting.getType() == 'Fixed Count'):

	            #collecting Z coordinates where grid will be drawn, grid will be drawn in XY plane
				zAuxGridCoordList = []
				if (currSetting.zenabled):
					if int(currSetting.getXYZ(refUnit)['z']) != 0:

						if int(currSetting.getXYZ(refUnit)['z']) == 1:
							zlines = np.array([(bbCoords.ZMin + bbCoords.ZMax)/2])
						else:
							zlines = np.linspace(bbCoords.ZMin, bbCoords.ZMax, int(currSetting.getXYZ(refUnit)['z']))

						#collecting Z coordinates where grid layers will be drawn
						for zGridLine in zlines:
							zAuxGridCoordList.append(zGridLine)

				print("zlines")
				print(zAuxGridCoordList)
				if len(zAuxGridCoordList) == 0:
					zAuxGridCoordList.append(bbCoords.ZMax)

				for zAuxGridCoord in zAuxGridCoordList:

					bbPointsVectors = [self.cadHelpers.Vector(bbCoords.YMin, bbCoords.XMin, 0), self.cadHelpers.Vector(bbCoords.YMin, bbCoords.XMax, 0), self.cadHelpers.Vector(bbCoords.YMax, bbCoords.XMin, 0), self.cadHelpers.Vector(bbCoords.YMax, bbCoords.XMax, 0)]
					angle1 = math.atan2(bbCoords.YMin, bbCoords.XMin) + 2*math.pi % (2*math.pi)
					angle2 = math.atan2(bbCoords.YMin, bbCoords.XMax) + 2*math.pi % (2*math.pi)
					angle3 = math.atan2(bbCoords.YMax, bbCoords.XMin) + 2*math.pi % (2*math.pi)
					angle4 = math.atan2(bbCoords.YMax, bbCoords.XMax) + 2*math.pi % (2*math.pi)

					minAngle = min([angle1, angle2, angle3, angle4])
					maxAngle = max([angle1, angle2, angle3, angle4])
					radius = max([math.sqrt(modelMinX**2 + modelMinY**2), math.sqrt(modelMaxX**2 + modelMaxY**2)])

					print("Calculate ylines for cylindrical coords.")
					print("minAngle: " + str(minAngle))
					print("maxAngle: " + str(maxAngle))
					print("radius: " + str(radius))

					#DRAW X LINES auxiliary grid in 3D view
					if (currSetting.xenabled):
						a = np.array([angle1, angle2, angle3, angle4])
						indicesMin = a.argmin()
						indicesMax = a.argmax()
						closestLineToCenter = bbPointsVectors[indicesMin] - bbPointsVectors[indicesMax]

						#minRadius = closestLineToCenter.distanceToPoint(self.cadHelpers.Vector(0,0,0))
						minRadius = abs((bbPointsVectors[indicesMax].x - bbPointsVectors[indicesMin].x)*bbPointsVectors[indicesMin].y - (bbPointsVectors[indicesMax].y - bbPointsVectors[indicesMin].y)*bbPointsVectors[indicesMin].x)/closestLineToCenter.Length
						maxRadius = max([math.sqrt(bbCoords.XMin**2 + bbCoords.YMin**2), math.sqrt(bbCoords.XMax**2 + bbCoords.YMax**2)])

						if float(currSetting.getXYZ(refUnit)['x']) == 1:
							xlines = np.array([(minRadius + maxRadius)/2])
						else:
							xlines = np.linspace(minRadius, maxRadius, int(currSetting.getXYZ(refUnit)['x']))

						for xGridLine in xlines:
							self.cadHelpers.drawDraftCircle("auxGridLine", self.cadHelpers.Vector(0,0,zAuxGridCoord), xGridLine)

					#DRAW Y LINES auxiliary grid in 3D view
					if (currSetting.yenabled):
						if float(currSetting.getXYZ(refUnit)['y']) == 1:
							ylines = np.array([(minAngle, maxAngle)/2])
						else:
							ylines = np.linspace(minAngle, maxAngle, int(currSetting.getXYZ(refUnit)['y']))

						print(ylines)

						for yGridLine in ylines:
							self.cadHelpers.drawDraftLine("auxGridLine", [0, 0, zAuxGridCoord], [math.cos(yGridLine)*radius, math.sin(yGridLine)*radius, zAuxGridCoord])

		elif (currSetting.coordsType == 'rectangular' and currGridAxis == "z"):

			#######################################################################################################################################################################
		  	# Z grid axis
			#######################################################################################################################################################################

			print("Drawing GRID in Z axis.")

			if (currSetting.getType() == 'Fixed Distance'):

				#here adding Z coordinates for which grid will be drawn so grid will be drawn in XY plane, so here are collected just Z coords for which it will be drawn
				zAuxGridCoordList = []
				if (currSetting.zenabled):
					if float(currSetting.getXYZ(refUnit)['z']) != 0:
						zlines = np.arange(bbCoords.ZMin, bbCoords.ZMax, currSetting.getXYZ(refUnit)['z'])    #split Z interval and generate Z layers
						for zGridLine in zlines:
							zAuxGridCoordList.append(zGridLine)
				if len(zAuxGridCoordList) == 0:
					zAuxGridCoordList.append(bbCoords.ZMax)

				for zAuxGridCoord in zAuxGridCoordList:
					#DRAW X LINES auxiliary grid in 3D view
					if (currSetting.xenabled):
						if float(currSetting.getXYZ(refUnit)['x']) !=  0:
							xlines = np.arange(bbCoords.XMin, bbCoords.XMax, currSetting.getXYZ(refUnit)['x'])
							for xGridLine in xlines:
								#self.cadHelpers.drawDraftLine("auxGridLine", [xGridLine, bbCoords.YMin, zAuxGridCoord], [xGridLine, bbCoords.YMax, zAuxGridCoord])
								self.cadHelpers.drawDraftLine("auxGridLine", [xGridLine, modelMinY, zAuxGridCoord], [xGridLine, modelMaxY, zAuxGridCoord])

					#DRAW Y LINES auxiliary grid in 3D view
					if (currSetting.yenabled):
						if float(currSetting.getXYZ(refUnit)['y']) != 0:
							ylines = np.arange(bbCoords.YMin, bbCoords.YMax, currSetting.getXYZ(refUnit)['y'])
							for yGridLine in ylines:
								#self.cadHelpers.drawDraftLine("auxGridLine", [bbCoords.XMin, yGridLine, zAuxGridCoord], [bbCoords.XMax, yGridLine, zAuxGridCoord])
								self.cadHelpers.drawDraftLine("auxGridLine", [modelMinX, yGridLine, zAuxGridCoord], [modelMaxX, yGridLine, zAuxGridCoord])

			elif (currSetting.getType() == 'Fixed Count'):

	            #collecting Z coordinates where grid will be drawn, grid will be drawn in XY plane
				zAuxGridCoordList = []
				if (currSetting.zenabled):
					if float(currSetting.getXYZ(refUnit)['z']) != 0:
						if float(currSetting.getXYZ(refUnit)['z']) == 1:
							zlines = np.arange(bbCoords.ZMin, bbCoords.ZMax, int(currSetting.getXYZ(refUnit)['z']))
						else:
							zlines = np.array([(bbCoords.ZMin + bbCoords.ZMax)/2])

						#collecting Z coordinates where grid layers will be drawn
						for zGridLine in zlines:
							zAuxGridCoordList.append(zGridLine)
				if len(zAuxGridCoordList) == 0:
					zAuxGridCoordList.append(bbCoords.ZMax)

				for zAuxGridCoord in zAuxGridCoordList:
					#DRAW X LINES auxiliary grid in 3D view
					if (currSetting.xenabled):
						if float(currSetting.getXYZ(refUnit)['x']) == 1:
							xlines = np.array([(bbCoords.XMin + bbCoords.XMax)/2])
						else:
							xlines = np.linspace(bbCoords.XMin, bbCoords.XMax, int(currSetting.getXYZ(refUnit)['x']))

						for xGridLine in xlines:
							#self.cadHelpers.drawDraftLine("auxGridLine", [xGridLine, bbCoords.YMin, zAuxGridCoord], [xGridLine, bbCoords.YMax, zAuxGridCoord])
							self.cadHelpers.drawDraftLine("auxGridLine", [xGridLine, modelMinY, zAuxGridCoord], [xGridLine, modelMaxY, zAuxGridCoord])

					#DRAW Y LINES auxiliary grid in 3D view
					if (currSetting.yenabled):
						if float(currSetting.getXYZ(refUnit)['y']) == 1:
							ylines = np.array([(bbCoords.YMin + bbCoords.YMax)/2])
						else:
							ylines = np.linspace(bbCoords.YMin, bbCoords.YMax, int(currSetting.getXYZ(refUnit)['y']))

						for yGridLine in ylines:
							#self.cadHelpers.drawDraftLine("auxGridLine", [bbCoords.XMin, yGridLine, zAuxGridCoord], [bbCoords.XMax, yGridLine, zAuxGridCoord])
							self.cadHelpers.drawDraftLine("auxGridLine", [modelMinX, yGridLine, zAuxGridCoord], [modelMaxX, yGridLine, zAuxGridCoord])

			elif (currSetting.getType() == 'User Defined'):
				#UNIT FOR MESH
				genScript += "meshUnit = " + currSetting.getUnitAsScriptLine() + "; % all length in mm\n"
				genScript += "mesh = " + currSetting.getXYZ(refUnit) + ";\n"

		elif (currSetting.coordsType == 'rectangular' and currGridAxis == "x"):

			#######################################################################################################################################################################
		  	# X grid axis - STILL EXPERIMENTAL require REPAIR
			#######################################################################################################################################################################

			print("Drawing GRID in X axis.")

			if (currSetting.getType() == 'Fixed Distance'):

				#here adding Z coordinates for which grid will be drawn so grid will be drawn in XY plane, so here are collected just Z coords for which it will be drawn
				xAuxGridCoordList = []
				if (currSetting.xenabled):
					if float(currSetting.getXYZ(refUnit)['x']) != 0:
						xlines = np.arange(bbCoords.XMin, bbCoords.XMax, currSetting.getXYZ(refUnit)['x'])    #split Z interval and generate Z layers
						for xGridLine in xlines:
							xAuxGridCoordList.append(xGridLine)
				if len(xAuxGridCoordList) == 0:
					xAuxGridCoordList.append(bbCoords.XMax)

				for xAuxGridCoord in xAuxGridCoordList:
					#DRAW Z LINES auxiliary grid in 3D view
					if (currSetting.zenabled):
						if float(currSetting.getXYZ(refUnit)['z']) !=  0:
							zlines = np.arange(bbCoords.ZMin, bbCoords.ZMax, currSetting.getXYZ(refUnit)['z'])
							for zGridLine in zlines:
								self.cadHelpers.drawDraftLine("auxGridLine", [xAuxGridCoord, modelMinY, zGridLine], [xAuxGridCoord, modelMaxY, zGridLine])

					#DRAW Y LINES auxiliary grid in 3D view
					if (currSetting.yenabled):
						if float(currSetting.getXYZ(refUnit)['y']) != 0:
							ylines = np.arange(bbCoords.YMin, bbCoords.YMax, currSetting.getXYZ(refUnit)['y'])
							for yGridLine in ylines:
								self.cadHelpers.drawDraftLine("auxGridLine", [xAuxGridCoord, yGridLine, modelMinZ], [xAuxGridCoord, yGridLine, modelMaxZ])

			elif (currSetting.getType() == 'Fixed Count'):

	            #collecting Z coordinates where grid will be drawn, grid will be drawn in XY plane
				xAuxGridCoordList = []
				if (currSetting.xenabled):
					if float(currSetting.getXYZ(refUnit)['x']) != 0:
						if float(currSetting.getXYZ(refUnit)['x']) == 1:
							xlines = np.array([(bbCoords.XMin + bbCoords.XMax)/2])
						else:
							xlines = np.arange(bbCoords.XMin, bbCoords.XMax, int(currSetting.getXYZ(refUnit)['x']))   #collecting Z coordinates where grid layers will be drawn

						for xGridLine in xlines:
							xAuxGridCoordList.append(xGridLine)

				if len(xAuxGridCoordList) == 0:
					xAuxGridCoordList.append(bbCoords.XMax)

				for xAuxGridCoord in xAuxGridCoordList:
					#DRAW X LINES auxiliary grid in 3D view
					if (currSetting.zenabled):
						if float(currSetting.getXYZ(refUnit)['z']) == 1:
							zlines = np.array([(bbCoords.ZMin + bbCoords.ZMax)/2])
						else:
							zlines = np.linspace(bbCoords.ZMin, bbCoords.ZMax, int(currSetting.getXYZ(refUnit)['z']))

						for zGridLine in zlines:
							self.cadHelpers.drawDraftLine("auxGridLine", [xAuxGridCoord, modelMinY, zGridLine], [xAuxGridCoord, modelMaxY, zGridLine])

					#DRAW Y LINES auxiliary grid in 3D view
					if (currSetting.yenabled):
						if float(currSetting.getXYZ(refUnit)['y']) == 1:
							ylines = np.array([(bbCoords.YMin + bbCoords.YMax)/2])
						else:
							ylines = np.linspace(bbCoords.YMin, bbCoords.YMax, int(currSetting.getXYZ(refUnit)['y']))

						for yGridLine in ylines:
								self.cadHelpers.drawDraftLine("auxGridLine", [xAuxGridCoord, yGridLine, modelMinZ], [xAuxGridCoord, yGridLine, modelMaxZ])

			elif (currSetting.getType() == 'User Defined'):
				#UNIT FOR MESH
				genScript += "meshUnit = " + currSetting.getUnitAsScriptLine() + "; % all length in mm\n"
				genScript += "mesh = " + currSetting.getXYZ(refUnit) + ";\n"

		elif (currSetting.coordsType == 'rectangular' and currGridAxis == "y"):

			#######################################################################################################################################################################
		  	# Y grid axis - NOT IMPLEMENTED
			#######################################################################################################################################################################

			print("Drawing GRID in Y axis.")

			if (currSetting.getType() == 'Fixed Distance'):

				#here adding Z coordinates for which grid will be drawn so grid will be drawn in XY plane, so here are collected just Z coords for which it will be drawn
				yAuxGridCoordList = []
				if (currSetting.yenabled):
					if float(currSetting.getXYZ(refUnit)['y']) != 0:
						ylines = np.arange(bbCoords.YMin, bbCoords.YMax, currSetting.getXYZ(refUnit)['y'])    #split Y interval and generate Z layers
						for yGridLine in ylines:
							yAuxGridCoordList.append(yGridLine)
				if len(yAuxGridCoordList) == 0:
					yAuxGridCoordList.append(bbCoords.YMax)

				for yAuxGridCoord in yAuxGridCoordList:
					#DRAW Z LINES auxiliary grid in 3D view
					if (currSetting.zenabled):
						if float(currSetting.getXYZ(refUnit)['z']) !=  0:
							zlines = np.arange(bbCoords.ZMin, bbCoords.ZMax, currSetting.getXYZ(refUnit)['z'])
							for zGridLine in zlines:
								self.cadHelpers.drawDraftLine("auxGridLine", [modelMinX, yAuxGridCoord, zGridLine], [modelMaxX, yAuxGridCoord, zGridLine])

					#DRAW X LINES auxiliary grid in 3D view
					if (currSetting.xenabled):
						if float(currSetting.getXYZ(refUnit)['x']) != 0:
							xlines = np.arange(bbCoords.XMin, bbCoords.XMax, currSetting.getXYZ(refUnit)['x'])
							for xGridLine in xlines:
								self.cadHelpers.drawDraftLine("auxGridLine", [xGridLine, yAuxGridCoord, modelMinZ], [xGridLine, yAuxGridCoord, modelMaxZ])

			elif (currSetting.getType() == 'Fixed Count'):

	            #collecting Z coordinates where grid will be drawn, grid will be drawn in XY plane
				yAuxGridCoordList = []
				if (currSetting.yenabled):
					if float(currSetting.getXYZ(refUnit)['y']) != 0:
						if float(currSetting.getXYZ(refUnit)['y']) == 1:
							ylines = np.array([(bbCoords.YMin + bbCoords.YMax)/2])
						else:
							ylines = np.arange(bbCoords.YMin, bbCoords.YMax, int(currSetting.getXYZ(refUnit)['y']))   #collecting Y coordinates where grid layers will be drawn

						for yGridLine in ylines:
							yAuxGridCoordList.append(yGridLine)

				if len(yAuxGridCoordList) == 0:
					yAuxGridCoordList.append(bbCoords.YMax)

				for yAuxGridCoord in yAuxGridCoordList:
					#DRAW Z LINES auxiliary grid in 3D view
					if (currSetting.zenabled):
						if float(currSetting.getXYZ(refUnit)['z']) == 1:
							zlines = np.array([(bbCoords.ZMin + bbCoords.ZMax)/2])
						else:
							zlines = np.linspace(bbCoords.ZMin, bbCoords.ZMax, int(currSetting.getXYZ(refUnit)['z']))

						for zGridLine in zlines:
							self.cadHelpers.drawDraftLine("auxGridLine", [modelMinX, yAuxGridCoord, zGridLine], [modelMaxX, yAuxGridCoord, zGridLine])

					#DRAW X LINES auxiliary grid in 3D view
					if (currSetting.xenabled):
						if float(currSetting.getXYZ(refUnit)['x']) == 1:
							xlines = np.array([(bbCoords.XMin + bbCoords.XMax)/2])
						else:
							xlines = np.linspace(bbCoords.XMin, bbCoords.XMax, int(currSetting.getXYZ(refUnit)['x']))

						for xGridLine in xlines:
							self.cadHelpers.drawDraftLine("auxGridLine", [xGridLine, yAuxGridCoord, modelMinZ], [xGridLine, yAuxGridCoord, modelMaxZ])

			elif (currSetting.getType() == 'User Defined'):
				#UNIT FOR MESH
				genScript += "meshUnit = " + currSetting.getUnitAsScriptLine() + "; % all length in mm\n"
				genScript += "mesh = " + currSetting.getXYZ(refUnit) + ";\n"

		#update whole document
		self.cadHelpers.recompute()
		print("---> Aux grid drawing finished. \n" + genScript)

	#######################################################################################################################################################################
  	# END GRID DRAWING
	#######################################################################################################################################################################

	def initLeftColumnTopLevelItems(self, filterStr = ""):
		self.form.objectAssignmentLeftTreeWidget.clear()

		items = self.cadHelpers.getOpenEMSObjects(filterStr)
		treeItems = []
		for i in items:
			#print("openEMS object to export:" + i.Label)

			# ADDING ITEMS with UserData object which store them in intelligent way
			#
			topItem = QtWidgets.QTreeWidgetItem([i.Label])
			itemData = FreeCADSettingsItem(name = i.Label, freeCadId = i.Name)
			topItem.setData(0, QtCore.Qt.UserRole, itemData)
			if (i.Name.find("Sketch") > -1):
				topItem.setIcon(0, QtGui.QIcon(os.path.join(self.APP_DIR, "img", "wire.svg")))
			elif (i.Name.find("Discretized_Edge") > -1):
				topItem.setIcon(0, QtGui.QIcon(os.path.join(self.APP_DIR, "img", "curve.svg")))
			else:
				topItem.setIcon(0, QtGui.QIcon(os.path.join(self.APP_DIR, "img", "object.svg")))

			treeItems.append(topItem)
			self.internalObjectNameLabelList[i.Name] = i.Label		#add object label into internal list for case when label change to update all object labels in GUI

		self.form.objectAssignmentLeftTreeWidget.insertTopLevelItems(0, treeItems)

	#
	#	ABORT simulation button handler
	#		write empty file ABORT into simulation_output/ folder what should abort simulation in next iteration
	#
	def abortSimulationButtonClicked(self, outputDir=None):
		programdir = os.path.dirname(self.cadHelpers.getCurrDocumentFileName())

		if not outputDir is None:
			absoluteOutputDir = os.path.join(outputDir, "simulation_output")
		else:
			absoluteOutputDir = os.path.join(programdir, "simulation_output")

		outFile = os.path.join(absoluteOutputDir, "ABORT")
		print("------------->" + outFile)

		if os.path.exists(absoluteOutputDir):
			f = open(outFile, "w+", encoding='utf-8')
			f.write("THIS CAN BE JUST EMPTY FILE. ABORT simulation.")
			f.close()
			print(f"ABORT file written into {absoluteOutputDir}")
			self.guiHelpers.displayMessage(f"ABORT file written into {absoluteOutputDir}", forceModal=False)
		else:
			print(f"Simulation simulation_output/ folder not found at expected path: {absoluteOutputDir}")
			self.guiHelpers.displayMessage(f"Simulation simulation_output/ folder not found at expected path: {absoluteOutputDir}", forceModal=False)

	def materialUserDeinedRadioButtonToggled(self):
		if (self.form.materialUserDefinedRadioButton.isChecked()):
			self.form.materialEpsilonNumberInput.setEnabled(True)
			self.form.materialMueNumberInput.setEnabled(True)
			self.form.materialKappaNumberInput.setEnabled(True)
			self.form.materialSigmaNumberInput.setEnabled(True)
		else:
			self.form.materialEpsilonNumberInput.setEnabled(False)
			self.form.materialMueNumberInput.setEnabled(False)
			self.form.materialKappaNumberInput.setEnabled(False)
			self.form.materialSigmaNumberInput.setEnabled(False)

	def materialConductingSheetRadioButtonToggled(self):
		if (self.form.materialConductingSheetRadioButton.isChecked()):
			self.form.materialConductingSheetThickness.setEnabled(True)
			self.form.materialConductingSheetUnits.setEnabled(True)
			self.form.materialConductingSheetConductivity.setEnabled(True)
		else:
			self.form.materialConductingSheetThickness.setEnabled(False)
			self.form.materialConductingSheetUnits.setEnabled(False)
			self.form.materialConductingSheetConductivity.setEnabled(False)

	def applyObjectAssignmentFilter(self):
		print("Filter left column")
		filterStr = self.form.objectAssignmentFilterLeft.text()
		self.initLeftColumnTopLevelItems(filterStr)

	#
	#	Get COORDINATION TYPE
	#		this function traverse priority tree view and return coordination type of the most high item
	#
	#	returns string coords type
	#
	def getModelCoordsType(self):
		for k in range(self.form.objectAssignmentPriorityTreeView.topLevelItemCount()):
			priorityObjNameSplitted = self.form.objectAssignmentPriorityTreeView.topLevelItem(k).text(0).split(',')
			if (priorityObjNameSplitted[0].strip() == "Grid"):
				gridCategoryItem = self.form.objectAssignmentRightTreeWidget.findItems("Grid", QtCore.Qt.MatchFixedString)
				gridObj = [gridCategoryItem[0].child(x) for x in range(gridCategoryItem[0].childCount()) if gridCategoryItem[0].child(x).text(0) == priorityObjNameSplitted[1].strip()]
				return gridObj[0].data(0, QtCore.Qt.UserRole).coordsType
		return ""

	def show(self):
		self.form.show()

	#
	#	Button << to assign object from FreeCAD to OpenEMS solver structure
	#
	def onMoveLeft(self):
		print("Button << clicked.")
		rightItem = self.form.objectAssignmentRightTreeWidget.selectedItems()[0]

		#
		#	REMOVE FROM PRIORITY OBJECT ASSIGNMENT tree view
		#
		prioritySettingsItemName = rightItem.parent().parent().text(0) + ", " + rightItem.parent().text(0) + ", " + rightItem.text(0)

		#going through items in priority object list and searching for name, when matched it's removed from list
		itemsCount = self.form.objectAssignmentPriorityTreeView.topLevelItemCount()
		for k in range(itemsCount):
			priorityItem = self.form.objectAssignmentPriorityTreeView.topLevelItem(k)
			if prioritySettingsItemName in priorityItem.text(0):
				self.form.objectAssignmentPriorityTreeView.takeTopLevelItem(k)
				print("Removing item " + prioritySettingsItemName + " from priority object list.")
				break	#this will break loop SO JUST ONE ITEM FROM PRIORITY LIST IS DELETED

		#
		#	REMOVE FROM PRIORITY MESH ASSIGNMENT tree view
		#

		#going through items in priority mesh list and searching for name, when matched it's removed from list
		itemsCount = self.form.meshPriorityTreeView.topLevelItemCount()
		for k in range(itemsCount):
			priorityItem = self.form.meshPriorityTreeView.topLevelItem(k)
			if prioritySettingsItemName in priorityItem.text(0):
				self.form.meshPriorityTreeView.takeTopLevelItem(k)
				print("Removing item " + prioritySettingsItemName + " from priority mesh list.")
				break	#this will break loop SO JUST ONE ITEM FROM PRIORITY LIST IS DELETED

		#if removing from Port category emit signal to update comboboxes with ports
		portObjectIsRemoved = False
		if (rightItem.parent().parent().text(0) == "Port"):
			portObjectIsRemoved = True
			self.guiSignals.portsChanged.emit("remove")

		probeObjectIsRemoved = False
		if (rightItem.parent().parent().text(0) == "Probe"):
			probeObjectIsRemoved = True
			self.guiSignals.probesChanged.emit("remove")

		#
		#	REMOVE ITEM FROM OpenEMS Simulation assignments tree view
		#
		rightItem.parent().removeChild(rightItem)

		#if port object was removed emit signal here when it's really removed from right column
		if (portObjectIsRemoved):
			self.guiSignals.portsChanged.emit("remove")
		if (probeObjectIsRemoved):
			self.guiSignals.probesChanged.emit("remove")

		return

	#
	#	Button >> to remove object assignment
	#
	def onMoveRight(self):
		print("Button >> clicked.")
		rightItem = self.form.objectAssignmentRightTreeWidget.selectedItems()[0]

		#check if item is type of SettingsItem based on its class name and if yes then add subitems into it
		print("Adding item into right column, type: " + str(type(rightItem.data(0, QtCore.Qt.UserRole))))
		reResult = re.search("([A-Za-z]*)SettingsItem'", str(type(rightItem.data(0, QtCore.Qt.UserRole))))
		if (reResult):
			if (reResult.group(1).lower() == 'excitation'):
				self.guiHelpers.displayMessage("Excitation doesn't accept any objects.")
				return
			if (reResult.group(1).lower() == 'freecad'):
				self.guiHelpers.displayMessage("FreeCAD object cannot have child item.")
				return

			for itemToAdd in self.form.objectAssignmentLeftTreeWidget.selectedItems():
				# here are created 2 clones of item in left column to be putted into right column into some category
				# as material, port or something and there is also priority list where another clone is inserted
				leftItem = itemToAdd.clone()
				leftItem2 = itemToAdd.clone()

				# CHECK FOR DUPLICATES OF object in category where object is added
				isObjAlreadyInCategory = False
				itemWithSameName = self.form.objectAssignmentRightTreeWidget.findItems(leftItem.text(0), QtCore.Qt.MatchFixedString | QtCore.Qt.MatchFlag.MatchRecursive)
				for item in itemWithSameName:
					#there must be check if item has parent, if pareent is None it means it's category name and categories ALWAYS HAVE SUBCATEGORIES
					#case scenario:
					#	- item freecad obj is named excitation
					#	- there is excitation category
					#	- in itemWithSameName Excitation category is inclucded so next condition filter it away
					#
					if (item.parent() != None and item.parent() == rightItem):
						print(f"Found parent {item.parent().text(0)} item {item.text(0)}")
						isObjAlreadyInCategory = True

				if (isObjAlreadyInCategory):
					self.guiHelpers.displayMessage(f"Object {leftItem.text(0)} already exists in category {rightItem.text(0)}")
					continue

				#
				# ADD ITEM INTO RIGHT LIST, first clone is inserted
				#
				rightItem.addChild(leftItem)
				rightItem.setExpanded(True)

				#
				# ADD ITEM INTO PRIORITY LIST, must be 2nd copy that's reason why there is used leftItem2 to have different clone of left item
				#
				addItemToPriorityList = True

				# check if object is added to probes (probes string is from class name), if yes it's not added into priority list as probes
				# are capturing data from FTDT and don't need to have set priority
				addItemToPriorityList = addItemToPriorityList and not(reResult.group(1).lower() == 'probe')

				#
				#	CREATE NEW OBJECT PRIORITY NAME
				#		- for LumpedPart, Material, ... name is "[category], [category name], [object name]"
				#		- for Grid child other than Smooth Mesh name is "[category], [category name], [object name]"
				#		- for Grid Smooth Mesh name is "[category], [category name]" there is no object name as Smooth Mesh group is taken whole as it is
				#
				if (hasattr(rightItem.data(0, QtCore.Qt.UserRole), 'type') and rightItem.data(0, QtCore.Qt.UserRole).type == "Smooth Mesh"):
					newAddedItemName = rightItem.parent().text(0) + ", " + rightItem.text(0) + ", SMOOTH MESH GROUP"
				else:
					newAddedItemName = rightItem.parent().text(0) + ", " + rightItem.text(0) + ", " + leftItem2.text(0)
				leftItem2.setData(0, QtCore.Qt.UserRole, rightItem.data(0, QtCore.Qt.UserRole))

				#
				#	Check if item is already in priority list, must be in same category as material, port or so to be not added due it will be duplicate
				#	There are 2 priority lists:
				#		1. objects priority for 3D objects - materials, ports
				#		2. mesh priority objects
				#
				isGridObjectToBeAdded = reResult.group(1).lower() == 'grid'

				if (isGridObjectToBeAdded):
					priorityListItems = self.form.meshPriorityTreeView.findItems(newAddedItemName, QtCore.Qt.MatchFixedString)
					addItemToPriorityList = addItemToPriorityList and len(priorityListItems) == 0	#check for DUPLICATES
				else:
					priorityListItems = self.form.objectAssignmentPriorityTreeView.findItems(newAddedItemName, QtCore.Qt.MatchFixedString)
					addItemToPriorityList = addItemToPriorityList and len(priorityListItems) == 0	#check for DUPLICATES

				if addItemToPriorityList:
					#	Item is gonna be added into list:
					#		1. copy icon of object category in right list to know what is added (PORT, MATERIAL, Excitation, ...)
					#		2. add item into priority list with according icon and category
					leftItem2.setText(0, newAddedItemName)

					if (isGridObjectToBeAdded):
						self.form.meshPriorityTreeView.insertTopLevelItem(0, leftItem2)
					else:
						self.form.objectAssignmentPriorityTreeView.insertTopLevelItem(0, leftItem2)

					leftItem2.setIcon(0, rightItem.parent().icon(0)) #set same icon as parent have means same as category
					print("Object " + leftItem2.text(0)+ " added into priority list")
				else:
					#
					#	NO ITEM WOULD BE ADDED BECAUSE ALREADY IS IN LIST
					#
					print("Object " + leftItem2.text(0)+ " in category " + rightItem.parent().text(0) + " already in priority list")

				#
				#	SUCCESS
				#
				print("Item " + leftItem.text(0) + " added into " + rightItem.text(0))

				#when add object to Port category emit signal to update comboboxes with ports
				if (reResult.group(1).lower() == 'port'):
					self.guiSignals.portsChanged.emit("add")
				elif (reResult.group(1).lower() == 'probe'):
					self.guiSignals.probesChanged.emit("add")

			#
			# If grid settings is not set to be top priority lines, therefore it's disabled (because then it's not take into account when generate mesh lines and it's overlapping something)
			#
			if (reResult.group(1).lower() == 'grid'):
				self.guiHelpers.updateMeshPriorityDisableItems()

		else:
				self.guiHelpers.displayMessage("Item must be added into some settings inside category.")


	#
	#	PRIORITY OBJECT LIST move item UP
	#
	def moveupPriorityButtonClicked(self):
		currItemIndex = self.form.objectAssignmentPriorityTreeView.indexOfTopLevelItem(self.form.objectAssignmentPriorityTreeView.currentItem())
		if currItemIndex > 0:
			takenItem = self.form.objectAssignmentPriorityTreeView.takeTopLevelItem(currItemIndex)
			self.form.objectAssignmentPriorityTreeView.insertTopLevelItem(currItemIndex-1, takenItem)
			self.form.objectAssignmentPriorityTreeView.setCurrentItem(takenItem)

	#
	#	PRIORITY OBJECT LIST move item DOWN
	#
	def movedownPriorityButtonClicked(self):
		currItemIndex = self.form.objectAssignmentPriorityTreeView.indexOfTopLevelItem(self.form.objectAssignmentPriorityTreeView.currentItem())
		countAllItems = self.form.objectAssignmentPriorityTreeView.topLevelItemCount()
		if currItemIndex < countAllItems-1:
			takenItem = self.form.objectAssignmentPriorityTreeView.takeTopLevelItem(currItemIndex)
			self.form.objectAssignmentPriorityTreeView.insertTopLevelItem(currItemIndex+1, takenItem)
			self.form.objectAssignmentPriorityTreeView.setCurrentItem(takenItem)

	#
	#	PRIORITY MESH LIST move item UP
	#
	def moveupPriorityMeshButtonClicked(self):
		currItemIndex = self.form.meshPriorityTreeView.indexOfTopLevelItem(self.form.meshPriorityTreeView.currentItem())
		if currItemIndex > 0:
			takenItem = self.form.meshPriorityTreeView.takeTopLevelItem(currItemIndex)
			self.form.meshPriorityTreeView.insertTopLevelItem(currItemIndex-1, takenItem)
			self.form.meshPriorityTreeView.setCurrentItem(takenItem)

	#
	#	PRIORITY MESH LIST move item DOWN
	#
	def movedownPriorityMeshButtonClicked(self):
		currItemIndex = self.form.meshPriorityTreeView.indexOfTopLevelItem(self.form.meshPriorityTreeView.currentItem())
		countAllItems = self.form.meshPriorityTreeView.topLevelItemCount()
		if currItemIndex < countAllItems-1:
			takenItem = self.form.meshPriorityTreeView.takeTopLevelItem(currItemIndex)
			self.form.meshPriorityTreeView.insertTopLevelItem(currItemIndex+1, takenItem)
			self.form.meshPriorityTreeView.setCurrentItem(takenItem)

	def checkTreeWidgetForDuplicityName(self, refTreeWidget, itemName, ignoreSelectedItem=True):
		isDuplicityName = False
		iterator = QtWidgets.QTreeWidgetItemIterator(refTreeWidget, QtWidgets.QTreeWidgetItemIterator.All)
		while iterator.value():
			item = iterator.value()
			if (ignoreSelectedItem == True and item.text(0) == itemName) or (ignoreSelectedItem == False and refTreeWidget.selectedItems()[0] != item and item.text(0) == itemName):
				isDuplicityName = True
				self.guiHelpers.displayMessage("Please change name, item with this name already exists.", True)
			iterator += 1
		return isDuplicityName

	#
	#	Save button clicked
	#
	def saveToFileSettingsButtonClicked(self):
		outputFile = self.simulationSettingsFile.writeToFile()

		if outputFile is None:
			return

		programname = os.path.basename(outputFile)
		programbase, ext = os.path.splitext(programname)  # extract basename and ext from filename
		programbase.replace(" ", "_")					#replace whitespaces to underscores, ie. "some file name 1" -> "some_file_name_1", octave has problem from gui to run files with spaces in name
		self.simulationOutputDir = f"{os.path.dirname(outputFile)}/{programbase}_openEMS_simulation"
		print(f"-----> saveToFileSettingsButtonClicked, setting simulationOutputDir: {self.simulationOutputDir}")

	def loadFromFileSettingsButtonClicked(self):
		outputFile = self.simulationSettingsFile.readFromFile()

		if outputFile is None:
			return

		programname = os.path.basename(outputFile)
		programbase, ext = os.path.splitext(programname)  # extract basename and ext from filename
		self.simulationOutputDir = f"{os.path.dirname(outputFile)}/{programbase}_openEMS_simulation"
		print(f"-----> loadFromFileSettingsButtonClicked, setting simulationOutputDir: {self.simulationOutputDir}")

		#
		#	Add default PEC material during load
		#
		self.materialAddPEC()

		# Inform GUI that there are some ports updated
		self.guiSignals.portsChanged.emit("update")
		self.guiSignals.probesChanged.emit("update")

		# PORT select first item
		topItem = self.form.portSettingsTreeView.itemAt(0,0)
		self.form.portSettingsTreeView.setCurrentItem(topItem)

	#
	#	Change current scripts type generator based on radiobutton from UI
	#		if no type by accident is choosed, octave script generator is used
	#
	def radioButtonOutputScriptsTypeClicked(self):
		if self.form.radioButton_octaveType.isChecked():
			self.scriptGenerator = self.octaveScriptGenerator
			self.guiHelpers.displayMessage("Output type changed to octave", forceModal=False)
		elif self.form.radioButton_pythonType.isChecked():
			self.scriptGenerator = self.pythonScriptGenerator
			self.guiHelpers.displayMessage("Output type changed to python", forceModal=False)
		else:
			self.scriptGenerator = self.octaveScriptGenerator
			self.guiHelpers.displayMessage("Some error - output type changed to default octave", forceModal=False)

	def checkMaterialForFaceObjects(self):
		"""
		Check if materials categories contain faces objects and if yes display warning, due there is problem
		that openEMS not generate right nodes for planar STL objects.

		THIS CHECK IS NOW AVAILABLE JUST IN FreeCAD!
		:return:
		"""
		outMessage = ""
		objListStr = ""

		if APP_CONTEXT == "FreeCAD":
			materialCategories = self.scriptGenerator.getItemsByClassName().get("MaterialSettingsItem", None)
			for [materialItem, currSetting] in materialCategories:

				#
				#	This check is just for materials which are no conducting sheets, conducting sheets containing faces are kind ok, since they can lay
				#	just on XY, XZ, YZ planes
				#
				if currSetting.type != "conducting sheet":
					allCadObjects = self.scriptGenerator.cadHelpers.getObjects()
					for k in range(materialItem.childCount()):
						childName = materialItem.child(k).text(0)
						freeCadObj = [i for i in  allCadObjects if (i.Label) == childName][0]
						if freeCadObj.Name.startswith("Face"):
							objListStr += f"\t{materialItem.text(0)} - {freeCadObj.Label}\n"

			#
			#	If objects were found create warning message
			#
			if len(objListStr) > 0:
				outMessage += "Following objects in materials categories are type of Face which are generated as planar STL objects and mesh for them WILL NOT BE GENERATED, please check mesh using debug PEC and debug material switch/variables:\n"
				outMessage += objListStr

		elif APP_CONTEXT == "Blender":
			#
			#	NOT IMPLEMENTED, wasn't tried how Blender behaves.
			#
			pass

		return outMessage

	#
	#	After click on generate openEMS script file button there is check if settings are saved, if not user is asked if he wants to save settings if not
	#	all simulation connected files will be generated inside local directory next to freecad file.
	#
	def generateOpenEMSScriptButtonClicked(self):
		if (self.simulationOutputDir is None or self.simulationOutputDir == ""):
			saveSettingsFlag = self.guiHelpers.displayYesNoMessage("Simulation settings aren't saved yet, do you want to save them? It's recommended to save settings, otherwise simulation files will be generated in same folder as FreeCAD file.")
			if saveSettingsFlag:
				self.saveToFileSettingsButtonClicked()

		#
		#	WARNING: Check material categories for Face objects which casue error in metal generate for openEMS for FreeCAD
		#
		faceObjectsWarning = self.checkMaterialForFaceObjects()
		if len(faceObjectsWarning) > 0:
			self.guiHelpers.displayMessage(faceObjectsWarning, forceModal=True)

		#write result .m file into subfolder named after .ini file next to simulation settings .ini file
		print(f"----> start saving file into {self.simulationOutputDir}")

		self.scriptGenerator.generateOpenEMSScript(self.simulationOutputDir)
		#self.scriptGenerator2.generateOpenEMSScript(self.simulationOutputDir + "_2nd_generator")
		#self.scriptGenerator3.generateOpenEMSScript(self.simulationOutputDir + "_3rd_generator")

	def drawS11ButtonClicked(self):
		portName = self.form.drawS11Port.currentText()

		if (len(portName) == 0):
			self.guiHelpers.displayMessage("Port not set, script will not be generated.")
			return
		#if (not self.guiHelpers.hasPortSomeObjects(portName)):
		#	self.guiHelpers.displayMessage(f"Port {portName} has no objects assigned, script will not be generated.")
		#	return

		self.scriptGenerator.drawS11ButtonClicked(self.simulationOutputDir, portName)
		self.guiHelpers.displayMessage("S11 script generated.")

	def drawS21ButtonClicked(self):
		sourcePortName = self.form.drawS21Source.currentText()
		targetPortName = self.form.drawS21Target.currentText()

		if (len(sourcePortName) == 0):
			self.guiHelpers.displayMessage("Source port not set, script will not be generated.")
			return
		if (len(targetPortName) == 0):
			self.guiHelpers.displayMessage("Target port not set, script will not be generated.")
			return

		#if (not self.guiHelpers.hasPortSomeObjects(sourcePortName)):
		#	self.guiHelpers.displayMessage(f"Port {sourcePortName} has no objects assigned, script will not be generated.")
		#	return
		#if (not self.guiHelpers.hasPortSomeObjects(targetPortName)):
		#	self.guiHelpers.displayMessage(f"Port {targetPortName} has no objects assigned, script will not be generated.")
		#	return

		self.scriptGenerator.drawS21ButtonClicked(self.simulationOutputDir, sourcePortName, targetPortName)
		self.guiHelpers.displayMessage("S21 script generated.")

	def writeNf2ffButtonClicked(self):
		nf2ffBoxName = self.form.portNf2ffObjectList.currentText()
		nf2ffBoxInputPortName = self.form.portNf2ffInput.currentText()
		freq = self.form.portNf2ffFreq.value()*1e6						#freq for nf2ff is in MHz in GUI
		freqCount = self.form.portNf2ffFreqCount.value()

		if (len(nf2ffBoxName) == 0):
			self.guiHelpers.displayMessage("NF2FF port not set, script will not be generated.")
			return
		if (len(nf2ffBoxInputPortName) == 0):
			self.guiHelpers.displayMessage("NF2FF input port not set, script will not be generated.")
			return

		#if (not self.guiHelpers.hasPortSomeObjects(nf2ffBoxName)):
		#	self.guiHelpers.displayMessage(f"NF2FF port category {nf2ffBoxName} has no objects assigned, script will not be generated.")
		#	return
		#if (not self.guiHelpers.hasPortSomeObjects(nf2ffBoxInputPortName)):
		#	self.guiHelpers.displayMessage(f"NF2FF input port {nf2ffBoxInputPortName} has no objects assigned in Port category, script will not be generated.")
		#	return

		self.scriptGenerator.writeNf2ffButtonClicked(self.simulationOutputDir, nf2ffBoxName, nf2ffBoxInputPortName, freq, freqCount)

		# display message that script was generated
		self.guiHelpers.displayMessage("Script to display far field generated.")

	# GRID SETTINGS
	#   _____ _____  _____ _____     _____ ______ _______ _______ _____ _   _  _____  _____
	#  / ____|  __ \|_   _|  __ \   / ____|  ____|__   __|__   __|_   _| \ | |/ ____|/ ____|
	# | |  __| |__) | | | | |  | | | (___ | |__     | |     | |    | | |  \| | |  __| (___
	# | | |_ |  _  /  | | | |  | |  \___ \|  __|    | |     | |    | | | . ` | | |_ |\___ \
	# | |__| | | \ \ _| |_| |__| |  ____) | |____   | |     | |   _| |_| |\  | |__| |____) |
	#  \_____|_|  \_\_____|_____/  |_____/|______|  |_|     |_|  |_____|_| \_|\_____|_____/
	#
	def fixedCountRadioButtonClicked(self):
		self.form.userDefinedGridLinesTextInput.setEnabled(False)
		self.form.gridTopPriorityLinesCheckbox.setEnabled(True)

	def fixedDistanceRadioButtonClicked(self):
		self.form.userDefinedGridLinesTextInput.setEnabled(False)
		self.form.gridTopPriorityLinesCheckbox.setEnabled(True)

	def smoothMeshRadioButtonClicked(self):
		self.form.userDefinedGridLinesTextInput.setEnabled(False)
		self.form.gridTopPriorityLinesCheckbox.setEnabled(True)

	def userDefinedRadioButtonClicked(self):
		self.form.userDefinedGridLinesTextInput.setEnabled(True)
		self.form.gridTopPriorityLinesCheckbox.setEnabled(True)

	def getCurrentSimulationGridType(self):
		isCoordTypeRectangular = True

		#none grid items defined
		if self.form.gridSettingsTreeView.invisibleRootItem().childCount() == 0:
			return None

		#there are grid items defined, so going through them and find their coordination type, they should be all the same coord type
		currentSimulationGridType = 'rectangular'
		topGridItem = self.form.gridSettingsTreeView.invisibleRootItem()
		definedGridItemsCount = topGridItem.childCount()
		for k in range(0, definedGridItemsCount):
			if topGridItem.child(k).data(0, QtCore.Qt.UserRole).coordsType != currentSimulationGridType:
				currentSimulationGridType = 'cylindrical'

		return currentSimulationGridType

	def getGridItemFromGui(self):
		name = self.form.gridSettingsNameInput.text()

		gridX = 0
		gridY = 0
		gridZ = 0

		gridItem = GridSettingsItem()
		gridItem.name = name

		xenabled = self.form.gridXEnable.isChecked()
		yenabled = self.form.gridYEnable.isChecked()
		zenabled = self.form.gridZEnable.isChecked()
		gridItem.xenabled = xenabled
		gridItem.yenabled = yenabled
		gridItem.zenabled = zenabled

		if (self.form.gridRectangularRadio.isChecked()):
			gridItem.coordsType = "rectangular"
		if (self.form.gridCylindricalRadio.isChecked()):
			gridItem.coordsType = "cylindrical"

		if (self.form.fixedCountRadioButton.isChecked()):
			gridItem.type = "Fixed Count"

			gridItem.fixedCount = {}
			gridItem.fixedCount['x'] = self.form.fixedCountXNumberInput.value()
			gridItem.fixedCount['y'] = self.form.fixedCountYNumberInput.value()
			gridItem.fixedCount['z'] = self.form.fixedCountZNumberInput.value()

			print("---> Saved GridSetting ")
			print(str(gridX) + " " + str(gridY) + " " + str(gridZ))

		if (self.form.fixedDistanceRadioButton.isChecked()):
			gridItem.type = "Fixed Distance"

			gridItem.fixedDistance = {}
			gridItem.fixedDistance['x'] = self.form.fixedDistanceXNumberInput.value()
			gridItem.fixedDistance['y'] = self.form.fixedDistanceYNumberInput.value()
			gridItem.fixedDistance['z'] = self.form.fixedDistanceZNumberInput.value()

		if (self.form.smoothMeshRadioButton.isChecked()):
			gridItem.type = "Smooth Mesh"

			gridItem.smoothMesh = {}
			gridItem.smoothMesh['xMaxRes'] = self.form.smoothMeshXMaxRes.value()
			gridItem.smoothMesh['yMaxRes'] = self.form.smoothMeshYMaxRes.value()
			gridItem.smoothMesh['zMaxRes'] = self.form.smoothMeshZMaxRes.value()

		if (self.form.userDefinedRadioButton.isChecked()):
			gridItem.type = "User Defined"
			gridItem.userDefined['data'] = self.form.userDefinedGridLinesTextInput.toPlainText()

		gridItem.units = self.form.gridUnitsInput.currentText()
		gridItem.unitsAngle = self.form.gridUnitsInput_2.currentText()
		gridItem.generateLinesInside = self.form.gridGenerateLinesInsideCheckbox.isChecked()
		gridItem.topPriorityLines = self.form.gridTopPriorityLinesCheckbox.isChecked()

		gridItem.gridOffset['x'] = self.form.gridOffsetX.value()
		gridItem.gridOffset['y'] = self.form.gridOffsetY.value()
		gridItem.gridOffset['z'] = self.form.gridOffsetZ.value()
		gridItem.gridOffset['units'] = self.form.gridOffsetUnits.currentText()

		return gridItem


	def gridSettingsAddButtonClicked(self):
		settingsInst = self.getGridItemFromGui()

		#check if all items have same type of coordinate system
		currentSimulationGridType = self.getCurrentSimulationGridType()
		if currentSimulationGridType != None and settingsInst.coordsType != currentSimulationGridType:
			self.guiHelpers.displayMessage("All current defined grids are " + currentSimulationGridType + " you have to remove them or change type of current grid item.")
			return

		#check for duplicity in names if there is some warning message displayed
		#if everything is OK, item is added into tree
		isDuplicityName = self.checkTreeWidgetForDuplicityName(self.form.gridSettingsTreeView, settingsInst.name)
		if (not isDuplicityName):

			#disable/enable grid plane drawing if rectangular, for cylindrical just axis z
			if settingsInst.coordsType == "rectangular":
				self.form.auxGridAxis.setEnabled(True)
			else:
				#set grid drawing plane to 'z' and disable choosing plane to draw grid
				index = self.form.auxGridAxis.findText('z', QtCore.Qt.MatchFixedString)
				if index >= 0:
					 self.form.auxGridAxis.setCurrentIndex(index)
				self.form.auxGridAxis.setEnabled(False)

			self.guiHelpers.addSettingsItemGui(settingsInst)	#add item into gui tree views
			self.guiHelpers.updateMeshPriorityDisableItems()	#update grid priority table at object assignment panel
			self.guiSignals.gridCoordsTypeChanged.emit()		#emit signal to update items dependant on coordinate system (rectangular or cartesian)

	def gridSettingsRemoveButtonClicked(self):
		#selectedItem = self.form.gridSettingsTreeView.selectedItems()[0].data(0, QtCore.Qt.UserRole)
		#self.guiHelpers.displayMessage(selectedItem.serializeToString())

		selectedItem = self.form.gridSettingsTreeView.selectedItems()[0]
		print("Selected port name: " + selectedItem.text(0))

		gridGroupItem = self.guiHelpers.getGridGroupObjectAssignmentTreeItem(selectedItem.text(0))
		print("Currently removing grid item: " + gridGroupItem.text(0))

		#	Remove from Priority List
		priorityName = gridGroupItem.parent().text(0) + ", " + gridGroupItem.text(0);
		self.guiHelpers.removePriorityName(priorityName)

		#	Remove from Assigned Object
		self.form.gridSettingsTreeView.invisibleRootItem().removeChild(selectedItem)
		gridGroupItem.parent().removeChild(gridGroupItem)

		self.guiHelpers.updateMeshPriorityDisableItems()	#update grid priority table at object assignment panel

	def gridSettingsUpdateButtonClicked(self):
		### capture UI settings
		settingsInst = self.getGridItemFromGui()

		### replace old with new settingsInst
		selectedItems = self.form.gridSettingsTreeView.selectedItems()
		if len(selectedItems) != 1:
			self.guiHelpers.displayMessage("No item is selected.")
			return

		#check if all items have same type of coordinate system
		currentSimulationGridType = self.getCurrentSimulationGridType()
		if currentSimulationGridType != None and settingsInst.coordsType != currentSimulationGridType:
			self.guiHelpers.displayMessage("All current defined grids are " + currentSimulationGridType + " you have to remove them or change type of current grid item.")
			return

		isDuplicityName = self.checkTreeWidgetForDuplicityName(self.form.gridSettingsTreeView, settingsInst.name, ignoreSelectedItem=False)
		if (not isDuplicityName):
			oldSettingsInst = selectedItems[0].data(0, QtCore.Qt.UserRole)
			selectedItems[0].setData(0, QtCore.Qt.UserRole, settingsInst)

			### update other UI elements to propagate changes
			# replace outdated copy of settingsInst
			self.updateObjectAssignmentRightTreeWidgetItemData("Grid", selectedItems[0].text(0), settingsInst)

			# update grid priority table at object assignment panel
			self.guiHelpers.updateMeshPriorityDisableItems()

			# emit rename signal
			if (selectedItems[0].text(0) != settingsInst.name):
				self.guiSignals.gridRenamed.emit(selectedItems[0].text(0), settingsInst.name)

			# SPECIAL CASE when grid type changed to Smooth Mesh
			if (oldSettingsInst.type != "Smooth Mesh" and settingsInst.type == "Smooth Mesh"):
				self.guiSignals.gridTypeChangedToSmoothMesh.emit(settingsInst.name)

			# SPECIAL CASE when grid type changed to Smooth Mesh
			if (oldSettingsInst.type == "Smooth Mesh" and settingsInst.type != "Smooth Mesh"):
				self.guiSignals.gridTypeChangedFromSmoothMesh.emit(settingsInst.name)

			self.guiHelpers.displayMessage(f"Grid {settingsInst.name} was updated", forceModal=False)
			self.guiSignals.gridCoordsTypeChanged.emit()		#emit signal to update items dependant on coordinate system (rectangular or cartesian)

	def gridCoordsTypeChoosed(self):
		if (self.form.gridRectangularRadio.isChecked()):
			self.form.gridXEnable.setText("X")
			self.form.gridYEnable.setText("Y")
			self.form.gridUnitsInput_2.setEnabled(False)

		if (self.form.gridCylindricalRadio.isChecked()):
			self.form.gridXEnable.setText("r")
			self.form.gridYEnable.setText("theta")
			self.form.gridUnitsInput_2.setEnabled(True)

	@Slot()
	def gridCoordsTypeChanged(self):
		"""
			BASED ON coordination type texts in different port propagation directions are changed
		"""

		def clearComboboxSetValuesRestoreIndex(comboboxRef, values):
			"""
				Inner method to clear combobox items add new ones and restore selected items, equivalent item must be at same index
				This method is specific for this object method that's reason why it's inner method.
			"""
			alternativeEquivalentValues = GridSettingsItem.cartesianCylindricCoordsAlternativeValues
			text = comboboxRef.currentText()
			comboboxRef.clear()
			comboboxRef.addItems(values)

			index = comboboxRef.findText(text, QtCore.Qt.MatchFixedString)
			if index >= 0:
				comboboxRef.setCurrentIndex(index)
				print(f"setComboboxItem for {comboboxRef} to value {text} at index {index}")
			else:
				flagWasAlternativeValueUsed = False
				for alternativeValueTuple in alternativeEquivalentValues:
					if (alternativeValueTuple[0] == text):
						flagWasAlternativeValueUsed = True
						print(f"WARNING: For {comboboxRef} instead {text} trying to use alternative equivalent value {alternativeValueTuple[1]}")
						self.guiHelpers.setComboboxItem(comboboxRef, alternativeValueTuple[1])
					elif (alternativeValueTuple[1] == text):
						flagWasAlternativeValueUsed = True
						print(f"WARNING: For {comboboxRef} instead {text} trying to use alternative equivalent value {alternativeValueTuple[0]}")
						self.guiHelpers.setComboboxItem(comboboxRef, alternativeValueTuple[0])

				if (not flagWasAlternativeValueUsed):
					print(f"WARNING: clearComboboxSetValuesRestoreIndex: Cannot set for {comboboxRef} item {text} alternative equivalent, no value.");

				return

			print(f"WARNING: clearComboboxSetValuesRestoreIndex: Cannot set for {comboboxRef} item {text}, wasn't found in items.")
			return

		if (self.getCurrentSimulationGridType() == "cylindrical"):
			[clearComboboxSetValuesRestoreIndex(comboboxRef, GridSettingsItem.multilayeredPortCylindricalPropagationDirection) for comboboxRef in [
				self.form.portCircWaveguideDirection,
				self.form.portRectWaveguideDirection,
				self.form.microstripPortPropagationComboBox,
				self.form.coaxialPortDirection,
				self.form.coplanarPortPropagationComboBox,
				self.form.striplinePortPropagationComboBox
			]]
			[clearComboboxSetValuesRestoreIndex(comboboxRef, GridSettingsItem.multilayeredPortCylindricalLayerDirection) for comboboxRef in [
				self.form.microstripPortDirection,
				self.form.coplanarPortDirection,
			]]
			[clearComboboxSetValuesRestoreIndex(comboboxRef, GridSettingsItem.multilayeredSymmetricPortCylindricalLayerDirection) for comboboxRef in [
				self.form.striplinePortDirection
			]]
			[clearComboboxSetValuesRestoreIndex(comboboxRef, GridSettingsItem.lumpedPortCylindricalExcitationDirection) for comboboxRef in [
				self.form.lumpedPortDirection
			]]
		else:
			[clearComboboxSetValuesRestoreIndex(comboboxRef, GridSettingsItem.multilayeredPortCartesianPropagationDirection) for comboboxRef in [
				self.form.portCircWaveguideDirection,
				self.form.portRectWaveguideDirection,
				self.form.microstripPortPropagationComboBox,
				self.form.coaxialPortDirection,
				self.form.coplanarPortPropagationComboBox,
				self.form.striplinePortPropagationComboBox
			]]
			[clearComboboxSetValuesRestoreIndex(comboboxRef, GridSettingsItem.multilayeredPortCartesianLayerDirection) for comboboxRef in [
				self.form.microstripPortDirection,
				self.form.coplanarPortDirection,
			]]
			[clearComboboxSetValuesRestoreIndex(comboboxRef, GridSettingsItem.multilayeredSymmetricPortCartesianLayerDirection) for comboboxRef in [
				self.form.striplinePortDirection
			]]
			[clearComboboxSetValuesRestoreIndex(comboboxRef, GridSettingsItem.lumpedPortCartesianExcitationDirection) for comboboxRef in [
				self.form.lumpedPortDirection
			]]

	def gridGenerateLinesInsideCheckboxToggle(self):
		self.form.gridOffsetX.setEnabled(False)
		self.form.gridOffsetY.setEnabled(False)
		self.form.gridOffsetZ.setEnabled(False)

		if self.form.gridGenerateLinesInsideCheckbox.checkState() == QtCore.Qt.Checked:
			if self.form.gridXEnable.checkState() == QtCore.Qt.Checked:
				self.form.gridOffsetX.setEnabled(True)
			if self.form.gridYEnable.checkState() == QtCore.Qt.Checked:
				self.form.gridOffsetY.setEnabled(True)
			if self.form.gridZEnable.checkState() == QtCore.Qt.Checked:
				self.form.gridOffsetZ.setEnabled(True)

	#
	# MATERIAL SETTINGS
	#  __  __       _______ ______ _____  _____          _         _____ ______ _______ _______ _____ _   _  _____  _____
	# |  \/  |   /\|__   __|  ____|  __ \|_   _|   /\   | |       / ____|  ____|__   __|__   __|_   _| \ | |/ ____|/ ____|
	# | \  / |  /  \  | |  | |__  | |__) | | |    /  \  | |      | (___ | |__     | |     | |    | | |  \| | |  __| (___
	# | |\/| | / /\ \ | |  |  __| |  _  /  | |   / /\ \ | |       \___ \|  __|    | |     | |    | | | . ` | | |_ |\___ \
	# | |  | |/ ____ \| |  | |____| | \ \ _| |_ / ____ \| |____   ____) | |____   | |     | |   _| |_| |\  | |__| |____) |
	# |_|  |_/_/    \_\_|  |______|_|  \_\_____/_/    \_\______| |_____/|______|  |_|     |_|  |_____|_| \_|\_____|_____/
	#

	def getMaterialItemFromGui(self):
		name = self.form.materialSettingsNameInput.text()
		epsilon = self.form.materialEpsilonNumberInput.value()
		mue = self.form.materialMueNumberInput.value()
		kappa = self.form.materialKappaNumberInput.value()
		sigma = self.form.materialSigmaNumberInput.value()

		# LuboJ, added at March 2023 so this is here to prevent errors
		try:
			conductingSheetThicknessValue = self.form.materialConductingSheetThickness.value()
			conductingSheetThicknessUnits = self.form.materialConductingSheetUnits.currentText()
			conductingSheetConductivity = self.form.materialConductingSheetConductivity.value()
		except:
			conductingSheetThicknessValue = 40.0
			conductingSheetThicknessUnits = "um"

		materialItem = MaterialSettingsItem()
		materialItem.name = name
		materialItem.constants = {}	# !!! <--- THIS MUST BE HERE, OTHERWISE ALL CONSTANTS IN ALL MATERIAL ITEMS HAVE SAME VALUE LIKE REFERENCING SAME OBJECT

		materialItem.constants['epsilon'] = epsilon
		materialItem.constants['mue'] = mue
		materialItem.constants['kappa'] = kappa
		materialItem.constants['sigma'] = sigma

		materialItem.constants['conductingSheetThicknessValue'] = conductingSheetThicknessValue
		materialItem.constants['conductingSheetThicknessUnits'] = conductingSheetThicknessUnits
		materialItem.constants['conductingSheetConductivity'] = conductingSheetConductivity

		if (self.form.materialMetalRadioButton.isChecked() == 1):
			materialItem.type = "metal"
		elif (self.form.materialUserDefinedRadioButton.isChecked() == 1):
			materialItem.type = "userdefined"
		elif (self.form.materialConductingSheetRadioButton.isChecked() == 1):
			materialItem.type = "conducting sheet"

		return materialItem


	def materialSettingsAddButtonClicked(self):
		materialItem = self.getMaterialItemFromGui()

		# display message box with current material settings to be added
		#self.guiHelpers.displayMessage(materialItem.serializeToString())

		#check for duplicity in names if there is some warning message displayed
		isDuplicityName = self.checkTreeWidgetForDuplicityName(self.form.materialSettingsTreeView, materialItem.name)
		isPEC = (materialItem.name.upper() == "PEC")

		if (isPEC and materialItem.type != "metal"):
			self.guiHelpers.displayMessage("Material with name PEC must be just metal, cannot be something else.")
			return

		if (isDuplicityName):
			return

		self.guiHelpers.addSettingsItemGui(materialItem)
		self.guiSignals.materialsChanged.emit("add")


	def materialSettingsRemoveButtonClicked(self):
		selectedItem = self.form.materialSettingsTreeView.selectedItems()[0]
		materialSettings = selectedItem.data(0, QtCore.Qt.UserRole)
		print("Selected material name: " + selectedItem.text(0))

		#
		#	PEC material with type metal cannot be removed
		#		but if it has different params by random than it can be removed.
		#
		if (materialSettings.name.upper() == "PEC" and materialSettings.type == "metal"):
			self.guiHelpers.displayMessage("Maaterial PEC which is metal cannot be removed.")
			return

		materialGroupWidgetItems = self.form.objectAssignmentRightTreeWidget.findItems(
			selectedItem.text(0),
			QtCore.Qt.MatchExactly | QtCore.Qt.MatchFlag.MatchRecursive
			)

		# material name MUST BE UNIQUE, this will go through all defined material in Object assignment right column
		# and return particular material group item in tree view object
		materialGroupItem = None
		for item in materialGroupWidgetItems:
			if (item.parent().text(0) == "Material"):
				materialGroupItem = item
		print("Currently removing material item: " + materialGroupItem.text(0))

		#
		# 1. There are microstrip, coaxial and other ports with material definition which must be removed first
		#
		portGroupWidgetItems = self.form.objectAssignmentRightTreeWidget.findItems(
			"Port",
			QtCore.Qt.MatchExactly | QtCore.Qt.MatchFlag.MatchRecursive
		)[0]
		portsWithMaterialToDelete = []	#there can be more microstrip ports with same material assignment but different parameters
		for k in range(portGroupWidgetItems.childCount()):
			item = portGroupWidgetItems.child(k)
			if (item.data(0, QtCore.Qt.UserRole).type == "microstrip" and item.data(0, QtCore.Qt.UserRole).mslMaterial == selectedItem.text(0)):
				portsWithMaterialToDelete.append(item)
			if (item.data(0, QtCore.Qt.UserRole).type == "coaxial" and (item.data(0, QtCore.Qt.UserRole).coaxialMaterial == selectedItem.text(0) or item.data(0, QtCore.Qt.UserRole).coaxialConductorMaterial == selectedItem.text(0))):
				portsWithMaterialToDelete.append(item)
			if (item.data(0, QtCore.Qt.UserRole).type == "coplanar" and item.data(0, QtCore.Qt.UserRole).coplanarMaterial == selectedItem.text(0)):
				portsWithMaterialToDelete.append(item)

		message = f"This port is removed because material '{materialGroupItem.text(0)}' is removed:\n"
		for portToRemove in portsWithMaterialToDelete:
			message += f"{portToRemove.text(0)}\n"
			print("\t" + message)
		message += "\n"
		message += "Do you want to continue?"

		#
		#	2. If there are ports using materials which is going to be removed asked for confirmation to remove material and ports will be also removed
		#
		if (len(portsWithMaterialToDelete) > 0 and not self.guiHelpers.displayYesNoMessage(message)):
			return
		for portToRemove in portsWithMaterialToDelete:
			self.portSettingsRemoveButtonClicked(portToRemove.text(0))

		#
		# 3. Remove from Priority list (Object and Grid priority list)
		#
		priorityName = materialGroupItem.parent().text(0) + ", " + materialGroupItem.text(0);
		self.guiHelpers.removePriorityName(priorityName)

		#
		# 4. Remove from Materials list
		#
		self.form.materialSettingsTreeView.invisibleRootItem().removeChild(selectedItem)
		materialGroupItem.parent().removeChild(materialGroupItem)

		self.guiSignals.materialsChanged.emit("remove")

	def materialSettingsUpdateButtonClicked(self):
		### capture UI settings
		settingsInst = self.getMaterialItemFromGui()

		### replace old with new settingsInst
		###	JUST ONE ITEM MUST BE SELECTED!
		selectedItems = self.form.materialSettingsTreeView.selectedItems()
		if len(selectedItems) != 1:
			return

		if (selectedItems[0].text(0).upper() == "PEC"):
			self.guiHelpers.displayMessage("Material PEC can be defined just as metal nothing else. It's name also cannot be changed. This update will not perform.")
			return

		isDuplicityName = self.checkTreeWidgetForDuplicityName(self.form.materialSettingsTreeView, settingsInst.name, ignoreSelectedItem=False)
		if (not isDuplicityName):
			selectedItems[0].setData(0, QtCore.Qt.UserRole, settingsInst)

			### update other UI elements to propagate changes
			# replace oudated copy of settingsInst
			self.updateObjectAssignmentRightTreeWidgetItemData("Material", selectedItems[0].text(0), settingsInst)

			# emit rename signal
			if (selectedItems[0].text(0) != settingsInst.name):
				self.guiSignals.materialRenamed.emit(selectedItems[0].text(0), settingsInst.name)

			# emit signal to change all comboboxes which contains material
			self.guiSignals.materialsChanged.emit("update")

			self.guiHelpers.displayMessage(f"Material {settingsInst.name} was updated", forceModal=False)

	@Slot(str)
	def materialsChanged(self, operation):
		"""
		Triggers when there is change at material tab and updates related settings in gui accordingly:
			- add new material
			- remove material
			- update material
		:param operation: "add" | "remove" | "update"
		:return: None
		"""
		print(f"@Slot materialsChanged: {operation}")

		if (operation in ["add", "remove", "update"]):
			self.updateMaterialComboBoxJustMetals(self.form.microstripPortMaterialComboBox)				# update microstrip port material combobox
			self.updateMaterialComboBoxJustMetals(self.form.coplanarPortMaterialComboBox)				# update coplanar port material combobox
			self.updateMaterialComboBoxJustUserdefined(self.form.coaxialPortMaterialComboBox)			# update coaxial port material combobox
			self.updateMaterialComboBoxAllMaterials(self.form.coaxialPortConductorMaterialComboBox)		# update coaxial port material combobox

	def materialAddPEC(self):
		"""
		Add PEC material as metal, this is done by default due PEC must be reserved word for perfect electric conductor (metal) to not confused most simulations
		in microwave design it's fully established name, if it will be defined as something else it will be confusing.
		:return: None
		"""
		# iterates over materials due if there is PEC defined as metal
		materialCategoryItem = self.form.objectAssignmentRightTreeWidget.findItems(
			"Material",
			QtCore.Qt.MatchExactly | QtCore.Qt.MatchFlag.MatchRecursive
			)[0]

		# here metal and conducting sheet are added into microstrip possible material combobox
		for k in range(materialCategoryItem.childCount()):
			materialData = materialCategoryItem.child(k).data(0, QtCore.Qt.UserRole)
			if (materialData.name == "PEC" and materialData.type == "metal"):
				return
			elif (materialData.name == "PEC" and materialData.type != "metal"):
				self.guiHelpers.displayMessage("There is material defined as PEC but it's not metal, check if it's as it should be, this is not normal settings as PEC is expected to be metal.")
				return

		self.form.materialSettingsNameInput.setText("PEC")
		self.form.materialMetalRadioButton.toggle()
		self.form.materialSettingsAddButton.clicked.emit()

	@Slot(str, str)
	def gridRenamed(self, oldName, newName):
		try:
			self.renameObjectAssignmentRightTreeWidgetItem("Grid", oldName, newName)
			self.renameMeshPriorityTreeViewItem(oldName, newName)
			self.renameTreeViewItem(self.form.gridSettingsTreeView, oldName, newName)
			self.guiHelpers.displayMessage("Grid " + oldName + " renamed to " + newName, forceModal=False)
		except Exception as e:
			self.guiHelpers.displayMessage("ERROR: " + str(e), forceModal=False)
			self.cadHelpers.printError(traceback.format_exc())

	@Slot(str)
	def gridTypeChangedToSmoothMesh(self, groupName):
		searchStr = "Grid, " + groupName
		newName = "Grid, " + groupName + ", SMOOTH MESH GROUP"
		[item.setText(0, newName) for item in self.form.meshPriorityTreeView.findItems(searchStr, QtCore.Qt.MatchStartsWith)]
		[self.form.meshPriorityTreeView.invisibleRootItem().removeChild(item) for item in self.form.meshPriorityTreeView.findItems(newName, QtCore.Qt.MatchStartsWith)[1:]]
		self.cadHelpers.printWarning(f"Updated {groupName} in mesh priority list")

	@Slot(str)
	def gridTypeChangedFromSmoothMesh(self, groupName):
		gridItem = self.guiHelpers.getGridGroupObjectAssignmentTreeItem(groupName)
		assignedObjectNames = [gridItem.child(k).text(0) for k in range(gridItem.childCount())]

		meshPrioritySmoothMeshItem = self.form.meshPriorityTreeView.findItems("Grid, " + groupName + ", SMOOTH MESH GROUP", QtCore.Qt.MatchExactly)[0]
		meshPrioritySmoothMeshItemIndex = self.form.meshPriorityTreeView.invisibleRootItem().indexOfChild(meshPrioritySmoothMeshItem)
		self.form.meshPriorityTreeView.invisibleRootItem().removeChild(meshPrioritySmoothMeshItem)

		newMeshPriorityItems = [QtWidgets.QTreeWidgetItem([f"Grid, {groupName}, {objName}"]) for objName in assignedObjectNames]
		[item.setIcon(0, gridItem.icon(0)) for item in newMeshPriorityItems]
		self.form.meshPriorityTreeView.invisibleRootItem().insertChildren(meshPrioritySmoothMeshItemIndex, newMeshPriorityItems)

		self.cadHelpers.printWarning(f"Updated {groupName} in mesh priority list, adding objects: {assignedObjectNames}")

	@Slot(str, str)
	def materialRenamed(self, oldName, newName):
		try:
			self.renameObjectAssignmentRightTreeWidgetItem("Material", oldName, newName)
			self.renameObjectAssignmentPriorityTreeViewItem("Material", oldName, newName)
			self.renameTreeViewItem(self.form.materialSettingsTreeView, oldName, newName)

			#
			# There are ports with material definition which must be also renamed
			#
			portGroupWidgetItems = self.form.objectAssignmentRightTreeWidget.findItems(
				"Port",
				QtCore.Qt.MatchExactly | QtCore.Qt.MatchFlag.MatchRecursive
			)[0]
			for k in range(portGroupWidgetItems.childCount()):
				item = portGroupWidgetItems.child(k)
				if (item.data(0, QtCore.Qt.UserRole).type == "microstrip" and item.data(0, QtCore.Qt.UserRole).mslMaterial == oldName):
					item.data(0, QtCore.Qt.UserRole).mslMaterial = newName
				if (item.data(0, QtCore.Qt.UserRole).type == "coaxial" and item.data(0, QtCore.Qt.UserRole).coaxialMaterial == oldName):
					item.data(0, QtCore.Qt.UserRole).coaxialMaterial = newName
				if (item.data(0, QtCore.Qt.UserRole).type == "coaxial" and item.data(0, QtCore.Qt.UserRole).coaxialConductorMaterial == oldName):
					item.data(0, QtCore.Qt.UserRole).coaxialConductorMaterial = newName
				if (item.data(0, QtCore.Qt.UserRole).type == "coplanar" and item.data(0, QtCore.Qt.UserRole).coplanarMaterial == oldName):
					item.data(0, QtCore.Qt.UserRole).coplanarMaterial = newName

			self.guiHelpers.displayMessage("Material " + oldName + " renamed to " + newName, forceModal=False)
		except Exception as e:
			self.guiHelpers.displayMessage("ERROR: " + str(e), forceModal=False)
			self.cadHelpers.printError(traceback.format_exc())

	@Slot(str, str)
	def excitationRenamed(self, oldName, newName):
		try:
			self.renameObjectAssignmentRightTreeWidgetItem("Excitation", oldName, newName)
			self.renameTreeViewItem(self.form.excitationSettingsTreeView, oldName, newName)
			self.guiHelpers.displayMessage("Excitation " + oldName + " renamed to " + newName, forceModal=False)
		except Exception as e:
			self.guiHelpers.displayMessage("ERROR: " + str(e), forceModal=False)
			self.cadHelpers.printError(traceback.format_exc())

	@Slot(str, str)
	def portRenamed(self, oldName, newName):
		try:
			self.renameObjectAssignmentRightTreeWidgetItem("Port", oldName, newName)
			self.renameObjectAssignmentPriorityTreeViewItem("Port", oldName, newName)
			self.renameTreeViewItem(self.form.portSettingsTreeView, oldName, newName)
			self.guiHelpers.displayMessage("Port " + oldName + " renamed to " + newName, forceModal=False)
		except Exception as e:
			self.guiHelpers.displayMessage("ERROR: " + str(e), forceModal=False)
			self.cadHelpers.printError(traceback.format_exc())

	@Slot(str, str)
	def lumpedPartRenamed(self, oldName, newName):
		try:
			self.renameObjectAssignmentRightTreeWidgetItem("LumpedPart", oldName, newName)
			self.renameObjectAssignmentPriorityTreeViewItem("LumpedPart", oldName, newName)
			self.renameTreeViewItem(self.form.lumpedPartTreeView, oldName, newName)
			self.guiHelpers.displayMessage("LumpedPart " + oldName + " renamed to " + newName, forceModal=False)
		except Exception as e:
			self.guiHelpers.displayMessage("ERROR: " + str(e), forceModal=False)
			self.cadHelpers.printError(traceback.format_exc())

	@Slot(str, str)
	def probeRenamed(self, oldName, newName):
		try:
			self.renameObjectAssignmentRightTreeWidgetItem("Probe", oldName, newName)
			self.renameTreeViewItem(self.form.probeSettingsTreeView, oldName, newName)
			self.guiHelpers.displayMessage("Probe " + oldName + " renamed to " + newName, forceModal=False)
		except Exception as e:
			self.guiHelpers.displayMessage("ERROR: " + str(e), forceModal=False)
			self.cadHelpers.printError(traceback.format_exc())

	# EXCITATION SETTINGS
	#  ________   _______ _____ _______    _______ _____ ____  _   _    _____ ______ _______ _______ _____ _   _  _____  _____
	# |  ____\ \ / / ____|_   _|__   __|/\|__   __|_   _/ __ \| \ | |  / ____|  ____|__   __|__   __|_   _| \ | |/ ____|/ ____|
	# | |__   \ V / |      | |    | |  /  \  | |    | || |  | |  \| | | (___ | |__     | |     | |    | | |  \| | |  __| (___
	# |  __|   > <| |      | |    | | / /\ \ | |    | || |  | | . ` |  \___ \|  __|    | |     | |    | | | . ` | | |_ |\___ \
	# | |____ / . \ |____ _| |_   | |/ ____ \| |   _| || |__| | |\  |  ____) | |____   | |     | |   _| |_| |\  | |__| |____) |
	# |______/_/ \_\_____|_____|  |_/_/    \_\_|  |_____\____/|_| \_| |_____/|______|  |_|     |_|  |_____|_| \_|\_____|_____/
	#
	def getExcitationItemFromGui(self):
		excitationItem = ExcitationSettingsItem(
			name = self.form.excitationSettingsNameInput.text(),
			units = self.form.excitationUnitsNumberInput.currentText()
		)

		if (self.form.sinusodialExcitationRadioButton.isChecked()):
			excitationItem.type = 'sinusodial'
			excitationItem.sinusodial = {}
			excitationItem.sinusodial['f0'] = self.form.sinusodialExcitationF0NumberInput.value()
		if (self.form.gaussianExcitationRadioButton.isChecked()):
			excitationItem.type = 'gaussian'
			excitationItem.gaussian = {}
			excitationItem.gaussian['fc'] = self.form.gaussianExcitationFcNumberInput.value()
			excitationItem.gaussian['f0'] = self.form.gaussianExcitationF0NumberInput.value()
		if (self.form.diracExcitationRadioButton.isChecked()):
			excitationItem.type = 'dirac'
			excitationItem.dirac = {}
			excitationItem.dirac['fm'] = self.form.diracExcitationFmNumberInput.value()
		if (self.form.stepExcitationRadioButton.isChecked()):
			excitationItem.type = 'step'
			excitationItem.step = {}
			excitationItem.step['fm'] = self.form.stepExcitationFmNumberInput.value()
		if (self.form.customExcitationRadioButton.isChecked()):
			excitationItem.type = 'custom'
			excitationItem.custom = {}
			excitationItem.custom['functionStr'] = self.form.customExcitationTextInput.text()
			excitationItem.custom['f0'] = self.form.customExcitationF0NumberInput.value()
		return excitationItem


	def excitationSettingsAddButtonClicked(self):
		settingsInst = self.getExcitationItemFromGui()

		#check for duplicity in names if there is some warning message displayed
		isDuplicityName = self.checkTreeWidgetForDuplicityName(self.form.excitationSettingsTreeView, settingsInst.name)
		isMoreThanOne = self.form.excitationSettingsTreeView.topLevelItemCount() > 0

		if (isDuplicityName):
			return
		if (isMoreThanOne):
			self.guiHelpers.displayMessage("There could be just one excitation!")
			return

		self.guiHelpers.addSettingsItemGui(settingsInst)


	def excitationSettingsRemoveButtonClicked(self):
		selectedItem = self.form.excitationSettingsTreeView.selectedItems()[0]
		print("Selected port name: " + selectedItem.text(0))

		excitationGroupWidgetItems = self.form.objectAssignmentRightTreeWidget.findItems(
			selectedItem.text(0),
			QtCore.Qt.MatchExactly | QtCore.Qt.MatchFlag.MatchRecursive
			)
		excitationGroupItem = None
		for item in excitationGroupWidgetItems:
			if (item.parent().text(0) == "Excitation"):
				excitationGroupItem = item
		print("Currently removing port item: " + excitationGroupItem.text(0))

		self.form.excitationSettingsTreeView.invisibleRootItem().removeChild(selectedItem)
		excitationGroupItem.parent().removeChild(excitationGroupItem)

	def excitationSettingsUpdateButtonClicked(self):
		### capture UI settings
		settingsInst = self.getExcitationItemFromGui()

		### replace old with new settingsInst
		selectedItems = self.form.excitationSettingsTreeView.selectedItems()
		if len(selectedItems) != 1:
			self.guiHelpers.displayMessage("Excitation ERROR during update.", forceModal=False)
			return
		selectedItems[0].setData(0, QtCore.Qt.UserRole, settingsInst)

		### update other UI elements to propagate changes
		# replace oudated copy of settingsInst
		self.updateObjectAssignmentRightTreeWidgetItemData("Excitation", selectedItems[0].text(0), settingsInst)

		# emit rename signal
		if (selectedItems[0].text(0) != settingsInst.name):
			self.guiSignals.excitationRenamed.emit(selectedItems[0].text(0), settingsInst.name)

		self.guiHelpers.displayMessage("Excitation updated.", forceModal=False)

	# PORT SETTINGS
	#  _____   ____  _____ _______    _____ ______ _______ _______ _____ _   _  _____  _____
	# |  __ \ / __ \|  __ \__   __|  / ____|  ____|__   __|__   __|_   _| \ | |/ ____|/ ____|
	# | |__) | |  | | |__) | | |    | (___ | |__     | |     | |    | | |  \| | |  __| (___
	# |  ___/| |  | |  _  /  | |     \___ \|  __|    | |     | |    | | | . ` | | |_ |\___ \
	# | |    | |__| | | \ \  | |     ____) | |____   | |     | |   _| |_| |\  | |__| |____) |
	# |_|     \____/|_|  \_\ |_|    |_____/|______|  |_|     |_|  |_____|_| \_|\_____|_____/
	#

	def getPortItemFromGui(self):
		name = self.form.portSettingsNameInput.text()

		portItem = PortSettingsItem()
		portItem.name = name

		if (self.form.lumpedPortRadioButton.isChecked()):
			portItem.type = "lumped"
			portItem.R = self.form.lumpedPortResistanceValue.value()
			portItem.RUnits = self.form.lumpedPortResistanceUnits.currentText()
			portItem.infiniteResistance = self.form.lumpedPortInfinitResistance.isChecked()
			portItem.isActive = self.form.lumpedPortActive.isChecked()
			portItem.direction = self.form.lumpedPortDirection.currentText()
			portItem.excitationAmplitude = self.form.lumpedPortExcitationAmplitude.value()

		if (self.form.microstripPortRadioButton.isChecked()):
			portItem.type = "microstrip"
			portItem.R = self.form.microstripPortResistanceValue.value()
			portItem.RUnits = self.form.microstripPortResistanceUnits.currentText()
			portItem.infiniteResistance = self.form.microstripPortInfinitResistance.isChecked()
			portItem.isActive = self.form.microstripPortActive.isChecked()
			portItem.direction = self.form.microstripPortDirection.currentText()
			portItem.excitationAmplitude = self.form.microstripPortExcitationAmplitude.value()

			portItem.mslMaterial = self.form.microstripPortMaterialComboBox.currentText()
			portItem.mslFeedShiftValue = self.form.microstripPortFeedpointShiftValue.value()
			portItem.mslFeedShiftUnits = self.form.microstripPortFeedpointShiftUnits.currentText()
			portItem.mslMeasPlaneShiftValue = self.form.microstripPortMeasureShiftValue.value()
			portItem.mslMeasPlaneShiftUnits = self.form.microstripPortMeasureShiftUnits.currentText()
			portItem.mslPropagation = self.form.microstripPortPropagationComboBox.currentText()

		if (self.form.circularWaveguidePortRadioButton.isChecked()):
			portItem.type = "circular waveguide"
			portItem.isActive = self.form.portCircWaveguideActive.isChecked()
			portItem.direction = self.form.portCircWaveguideDirection.currentText()
			portItem.modeName = self.form.portCircWaveguideModeName.currentText()
			portItem.polarizationAngle = self.form.portCircWaveguidePolarizationAngle.currentText()
			portItem.excitationAmplitude = self.form.portCircWaveguideExcitationAmplitude.value()
			portItem.waveguideCircDir = self.form.portCircWaveguideDirection.currentText()

		if (self.form.rectangularWaveguidePortRadioButton.isChecked()):
			portItem.type = "rectangular waveguide"
			portItem.isActive = self.form.portRectWaveguideActive.isChecked()
			portItem.direction = self.form.portRectWaveguideDirection.currentText()
			portItem.modeName = self.form.portRectWaveguideModeName.currentText()
			portItem.waveguideRectDir = self.form.portRectWaveguideDirection.currentText()
			portItem.excitationAmplitude = self.form.portRectWaveguideExcitationAmplitude.value()

		if (self.form.coaxialPortRadioButton.isChecked()):
			portItem.type = "coaxial"

			portItem.R = self.form.coaxialPortResistanceValue.value()
			portItem.RUnits = self.form.coaxialPortResistanceUnits.currentText()
			portItem.infiniteResistance = self.form.coaxialPortInfinitResistance.isChecked()
			portItem.isActive = self.form.coaxialPortActive.isChecked()
			portItem.direction = self.form.coaxialPortDirection.currentText()
			portItem.excitationAmplitude = self.form.coaxialPortExcitationAmplitude.value()

			portItem.coaxialMaterial = self.form.coaxialPortMaterialComboBox.currentText()
			portItem.coaxialConductorMaterial = self.form.coaxialPortConductorMaterialComboBox.currentText()
			portItem.coaxialInnerRadiusValue = self.form.coaxialPortInnerRadiusValue.value()
			portItem.coaxialInnerRadiusUnits = self.form.coaxialPortInnerRadiusUnits.currentText()
			portItem.coaxialShellThicknessValue = self.form.coaxialPortShellThicknessValue.value()
			portItem.coaxialShellThicknessUnits = self.form.coaxialPortShellThicknessUnits.currentText()
			portItem.coaxialFeedpointShiftValue = self.form.coaxialPortFeedpointShiftValue.value()
			portItem.coaxialFeedpointShiftUnits = self.form.coaxialPortFeedpointShiftUnits.currentText()
			portItem.coaxialMeasPlaneShiftValue = self.form.coaxialPortMeasureShiftValue.value()
			portItem.coaxialMeasPlaneShiftUnits = self.form.coaxialPortMeasureShiftUnits.currentText()

		if (self.form.coplanarPortRadioButton.isChecked()):
			portItem.type = "coplanar"

			portItem.R = self.form.coplanarPortResistanceValue.value()
			portItem.RUnits = self.form.coplanarPortResistanceUnits.currentText()
			portItem.infiniteResistance = self.form.coplanarPortInfinitResistance.isChecked()
			portItem.isActive = self.form.coplanarPortActive.isChecked()
			portItem.direction = self.form.coplanarPortDirection.currentText()
			portItem.excitationAmplitude = self.form.coplanarPortExcitationAmplitude.value()

			portItem.coplanarMaterial = self.form.coplanarPortMaterialComboBox.currentText()
			portItem.coplanarPropagation = self.form.coplanarPortPropagationComboBox.currentText()
			portItem.coplanarGapValue = self.form.coplanarPortGapValue.value()
			portItem.coplanarGapUnits = self.form.coplanarPortGapUnits.currentText()
			portItem.coplanarFeedpointShiftValue = self.form.coplanarPortFeedpointShiftValue.value()
			portItem.coplanarFeedpointShiftUnits = self.form.coplanarPortFeedpointShiftUnits.currentText()
			portItem.coplanarMeasPlaneShiftValue = self.form.coplanarPortMeasureShiftValue.value()
			portItem.coplanarMeasPlaneShiftUnits = self.form.coplanarPortMeasureShiftUnits.currentText()

		if (self.form.striplinePortRadioButton.isChecked()):
			portItem.type = "stripline"

			portItem.R = self.form.striplinePortResistanceValue.value()
			portItem.RUnits = self.form.striplinePortResistanceUnits.currentText()
			portItem.infiniteResistance = self.form.striplinePortInfinitResistance.isChecked()
			portItem.isActive = self.form.striplinePortActive.isChecked()
			portItem.direction = self.form.striplinePortDirection.currentText()
			portItem.excitationAmplitude = self.form.striplinePortExcitationAmplitude.value()

			portItem.striplinePropagation = self.form.striplinePortPropagationComboBox.currentText()
			portItem.striplineFeedpointShiftValue = self.form.striplinePortFeedpointShiftValue.value()
			portItem.striplineFeedpointShiftUnits = self.form.striplinePortFeedpointShiftUnits.currentText()
			portItem.striplineMeasPlaneShiftValue = self.form.striplinePortMeasureShiftValue.value()
			portItem.striplineMeasPlaneShiftUnits = self.form.striplinePortMeasureShiftUnits.currentText()

		if (self.form.curvePortRadioButton.isChecked()):
			portItem.type = "curve"
			portItem.R = self.form.curvePortResistanceValue.value()
			portItem.RUnits = self.form.curvePortResistanceUnits.currentText()
			portItem.infiniteResistance = self.form.curvePortInfinitResistance.isChecked()
			portItem.isActive = self.form.curvePortActive.isChecked()
			portItem.excitationAmplitude = self.form.curvePortExcitationAmplitude.value()

		return portItem

	def probeCheckCurrentSettings(self, currentSettings):
		checkResult = True

		if (currentSettings.type == "dumpbox" and currentSettings.dumpboxDomain == "frequency" and len(currentSettings.dumpboxFrequencyList) == 0):
			checkResult = False
			self.guiHelpers.displayMessage("Port settings ERROR, current settings set dumpox in frequency domain, but list of frequencies is empty.")

		if (currentSettings.type == "probe" and currentSettings.probeDomain == "frequency" and len(currentSettings.probeFrequencyList) == 0):
			checkResult = False
			self.guiHelpers.displayMessage("Port settings ERROR, current settings set probe in frequency domain, but list of frequencies is empty.")

		return checkResult

	def portCheckCurrentSettings(self, currentSettings):
		checkResult = True

		if (currentSettings.excitationAmplitude == 0 and currentSettings.type in ["microstrip", "coplanar", "stripline"]):
			checkResult = False
			self.guiHelpers.displayMessage("Port excitation amplitude cannot be 0.")

		return checkResult

	def portSettingsAddButtonClicked(self):
		settingsInst = self.getPortItemFromGui()

		#check for duplicity in names if there is some warning message displayed
		isDuplicityName = self.checkTreeWidgetForDuplicityName(self.form.portSettingsTreeView, settingsInst.name)

		if (not isDuplicityName and self.portCheckCurrentSettings(settingsInst)):
			self.guiHelpers.addSettingsItemGui(settingsInst)
			self.guiSignals.portsChanged.emit("add")

	def portSettingsRemoveButtonClicked(self, name = None):
		#if there is no name it's called from UI, if there is name it's called as function this is done to have one function removing port properly for both cases
		if (type(name) != "str"):
			selectedItem = self.form.portSettingsTreeView.selectedItems()[0]
			print("Selected port name: " + selectedItem.text(0))
		else:
			selectedItem = self.form.portSettingsTreeView.findItems(name, QtCore.Qt.MatchExactly)[0]
			print("Called by name to remove port: " + selectedItem.text(0))

		portGroupWidgetItems = self.form.objectAssignmentRightTreeWidget.findItems(
			selectedItem.text(0),
			QtCore.Qt.MatchExactly | QtCore.Qt.MatchFlag.MatchRecursive
			)
		portGroupItem = None
		for item in portGroupWidgetItems:
			if (item.parent().text(0) == "Port"):
				portGroupItem = item
		print("Currently removing port item: " + portGroupItem.text(0))

		# Removing from Priority List
		priorityName = portGroupItem.parent().text(0) + ", " + portGroupItem.text(0);
		self.guiHelpers.removePriorityName(priorityName)

		# Removing from Object Assugnment Tree
		self.form.portSettingsTreeView.invisibleRootItem().removeChild(selectedItem)
		portGroupItem.parent().removeChild(portGroupItem)

		# Emit signal about remove port to update comboboxes
		self.guiSignals.portsChanged.emit("remove")

	def portSettingsUpdateButtonClicked(self):
		### capture UI settings
		settingsInst = self.getPortItemFromGui()

		### replace old with new settingsInst
		selectedItems = self.form.portSettingsTreeView.selectedItems()
		if len(selectedItems) != 1:
			return

		isDuplicityName = self.checkTreeWidgetForDuplicityName(self.form.portSettingsTreeView, settingsInst.name, ignoreSelectedItem=False)
		if (not isDuplicityName and self.portCheckCurrentSettings(settingsInst)):
			selectedItems[0].setData(0, QtCore.Qt.UserRole, settingsInst)

			### update other UI elements to propagate changes
			# replace oudated copy of settingsInst
			self.updateObjectAssignmentRightTreeWidgetItemData("Port", selectedItems[0].text(0), settingsInst)

			# emit rename signal
			if (selectedItems[0].text(0) != settingsInst.name):
				self.guiSignals.portRenamed.emit(selectedItems[0].text(0), settingsInst.name)

			# Emit signal about remove port to update comboboxes
			self.guiSignals.portsChanged.emit("update")

			# Display message to user
			self.guiHelpers.displayMessage(f"Port {settingsInst.name} was updated", forceModal=False)

	def portSettingsTypeChoosed(self):
		#first disable all additional settings for ports
		self.form.lumpedPortSettingsGroup.setEnabled(False)
		self.form.microstripPortSettingsGroup.setEnabled(False)
		self.form.waveguideCircSettingsGroup.setEnabled(False)
		self.form.waveguideRectSettingsGroup.setEnabled(False)
		self.form.coaxialPortSettingsGroup.setEnabled(False)
		self.form.coplanarPortSettingsGroup.setEnabled(False)
		self.form.striplinePortSettingsGroup.setEnabled(False)
		self.form.curvePortSettingsGroup.setEnabled(False)

		#for modes update here is some source on internet: https://arxiv.org/ftp/arxiv/papers/1201/1201.3202.pdf

		#enable current choosed radiobox settings for port
		if (self.form.lumpedPortRadioButton.isChecked()):
			self.form.lumpedPortSettingsGroup.setEnabled(True)
			self.guiHelpers.portSpecificSettingsTabSetActiveByName("Lumped")

		elif (self.form.circularWaveguidePortRadioButton.isChecked()):
			self.form.waveguideCircSettingsGroup.setEnabled(True)
			self.guiHelpers.portSpecificSettingsTabSetActiveByName("CircWaveguide")

		elif (self.form.rectangularWaveguidePortRadioButton.isChecked()):
			self.form.waveguideRectSettingsGroup.setEnabled(True)
			self.guiHelpers.portSpecificSettingsTabSetActiveByName("RectWaveguide")

		elif (self.form.microstripPortRadioButton.isChecked()):
			self.form.microstripPortSettingsGroup.setEnabled(True)
			self.guiHelpers.portSpecificSettingsTabSetActiveByName("Microstrip")

		elif (self.form.coaxialPortRadioButton.isChecked()):
			self.form.coaxialPortSettingsGroup.setEnabled(True)
			self.guiHelpers.portSpecificSettingsTabSetActiveByName("Coaxial")

		elif (self.form.coplanarPortRadioButton.isChecked()):
			self.form.coplanarPortSettingsGroup.setEnabled(True)
			self.guiHelpers.portSpecificSettingsTabSetActiveByName("Coplanar")

		elif (self.form.striplinePortRadioButton.isChecked()):
			self.form.striplinePortSettingsGroup.setEnabled(True)
			self.guiHelpers.portSpecificSettingsTabSetActiveByName("Stripline")

		elif (self.form.curvePortRadioButton.isChecked()):
			self.form.curvePortSettingsGroup.setEnabled(True)
			self.guiHelpers.portSpecificSettingsTabSetActiveByName("Curve")

		else:
			self.guiHelpers.portSpecificSettingsTabSetActiveByName("")


	def probeProbeFrequencyAddButtonClicked(self):
		newItem = str(self.form.probeProbeFrequencyInput.value()) + str(self.form.probeProbeFrequencyUnits.currentText())
		self.form.probeProbeFrequencyList.insertItem(self.form.probeProbeFrequencyList.currentRow()+1, newItem)

	def probeProbeFrequencyRemoveButtonClicked(self):
		for item in self.form.probeProbeFrequencyList.selectedItems():
			self.form.probeProbeFrequencyList.takeItem(self.form.probeProbeFrequencyList.row(item))

	def dumpboxProbeFrequencyAddButtonClicked(self):
		newItem = str(self.form.dumpboxProbeFrequencyInput.value()) + str(self.form.dumpboxProbeFrequencyUnits.currentText())
		self.form.dumpboxProbeFrequencyList.insertItem(self.form.dumpboxProbeFrequencyList.currentRow()+1, newItem)

	def dumpboxProbeFrequencyRemoveButtonClicked(self):
		for item in self.form.dumpboxProbeFrequencyList.selectedItems():
			self.form.dumpboxProbeFrequencyList.takeItem(self.form.dumpboxProbeFrequencyList.row(item))

	def dumpboxProbeDomainChanged(self):
		"""
		Updates file type setting for dump box, if port domain is frequency than just hdf5 file is only one option.
		Tested in openEMS trying to save data in frequency domain into vtk file, but no file was produced,
		hence this event handler must be defined.
		:return: None
		"""
		self.form.dumpboxProbeFileType.clear();
		if self.form.dumpboxProbeDomain.currentText() == "frequency":
			self.form.dumpboxProbeFileType.addItems(["hdf5"]);
			[element.setEnabled(True) for element in [self.form.dumpboxProbeFrequencyInput, self.form.dumpboxProbeFrequencyUnits, self.form.dumpboxProbeFrequencyList, self.form.dumpboxProbeFrequencyAddButton, self.form.dumpboxProbeFrequencyRemoveButton]]
		else:
			self.form.dumpboxProbeFileType.addItems(["vtk", "hdf5"]);
			[element.setEnabled(False) for element in [self.form.dumpboxProbeFrequencyInput, self.form.dumpboxProbeFrequencyUnits, self.form.dumpboxProbeFrequencyList, self.form.dumpboxProbeFrequencyAddButton, self.form.dumpboxProbeFrequencyRemoveButton]]

	@Slot(str)
	def portsChanged(self, operation):
		"""
		Triggers when there is change in ports tab and updates related settings (now mostly comboboxes for Sxx script generation) in gui accordingly:
			- add new port
			- remove port
			- update port
		:param operation: "add" | "remove" | "update"
		:return: None
		"""
		print(f"@Slot portsChanged: {operation}")

		if (operation in ["add", "remove", "update"]):
			self.updateComboboxWithAllowedItems(self.form.drawS11Port, "Port", ["lumped", "microstrip", "circular waveguide", "rectangular waveguide", "coaxial", "coplanar", "stripline", "curve"])
			self.updateComboboxWithAllowedItems(self.form.drawS21Source, "Port", ["lumped", "microstrip", "circular waveguide", "rectangular waveguide", "coaxial", "coplanar", "stripline", "curve"], isActive=True)
			self.updateComboboxWithAllowedItems(self.form.drawS21Target, "Port", ["lumped", "microstrip", "circular waveguide", "rectangular waveguide", "coaxial", "coplanar", "stripline", "curve"], isActive=False)
			self.updateComboboxWithAllowedItems(self.form.portNf2ffInput, "Port", ["lumped", "microstrip", "circular waveguide", "rectangular waveguide", "coaxial", "coplanar", "stripline", "curve"], isActive=True)

	@Slot(str)
	def probesChanged(self, operation):
		"""
		Triggers when there is change in ports tab and updates related settings (now mostly comboboxes for Sxx script generation) in gui accordingly:
			- add/remove/update probe
		:param operation: "add" | "remove" | "update"
		:return: None
		"""
		print(f"@Slot probesChanged: {operation}")

		if (operation in ["add", "remove", "update"]):
			self.updateComboboxWithAllowedItems(self.form.portNf2ffObjectList, "Probe", ["nf2ff box"])

	#########################################################################################################################################
	#
	#	PROBE TAB HANDLERS
	#
	#########################################################################################################################################

	def getProbeItemFromGui(self):
		name = self.form.probeSettingsNameInput.text()

		probeItem = ProbeSettingsItem()
		probeItem.name = name

		if (self.form.probeProbeRadioButton.isChecked()):
			probeItem.type = "probe"
			probeItem.probeType = self.form.probeProbeType.currentText()
			probeItem.direction = self.form.probeProbeDirection.currentText()
			probeItem.probeDomain = self.form.probeProbeDomain.currentText()
			probeItem.probeFrequencyList = [str(self.form.probeProbeFrequencyList.item(i).text()) for i in range(self.form.probeProbeFrequencyList.count())]

		if (self.form.dumpboxProbeRadioButton.isChecked()):
			probeItem.type = "dumpbox"
			probeItem.dumpboxType = self.form.dumpboxProbeType.currentText()
			probeItem.dumpboxDomain = self.form.dumpboxProbeDomain.currentText()
			probeItem.dumpboxFileType = self.form.dumpboxProbeFileType.currentText()
			probeItem.dumpboxFrequencyList = [str(self.form.dumpboxProbeFrequencyList.item(i).text()) for i in range(self.form.dumpboxProbeFrequencyList.count())]

		if (self.form.etDumpProbeRadioButton.isChecked()):
			probeItem.type = "et dump"
		if (self.form.htDumpProbeRadioButton.isChecked()):
			probeItem.type = "ht dump"
		if (self.form.nf2ffBoxProbeRadioButton.isChecked()):
			probeItem.type = "nf2ff box"

		return probeItem

	def probeSettingsAddButtonClicked(self):
		settingsInst = self.getProbeItemFromGui()

		# check for duplicity in names if there is some warning message displayed
		isDuplicityName = self.checkTreeWidgetForDuplicityName(self.form.probeSettingsTreeView, settingsInst.name)

		if (not isDuplicityName and self.probeCheckCurrentSettings(settingsInst)):
			self.guiHelpers.addSettingsItemGui(settingsInst)
			self.guiSignals.probesChanged.emit("add")

	def probeSettingsRemoveButtonClicked(self, name=None):
		# if there is no name it's called from UI, if there is name it's called as function this is done to have one function removing port properly for both cases
		if (type(name) != "str"):
			selectedItem = self.form.probeSettingsTreeView.selectedItems()[0]
			print("Selected probe name: " + selectedItem.text(0))
		else:
			selectedItem = self.form.probeSettingsTreeView.findItems(name, QtCore.Qt.MatchExactly)[0]
			print("Called by name to remove probe: " + selectedItem.text(0))

		probeGroupWidgetItems = self.form.objectAssignmentRightTreeWidget.findItems(
			selectedItem.text(0),
			QtCore.Qt.MatchExactly | QtCore.Qt.MatchFlag.MatchRecursive
		)
		probeGroupItem = None
		for item in probeGroupWidgetItems:
			if (item.parent().text(0) == "Probe"):
				probeGroupItem = item
		print("Currently removing probe item: " + probeGroupItem.text(0))

		# Removing from Object Assignment Tree
		self.form.probeSettingsTreeView.invisibleRootItem().removeChild(selectedItem)
		probeGroupItem.parent().removeChild(probeGroupItem)

		# Emit signal about remove port to update comboboxes
		self.guiSignals.probesChanged.emit("remove")

	def probeSettingsUpdateButtonClicked(self):
		### capture UI settings
		settingsInst = self.getProbeItemFromGui()

		### replace old with new settingsInst
		selectedItems = self.form.probeSettingsTreeView.selectedItems()
		if len(selectedItems) != 1:
			return

		isDuplicityName = self.checkTreeWidgetForDuplicityName(self.form.probeSettingsTreeView, settingsInst.name, ignoreSelectedItem=False)
		if (not isDuplicityName and self.probeCheckCurrentSettings(settingsInst)):
			selectedItems[0].setData(0, QtCore.Qt.UserRole, settingsInst)

			### update other UI elements to propagate changes
			# replace oudated copy of settingsInst
			self.updateObjectAssignmentRightTreeWidgetItemData("Probe", selectedItems[0].text(0), settingsInst)

			# emit rename signal
			if (selectedItems[0].text(0) != settingsInst.name):
				self.guiSignals.probeRenamed.emit(selectedItems[0].text(0), settingsInst.name)

			# Emit signal about remove port to update comboboxes
			self.guiSignals.probesChanged.emit("update")

			# Display message to user
			self.guiHelpers.displayMessage(f"Probe {settingsInst.name} was updated", forceModal=False)

	def probeSettingsTypeChoosed(self):
		#first disable all additional settings for Probes
		self.form.probeProbeSettingsGroup.setEnabled(False)
		self.form.dumpboxProbeSettingsGroup.setEnabled(False)

		if (self.form.probeProbeRadioButton.isChecked()):
			self.form.probeProbeSettingsGroup.setEnabled(True)
			self.guiHelpers.probeSpecificSettingsTabSetActiveByName("Probe")

		elif (self.form.dumpboxProbeRadioButton.isChecked()):
			self.form.dumpboxProbeSettingsGroup.setEnabled(True)
			self.guiHelpers.probeSpecificSettingsTabSetActiveByName("DumpBox")

		else:
			self.guiHelpers.probeSpecificSettingsTabSetActiveByName("")

	def probeTreeWidgetItemChanged(self, current, previous):
		print("Probe item changed.")

		#if last item was erased from port list do nothing
		if not self.form.probeSettingsTreeView.currentItem():
			return

		currSetting = self.form.probeSettingsTreeView.currentItem().data(0, QtCore.Qt.UserRole)
		self.form.probeSettingsNameInput.setText(currSetting.name)

		if (currSetting.type.lower() == "et dump"):
			self.form.etDumpProbeRadioButton.click()

		elif (currSetting.type.lower() == "ht dump"):
			self.form.htDumpProbeRadioButton.click()

		elif (currSetting.type.lower() == "nf2ff box"):
			self.form.nf2ffBoxProbeRadioButton.click()

		elif (currSetting.type.lower() == "probe"):
			try:
				self.form.probeProbeRadioButton.click()
				self.guiHelpers.setComboboxItem(self.form.probeProbeDirection, currSetting.direction)
				self.guiHelpers.setComboboxItem(self.form.probeProbeType, currSetting.probeType)
				self.guiHelpers.setComboboxItem(self.form.probeProbeDomain, currSetting.probeDomain)

				self.form.probeProbeFrequencyList.clear()
				for freqItemStr in currSetting.probeFrequencyList:
					self.form.probeProbeFrequencyList.addItem(freqItemStr)
			except Exception as e:
				self.guiHelpers.displayMessage(f"ERROR update probe current settings: {e}", forceModal=False)

		elif (currSetting.type.lower() == "dumpbox"):
			try:
				self.form.dumpboxProbeRadioButton.click()
				self.guiHelpers.setComboboxItem(self.form.dumpboxProbeType, currSetting.dumpboxType)
				self.guiHelpers.setComboboxItem(self.form.dumpboxProbeDomain, currSetting.dumpboxDomain)
				self.guiHelpers.setComboboxItem(self.form.dumpboxProbeFileType, currSetting.dumpboxFileType)

				self.form.dumpboxProbeFrequencyList.clear()
				for freqItemStr in currSetting.dumpboxFrequencyList:
					self.form.dumpboxProbeFrequencyList.addItem(freqItemStr)
			except Exception as e:
				self.guiHelpers.displayMessage(f"ERROR update dumpbox current settings: {e}", forceModal=False)

		else:
			pass #no gui update

		return


	#########################################################################################################################################
	#
	#	SOME GUI HANDLERS
	#
	#########################################################################################################################################

	def updateMaterialComboBoxAllMaterials(self, comboboxRef):
		"""
		Update items in combobox for provided combobox control, this add all materials available. It clears all items and fill them agains with actual values.
		"""
		comboboxRef.clear()

		# iterates over materials due if there are metal or conducting sheet they are added into microstrip possible materials combobox
		objectAssignemntRightPortParent = self.form.objectAssignmentRightTreeWidget.findItems(
			"Material",
			QtCore.Qt.MatchExactly | QtCore.Qt.MatchFlag.MatchRecursive
			)[0]

		# here user defined are added into coaxial possible material combobox
		for k in range(objectAssignemntRightPortParent.childCount()):
			materialData = objectAssignemntRightPortParent.child(k).data(0, QtCore.Qt.UserRole)
			comboboxRef.addItem(materialData.name)

	def updateMaterialComboBoxJustUserdefined(self, comboboxRef):
		"""
		Update items in combobox for provided combobox control, this add just user defined material types. It clears all items and fill them agains with actual values.
		"""
		comboboxRef.clear()

		# iterates over materials due if there are metal or conducting sheet they are added into microstrip possible materials combobox
		objectAssignemntRightPortParent = self.form.objectAssignmentRightTreeWidget.findItems(
			"Material",
			QtCore.Qt.MatchExactly | QtCore.Qt.MatchFlag.MatchRecursive
			)[0]

		# here user defined are added into coaxial possible material combobox
		for k in range(objectAssignemntRightPortParent.childCount()):
			materialData = objectAssignemntRightPortParent.child(k).data(0, QtCore.Qt.UserRole)
			if (materialData.type in ["userdefined"]):
				comboboxRef.addItem(materialData.name)

	def updateMaterialComboBoxJustMetals(self, comboboxRef):
		"""
		Update items in combobox for provided combobox control, this add just metallic material types (metal, conductive sheet). It clears all items and fill them agains with actual values.
		"""
		currentItemText = comboboxRef.currentText()
		print(f"---> updateMaterialComboBoxJustMetals() setComboboxItem {comboboxRef}, current text '{currentItemText}' current item index {comboboxRef.currentIndex()}")

		comboboxRef.clear()

		# iterates over materials due if there are metal or conducting sheet they are added into microstrip possible materials combobox
		objectAssignemntRightPortParent = self.form.objectAssignmentRightTreeWidget.findItems(
			"Material",
			QtCore.Qt.MatchExactly | QtCore.Qt.MatchFlag.MatchRecursive
			)[0]

		# here user defined are added into coaxial possible material combobox
		selectedItem = None
		for k in range(objectAssignemntRightPortParent.childCount()):
			materialData = objectAssignemntRightPortParent.child(k).data(0, QtCore.Qt.UserRole)
			if (materialData.type in ["metal", "conducting sheet"]):
				newItem = comboboxRef.addItem(materialData.name)
				print(f"updating {comboboxRef} with item: {materialData.name}")

		# this set value of combobox to previous value
		#if (not currentItemText is None and materialData.name == currentItemText):
		print(f"---> updateMaterialComboBoxJustMetals() setComboboxItem for text '{currentItemText}'")
		self.guiHelpers.setComboboxItem(comboboxRef, currentItemText)

	@Slot(int)
	def microstripPortDirectionOnChange(self, activatedItemIndex):
		"""
		Update microstrip port propagation direction on port tab in microstrip settings according coplanar port direction, based on its plane:
			- for XY plane there are just possible directions x+, x-, y+, y-
			- for XZ plane there are just possible directions x+, x-, z+, z-
			- for YZ plane there are just possible directions y+, y-, y+, y-
		This is advanced GUI function to provide user just allowed direction for microstrip port in settings and to remove not allowed direction, script maybe will run but results would be strange like no port...
		:return: None
		"""
		previousPropagationValue = self.form.microstripPortPropagationComboBox.currentText()

		self.form.microstripPortPropagationComboBox.clear()
		for directionAxis in list(self.form.microstripPortDirection.currentText().lower()[0:2]):
			self.form.microstripPortPropagationComboBox.addItem(directionAxis + "+")
			self.form.microstripPortPropagationComboBox.addItem(directionAxis + "-")

		self.guiHelpers.setComboboxItem(self.form.microstripPortPropagationComboBox, previousPropagationValue)

	@Slot(int)
	def coplanarPortDirectionOnChange(self, activatedItemIndex):
		"""
		Update coplanar port propagation direction on port tab in coplanar settings according coplanar port direction, based on its plane:
			- for XY plane there are just possible directions x+, x-, y+, y-
			- for XZ plane there are just possible directions x+, x-, z+, z-
			- for YZ plane there are just possible directions y+, y-, y+, y-
		This is advanced GUI function to provide user just allowed direction for coplanar port in settings and to remove not allowed direction, script maybe will run but results would be strange like no port...
		:return: None
		"""
		previousPropagationValue = self.form.coplanarPortPropagationComboBox.currentText()

		self.form.coplanarPortPropagationComboBox.clear()
		for directionAxis in list(self.form.coplanarPortDirection.currentText().lower()[0:2]):
			self.form.coplanarPortPropagationComboBox.addItem(directionAxis + "+")
			self.form.coplanarPortPropagationComboBox.addItem(directionAxis + "-")

		self.guiHelpers.setComboboxItem(self.form.coplanarPortPropagationComboBox, previousPropagationValue)

	@Slot(int)
	def striplinePortDirectionOnChange(self, activatedItemIndex):
		"""
		Update stripline port propagation direction on port tab in stripline settings according coplanar port direction, based on its plane:
			- for XY plane there are just possible directions x+, x-, y+, y-
			- for XZ plane there are just possible directions x+, x-, z+, z-
			- for YZ plane there are just possible directions y+, y-, y+, y-
		This is advanced GUI function to provide user just allowed direction for stripline port in settings and to remove not allowed direction, script maybe will run but results would be strange like no port...
		:return: None
		"""
		previousPropagationValue = self.form.striplinePortPropagationComboBox.currentText()

		self.form.striplinePortPropagationComboBox.clear()
		for directionAxis in list(self.form.striplinePortDirection.currentText().lower()[0:2]):
			self.form.striplinePortPropagationComboBox.addItem(directionAxis + "+")
			self.form.striplinePortPropagationComboBox.addItem(directionAxis + "-")

		self.guiHelpers.setComboboxItem(self.form.striplinePortPropagationComboBox, previousPropagationValue)

	#  _     _    _ __  __ _____  ______ _____    _____        _____ _______            _   _   _
	# | |   | |  | |  \/  |  __ \|  ____|  __ \  |  __ \ /\   |  __ \__   __|          | | | | (_)
	# | |   | |  | | \  / | |__) | |__  | |  | | | |__) /  \  | |__) | | |     ___  ___| |_| |_ _ _ __   __ _ ___
	# | |   | |  | | |\/| |  ___/|  __| | |  | | |  ___/ /\ \ |  _  /  | |    / __|/ _ \ __| __| | '_ \ / _` / __|
	# | |___| |__| | |  | | |    | |____| |__| | | |  / ____ \| | \ \  | |    \__ \  __/ |_| |_| | | | | (_| \__ \
	# |______\____/|_|  |_|_|    |______|_____/  |_| /_/    \_\_|  \_\ |_|    |___/\___|\__|\__|_|_| |_|\__, |___/
	#                                                                                                    __/ |
	#                                                                                                   |___/
	#

	def getLumpedPartItemFromGui(self):
		name = self.form.lumpedPartSettingsNameInput.text()

		lumpedPartItem = LumpedPartSettingsItem()
		lumpedPartItem.name = name

		if (self.form.lumpedPartLEnable.isChecked()):
			lumpedPartItem.params['L'] = self.form.lumpedPartLInput.value()
			lumpedPartItem.params['LUnits'] = self.form.lumpedPartLUnits.currentText()
			lumpedPartItem.params['LEnabled'] = 1
		if (self.form.lumpedPartREnable.isChecked()):
			lumpedPartItem.params['R'] = self.form.lumpedPartRInput.value()
			lumpedPartItem.params['RUnits'] = self.form.lumpedPartRUnits.currentText()
			lumpedPartItem.params['REnabled'] = 1
		if (self.form.lumpedPartCEnable.isChecked()):
			lumpedPartItem.params['C'] = self.form.lumpedPartCInput.value()
			lumpedPartItem.params['CUnits'] = self.form.lumpedPartCUnits.currentText()
			lumpedPartItem.params['CEnabled'] = 1

		lumpedPartItem.params['capsEnabled'] = self.form.lumpedPartCapsEnable.isChecked()
		lumpedPartItem.params['direction'] = self.form.lumpedPartDirection.currentText()
		lumpedPartItem.params['combinationType'] = self.form.lumpedPartCombinationType.currentText()

		return lumpedPartItem


	def lumpedPartSettingsAddButtonClicked(self):
		# capture UI settings
		settingsInst = self.getLumpedPartItemFromGui()

		#check for duplicity in names if there is some warning message displayed
		isDuplicityName = self.checkTreeWidgetForDuplicityName(self.form.lumpedPartTreeView, settingsInst.name)
		if (not isDuplicityName):
			self.guiHelpers.addSettingsItemGui(settingsInst)


	def lumpedPartSettingsRemoveButtonClicked(self):
		selectedItem = self.form.lumpedPartTreeView.selectedItems()[0]
		print("Selected lumpedpart name: " + selectedItem.text(0))

		lumpedPartGroupWidgetItems = self.form.objectAssignmentRightTreeWidget.findItems(
			selectedItem.text(0),
			QtCore.Qt.MatchExactly|QtCore.Qt.MatchFlag.MatchRecursive
			)
		lumpedPartGroupItem = None
		for item in lumpedPartGroupWidgetItems:
			if (item.parent().text(0) == "LumpedPart"):
				lumpedPartGroupItem = item
		print("Currently removing lumped part item: " + lumpedPartGroupItem.text(0))

		###
		#	Removing from Priority List
		###
		priorityName = lumpedPartGroupItem.parent().text(0) + ", " + lumpedPartGroupItem.text(0);
		self.guiHelpers.removePriorityName(priorityName)

		self.form.lumpedPartTreeView.invisibleRootItem().removeChild(selectedItem)
		lumpedPartGroupItem.parent().removeChild(lumpedPartGroupItem)


	def lumpedPartSettingsUpdateButtonClicked(self):
		### capture UI settings
		settingsInst = self.getLumpedPartItemFromGui()

		### replace old with new settingsInst
		selectedItems = self.form.lumpedPartTreeView.selectedItems()
		if len(selectedItems) != 1:
			return

		isDuplicityName = self.checkTreeWidgetForDuplicityName(self.form.lumpedPartTreeView, settingsInst.name, ignoreSelectedItem=False)
		if (not isDuplicityName):
			selectedItems[0].setData(0, QtCore.Qt.UserRole, settingsInst)

			### update other UI elements to propagate changes
			# replace oudated copy of settingsInst
			self.updateObjectAssignmentRightTreeWidgetItemData("LumpedPart", selectedItems[0].text(0), settingsInst)

			# emit rename signal
			if (selectedItems[0].text(0) != settingsInst.name):
				self.guiSignals.lumpedPartRenamed.emit(selectedItems[0].text(0), settingsInst.name)

			self.guiHelpers.displayMessage(f"LumpedPart {settingsInst.name} updated.", forceModal=False)

	#   _____________   ____________  ___    __       _____ _______________________   _____________
	#  / ____/ ____/ | / / ____/ __ \/   |  / /      / ___// ____/_  __/_  __/  _/ | / / ____/ ___/
	# / / __/ __/ /  |/ / __/ / /_/ / /| | / /       \__ \/ __/   / /   / /  / //  |/ / / __ \__ \
	#/ /_/ / /___/ /|  / /___/ _, _/ ___ |/ /___    ___/ / /___  / /   / / _/ // /|  / /_/ /___/ /
	#\____/_____/_/ |_/_____/_/ |_/_/  |_/_____/   /____/_____/ /_/   /_/ /___/_/ |_/\____//____/
	#
	def materialTreeWidgetItemChanged(self, current, previous):
		print("materialTreeWidgetItemChanged(): Material item changed.")

		#if last item was erased from port list do nothing
		if not self.form.materialSettingsTreeView.currentItem():
			return

		currSetting = self.form.materialSettingsTreeView.currentItem().data(0, QtCore.Qt.UserRole)
		self.form.materialSettingsNameInput.setText(currSetting.name)

		#ATTENTIONS there is ocnversion to float() used BELOW
		if (currSetting.type == 'metal'):
			self.form.materialMetalRadioButton.click()
		elif (currSetting.type == 'userdefined'):
			self.form.materialUserDefinedRadioButton.click()

			self.form.materialEpsilonNumberInput.setValue(float(currSetting.constants['epsilon']))
			self.form.materialMueNumberInput.setValue(float(currSetting.constants['mue']))
			self.form.materialKappaNumberInput.setValue(float(currSetting.constants['kappa']))
			self.form.materialSigmaNumberInput.setValue(float(currSetting.constants['sigma']))
		elif (currSetting.type == 'conducting sheet'):
			self.form.materialConductingSheetRadioButton.click()

			# set microstrip related values in material tab (thickness and units)
			# if not found looks for 'um'
			#	else set first item in combobox what is 'm'
			try:
				self.form.materialConductingSheetThickness.setValue(float(currSetting.constants['conductingSheetThicknessValue']))
				index = self.form.materialConductingSheetUnits.findText(currSetting.constants['conductingSheetThicknessUnits'], QtCore.Qt.MatchFixedString)
				if index >= 0:
					self.form.materialConductingSheetUnits.setCurrentIndex(index)
				else:
					index = self.form.materialConductingSheetUnits.findText("um", QtCore.Qt.MatchFixedString)
					if index >= 0:
						self.form.materialConductingSheetUnits.setCurrentIndex(index)
					else:
						self.form.materialConductingSheetUnits.setCurrentIndex(0)

				self.form.materialConductingSheetConductivity.setValue(float(currSetting.constants['conductingSheetConductivity']))
			except Exception as e:
				print(f"materialTreeWidgetItemChanged() ERROR: {e}")

		return

	def gridTreeWidgetItemChanged(self, current, previous):
		print("Grid item changed.")

		#if last item was erased from port list do nothing
		if not self.form.gridSettingsTreeView.currentItem():
			return

		#set values to zero to not left previous settings to confuse user
		self.form.fixedDistanceXNumberInput.setValue(0)
		self.form.fixedDistanceYNumberInput.setValue(0)
		self.form.fixedDistanceZNumberInput.setValue(0)
		self.form.fixedCountXNumberInput.setValue(0)
		self.form.fixedCountYNumberInput.setValue(0)
		self.form.fixedCountZNumberInput.setValue(0)
		self.form.userDefinedGridLinesTextInput.setPlainText("")
		self.form.gridXEnable.setChecked(False)
		self.form.gridYEnable.setChecked(False)
		self.form.gridZEnable.setChecked(False)
		self.form.smoothMeshXMaxRes.setValue(0)
		self.form.smoothMeshYMaxRes.setValue(0)
		self.form.smoothMeshZMaxRes.setValue(0)
		self.form.gridGenerateLinesInsideCheckbox.setChecked(False)
		self.form.gridTopPriorityLinesCheckbox.setChecked(False)
		self.form.gridOffsetX.setValue(0)
		self.form.gridOffsetY.setValue(0)
		self.form.gridOffsetZ.setValue(0)
		self.guiHelpers.setComboboxItem(self.form.gridOffsetUnits, 'um')

		#set values in grid settings by actual selected item
		currSetting = self.form.gridSettingsTreeView.currentItem().data(0, QtCore.Qt.UserRole)
		self.form.gridSettingsNameInput.setText(currSetting.name)

		#set grid units ie. mm, deg
		self.guiHelpers.setComboboxItem(self.form.gridUnitsInput, currSetting.units)
		self.guiHelpers.setComboboxItem(self.form.gridUnitsInput_2, currSetting.unitsAngle)

		if (currSetting.coordsType == "rectangular"):
			self.form.gridRectangularRadio.click()
		if (currSetting.coordsType == "cylindrical"):
			self.form.gridCylindricalRadio.click()

		try:
			self.form.gridXEnable.setChecked(currSetting.xenabled)
			self.form.gridYEnable.setChecked(currSetting.yenabled)
			self.form.gridZEnable.setChecked(currSetting.zenabled)
		except:
			pass

		if (currSetting.type == "Fixed Distance"):
			self.form.fixedDistanceRadioButton.click()

			self.form.fixedDistanceXNumberInput.setValue(currSetting.fixedDistance['x'])
			self.form.fixedDistanceYNumberInput.setValue(currSetting.fixedDistance['y'])
			self.form.fixedDistanceZNumberInput.setValue(currSetting.fixedDistance['z'])
		elif (currSetting.type == "Fixed Count"):
			self.form.fixedCountRadioButton.click()

			self.form.fixedCountXNumberInput.setValue(currSetting.fixedCount['x'])
			self.form.fixedCountYNumberInput.setValue(currSetting.fixedCount['y'])
			self.form.fixedCountZNumberInput.setValue(currSetting.fixedCount['z'])

		elif (currSetting.type == "Smooth Mesh"):
			try:
				self.form.smoothMeshRadioButton.click()

				self.form.smoothMeshXMaxRes.setValue(currSetting.smoothMesh['xMaxRes'])
				self.form.smoothMeshYMaxRes.setValue(currSetting.smoothMesh['yMaxRes'])
				self.form.smoothMeshZMaxRes.setValue(currSetting.smoothMesh['zMaxRes'])
			except:
				pass

		elif (currSetting.type == "User Defined"):
			self.form.userDefinedRadioButton.click()
			self.form.userDefinedGridLinesTextInput.setPlainText(currSetting.userDefined['data'])

		else:
			pass

		self.form.gridGenerateLinesInsideCheckbox.setChecked(currSetting.generateLinesInside)
		self.form.gridTopPriorityLinesCheckbox.setChecked(currSetting.topPriorityLines)

		try:
			self.form.gridOffsetX.setValue(currSetting.gridOffset['x'])
			self.form.gridOffsetY.setValue(currSetting.gridOffset['y'])
			self.form.gridOffsetZ.setValue(currSetting.gridOffset['z'])
			self.guiHelpers.setComboboxItem(self.form.gridOffsetUnits, currSetting.gridOffset['units'])
		except:
			pass

		return

	def excitationTreeWidgetItemChanged(self, current, previous):
		print("Excitation item changed.")

		#if last item was erased from port list do nothing
		if not self.form.excitationSettingsTreeView.currentItem():
			return

		currSetting = self.form.excitationSettingsTreeView.currentItem().data(0, QtCore.Qt.UserRole)
		self.form.excitationSettingsNameInput.setText(currSetting.name)
		if (currSetting.type == "sinusodial"):
			self.form.sinusodialExcitationRadioButton.click()
			self.form.sinusodialExcitationF0NumberInput.setValue(currSetting.sinusodial['f0'])

		elif (currSetting.type == "gaussian"):
			self.form.gaussianExcitationRadioButton.click()
			self.form.gaussianExcitationF0NumberInput.setValue(currSetting.gaussian['f0'])
			self.form.gaussianExcitationFcNumberInput.setValue(currSetting.gaussian['fc'])

		elif (currSetting.type == "dirac"):
			self.form.diracExcitationRadioButton.click()
			self.form.diracExcitationFmNumberInput.setValue(currSetting.dirac['fm'])

		elif (currSetting.type == "step"):
			self.form.stepExcitationRadioButton.click()
			self.form.stepExcitationFmNumberInput.setValue(currSetting.step['fm'])

		elif (currSetting.type == "custom"):
			self.form.customExcitationRadioButton.click()
			self.form.customExcitationTextInput.setText(currSetting.custom['functionStr'])
			self.form.customExcitationF0NumberInput.setValue(currSetting.custom['f0'])

			index = self.form.excitationUnitsNumberInput.findText(currSetting.units, QtCore.Qt.MatchFixedString)
			if index >= 0:
				self.form.excitationUnitsNumberInput.setCurrentIndex(index)
		else:
			return #no gui update

		index = self.form.excitationUnitsNumberInput.findText(currSetting.units, QtCore.Qt.MatchFixedString)
		if index >= 0:
			self.form.excitationUnitsNumberInput.setCurrentIndex(index)

		return

	def portTreeWidgetItemChanged(self, current, previous):
		print("portTreeWidgetItemChanged(): Port item changed.")

		#if last item was erased from port list do nothing
		if not self.form.portSettingsTreeView.currentItem():
			return

		cartesianCylindricCoordsAlternativeValues = GridSettingsItem.cartesianCylindricCoordsAlternativeValues

		currSetting = self.form.portSettingsTreeView.currentItem().data(0, QtCore.Qt.UserRole)
		self.form.portSettingsNameInput.setText(currSetting.name)

		if (currSetting.type.lower() == "lumped"):
			try:
				self.form.lumpedPortRadioButton.click()
				self.form.lumpedPortResistanceValue.setValue(float(currSetting.R))
				self.guiHelpers.setComboboxItem(self.form.lumpedPortResistanceUnits, currSetting.RUnits)
				self.guiHelpers.setComboboxItem(self.form.lumpedPortDirection, currSetting.direction, cartesianCylindricCoordsAlternativeValues)
				self.form.lumpedPortActive.setChecked(currSetting.isActive)

				self.form.lumpedPortInfinitResistance.setChecked(currSetting.infiniteResistance)
				self.form.lumpedPortExcitationAmplitude.setValue(currSetting.excitationAmplitude)
			except Exception as e:
				self.guiHelpers.displayMessage(f"ERROR update lumped current settings: {e}", forceModal=False)

		elif (currSetting.type.lower() == "microstrip"):
			self.form.microstripPortRadioButton.click()

			try:
				self.form.microstripPortActive.setChecked(currSetting.isActive)
				self.form.microstripPortResistanceValue.setValue(float(currSetting.R))
				self.guiHelpers.setComboboxItem(self.form.microstripPortResistanceUnits, currSetting.RUnits)
				self.guiHelpers.setComboboxItem(self.form.microstripPortDirection, currSetting.direction)

				self.form.microstripPortDirection.activated.emit(self.form.microstripPortDirection.currentIndex())

				self.form.microstripPortFeedpointShiftValue.setValue(currSetting.mslFeedShiftValue)
				self.form.microstripPortMeasureShiftValue.setValue(currSetting.mslMeasPlaneShiftValue)

				self.guiHelpers.setComboboxItem(self.form.microstripPortFeedpointShiftUnits, currSetting.mslFeedShiftUnits)
				self.guiHelpers.setComboboxItem(self.form.microstripPortMeasureShiftUnits, currSetting.mslMeasPlaneShiftUnits)
				self.guiHelpers.setComboboxItem(self.form.microstripPortPropagationComboBox, currSetting.mslPropagation, cartesianCylindricCoordsAlternativeValues)
				self.guiHelpers.setComboboxItem(self.form.microstripPortMaterialComboBox, currSetting.mslMaterial)

				self.form.microstripPortInfinitResistance.setChecked(currSetting.infiniteResistance)
				self.form.microstripPortExcitationAmplitude.setValue(currSetting.excitationAmplitude)
			except Exception as e:
				self.guiHelpers.displayMessage(f"ERROR update microstrip current settings: {e}", forceModal=False)

		elif (currSetting.type.lower() == "coaxial"):
			self.form.coaxialPortRadioButton.click()
			try:
				self.form.coaxialPortActive.setChecked(currSetting.isActive)
				self.form.coaxialPortResistanceValue.setValue(float(currSetting.R))
				self.guiHelpers.setComboboxItem(self.form.coaxialPortResistanceUnits, currSetting.RUnits)
				self.guiHelpers.setComboboxItem(self.form.coaxialPortDirection, currSetting.direction, cartesianCylindricCoordsAlternativeValues)

				self.form.coaxialPortInnerRadiusValue.setValue(currSetting.coaxialInnerRadiusValue)
				self.form.coaxialPortShellThicknessValue.setValue(currSetting.coaxialShellThicknessValue)
				self.form.coaxialPortFeedpointShiftValue.setValue(currSetting.coaxialFeedpointShiftValue)
				self.form.coaxialPortMeasureShiftValue.setValue(currSetting.coaxialMeasPlaneShiftValue)

				self.guiHelpers.setComboboxItem(self.form.coaxialPortMeasureShiftUnits, currSetting.coaxialMeasPlaneShiftUnits)
				self.guiHelpers.setComboboxItem(self.form.coaxialPortFeedpointShiftUnits, currSetting.coaxialFeedpointShiftUnits)
				self.guiHelpers.setComboboxItem(self.form.coaxialPortShellThicknessUnits, currSetting.coaxialShellThicknessUnits)
				self.guiHelpers.setComboboxItem(self.form.coaxialPortInnerRadiusUnits, currSetting.coaxialInnerRadiusUnits)
				self.guiHelpers.setComboboxItem(self.form.coaxialPortMaterialComboBox, currSetting.coaxialMaterial)
				self.guiHelpers.setComboboxItem(self.form.coaxialPortConductorMaterialComboBox, currSetting.coaxialConductorMaterial)

				self.form.coaxialPortInfinitResistance.setChecked(currSetting.infiniteResistance)
				self.form.coaxialPortExcitationAmplitude.setValue(currSetting.excitationAmplitude)
			except Exception as e:
				self.guiHelpers.displayMessage(f"ERROR update coaxial current settings: {e}", forceModal=False)

		elif (currSetting.type.lower() == "coplanar"):
			self.form.coplanarPortRadioButton.click()
			try:
				self.form.coplanarPortActive.setChecked(currSetting.isActive)
				self.form.coplanarPortResistanceValue.setValue(float(currSetting.R))
				self.guiHelpers.setComboboxItem(self.form.coplanarPortResistanceUnits, currSetting.RUnits)
				self.guiHelpers.setComboboxItem(self.form.coplanarPortDirection, currSetting.direction, cartesianCylindricCoordsAlternativeValues)

				#	emit signal to update direction combobox, must be here to have right reaction when change direction combobox,
				#	then click on radiobutton stripline and
				#	then then on some coplanar port in port treewidget item
				self.form.coplanarPortDirection.activated.emit(self.form.coplanarPortDirection.currentIndex())

				self.form.coplanarPortGapValue.setValue(currSetting.coplanarGapValue)
				self.form.coplanarPortFeedpointShiftValue.setValue(currSetting.coplanarFeedpointShiftValue)
				self.form.coplanarPortMeasureShiftValue.setValue(currSetting.coplanarMeasPlaneShiftValue)

				self.guiHelpers.setComboboxItem(self.form.coplanarPortGapUnits, currSetting.coplanarGapUnits)
				self.guiHelpers.setComboboxItem(self.form.coplanarPortFeedpointShiftUnits, currSetting.coplanarFeedpointShiftUnits)
				self.guiHelpers.setComboboxItem(self.form.coplanarPortMeasureShiftUnits, currSetting.coplanarMeasPlaneShiftUnits)
				self.guiHelpers.setComboboxItem(self.form.coplanarPortPropagationComboBox, currSetting.coplanarPropagation)
				self.guiHelpers.setComboboxItem(self.form.coplanarPortMaterialComboBox, currSetting.coplanarMaterial)

				self.form.coplanarPortInfinitResistance.setChecked(currSetting.infiniteResistance)
				self.form.coplanarPortExcitationAmplitude.setValue(currSetting.excitationAmplitude)
			except Exception as e:
				self.guiHelpers.displayMessage(f"ERROR update coplanar current settings: {e}", forceModal=False)

		elif (currSetting.type.lower() == "stripline"):
			self.form.striplinePortRadioButton.click()
			try:
				self.form.striplinePortActive.setChecked(currSetting.isActive)
				self.form.striplinePortResistanceValue.setValue(float(currSetting.R))
				self.guiHelpers.setComboboxItem(self.form.striplinePortResistanceUnits, currSetting.RUnits)
				self.guiHelpers.setComboboxItem(self.form.striplinePortDirection, currSetting.direction, cartesianCylindricCoordsAlternativeValues)

				self.form.striplinePortDirection.activated.emit(self.form.striplinePortDirection.currentIndex())

				self.form.striplinePortFeedpointShiftValue.setValue(currSetting.striplineFeedpointShiftValue)
				self.form.striplinePortMeasureShiftValue.setValue(currSetting.striplineMeasPlaneShiftValue)

				self.guiHelpers.setComboboxItem(self.form.striplinePortFeedpointShiftUnits, currSetting.striplineFeedpointShiftUnits)
				self.guiHelpers.setComboboxItem(self.form.striplinePortMeasureShiftUnits, currSetting.striplineMeasPlaneShiftUnits)
				self.guiHelpers.setComboboxItem(self.form.striplinePortPropagationComboBox, currSetting.striplinePropagation)

				self.form.striplinePortInfinitResistance.setChecked(currSetting.infiniteResistance)
				self.form.striplinePortExcitationAmplitude.setValue(currSetting.excitationAmplitude)
			except Exception as e:
				self.guiHelpers.displayMessage(f"ERROR update stripline current settings: {e}", forceModal=False)

		elif (currSetting.type.lower() == "circular waveguide"):
			self.form.circularWaveguidePortRadioButton.click()

			self.form.portCircWaveguideActive.setChecked(currSetting.isActive)

			self.guiHelpers.setComboboxItem(self.form.portCircWaveguideModeName, currSetting.modeName)						#set mode, e.g. TE11, TM21, ...
			self.guiHelpers.setComboboxItem(self.form.portCircWaveguidePolarizationAngle, currSetting.polarizationAngle)
			self.guiHelpers.setComboboxItem(self.form.portCircWaveguideDirection, currSetting.waveguideCircDir, cartesianCylindricCoordsAlternativeValues)

			self.form.portCircWaveguideExcitationAmplitude.setValue(float(currSetting.excitationAmplitude))
		elif (currSetting.type.lower() == "rectangular waveguide"):
			self.form.rectangularWaveguidePortRadioButton.click()

			self.form.portRectWaveguideActive.setChecked(currSetting.isActive)

			self.guiHelpers.setComboboxItem(self.form.portRectWaveguideModeName, currSetting.modeName)						#set mode, e.g. TE11, TM21, ...
			self.guiHelpers.setComboboxItem(self.form.portRectWaveguideDirection, currSetting.waveguideRectDir, cartesianCylindricCoordsAlternativeValues)

			self.form.portRectWaveguideExcitationAmplitude.setValue(float(currSetting.excitationAmplitude))

		elif (currSetting.type.lower() == "curve"):
			try:
				self.form.curvePortRadioButton.click()

				self.form.curvePortActive.setChecked(currSetting.isActive)
				self.form.curvePortResistanceValue.setValue(float(currSetting.R))
				self.guiHelpers.setComboboxItem(self.form.curvePortResistanceUnits, currSetting.RUnits)
				self.form.curvePortInfinitResistance.setChecked(currSetting.infiniteResistance)
				self.form.curvePortExcitationAmplitude.setValue(currSetting.excitationAmplitude)
			except Exception as e:
				self.guiHelpers.displayMessage(f"ERROR update curve port current settings: {e}", forceModal=False)

		else:
			pass #no gui update

		return

	def simulationTreeWidgetItemChanged(self, current, previous):
		print("Simulation params changed.")
		return

	def lumpedPartTreeWidgetItemChanged(self, current, previous):
		print("Lumped part item changed.")

		#if last item was erased from port list do nothing
		if not self.form.lumpedPartTreeView.currentItem():
			return

		currSetting = self.form.lumpedPartTreeView.currentItem().data(0, QtCore.Qt.UserRole)
		self.form.lumpedPartSettingsNameInput.setText(currSetting.name)

		self.form.lumpedPartLEnable.setChecked(False)
		self.form.lumpedPartREnable.setChecked(False)
		self.form.lumpedPartCEnable.setChecked(False)
		if (currSetting.params['LEnabled']):
			self.form.lumpedPartLEnable.setChecked(True)
		if (currSetting.params['REnabled']):
			self.form.lumpedPartREnable.setChecked(True)
		if (currSetting.params['CEnabled']):
			self.form.lumpedPartCEnable.setChecked(True)

		self.form.lumpedPartLInput.setValue(currSetting.params['L'])
		self.form.lumpedPartRInput.setValue(currSetting.params['R'])
		self.form.lumpedPartCInput.setValue(currSetting.params['C'])

		index = self.form.lumpedPartLUnits.findText(currSetting.params['LUnits'], QtCore.Qt.MatchFixedString)
		if index >= 0:
			self.form.lumpedPartLUnits.setCurrentIndex(index)
		index = self.form.lumpedPartRUnits.findText(currSetting.params['RUnits'], QtCore.Qt.MatchFixedString)
		if index >= 0:
			self.form.lumpedPartRUnits.setCurrentIndex(index)
		index = self.form.lumpedPartCUnits.findText(currSetting.params['CUnits'], QtCore.Qt.MatchFixedString)
		if index >= 0:
			self.form.lumpedPartCUnits.setCurrentIndex(index)

		try:
			self.form.lumpedPartCapsEnable.setChecked(_bool(currSetting.params['capsEnabled']))
		except:
			print("WARNING: LumpedPart: capsEnabled value not found.")
			pass

		try:
			index = self.form.lumpedPartDirection.findText(currSetting.params['direction'], QtCore.Qt.MatchFixedString)
			if index >= 0:
				self.form.lumpedPartDirection.setCurrentIndex(index)
		except:
			print("WARNING: LumpedPart: direction value not found.")
			pass

		try:
			index = self.form.lumpedPartCombinationType.findText(currSetting.params['combinationType'], QtCore.Qt.MatchFixedString)
			if index >= 0:
				self.form.lumpedPartCombinationType.setCurrentIndex(index)
		except:
			print("WARNING: LumpedPart: combinationType value not found.")
			pass

		return

####################################################################################################################################################################
# End of PANEL definition
####################################################################################################################################################################

if __name__ == "__main__":
	#
	#	TODO:
	#		- in case of running from Blender app must run in parallel, now Blender window is waiting for close addon
	#
	if APP_CONTEXT == "Blender":
		"""
			Finally this is running, it will create Misc tab on right side of View3D and there is button for open
			addon to specify simulation.

			Found in forum here: https://blenderartists.org/t/parent-pyqt-window-widget-to-blenders-window/700722/17
			related:			 https://blenderartists.org/t/bqt-custom-ui-for-add-ons-tool-in-blender-with-pyqt-or-pyside/1458808
		"""
		class PYSIDE_PT_tools_my_panel(bpy.types.Panel):
			bl_label = "Export to OpenEMS"
			bl_space_type = 'VIEW_3D'
			bl_region_type = 'UI'

			def draw(self, context):
				layout = self.layout
				layout.operator('pyside.display_window')


		class PYSIDE_OT_display_window(bpy.types.Operator):
			bl_idname = 'pyside.display_window'
			bl_label = "Show Export Dialog"
			bl_options = {'REGISTER'}

			def execute(self, context):
				self.app = QtWidgets.QApplication.instance()
				if not self.app:
					self.app = QtWidgets.QApplication(['blender'])

				self.event_loop = QtCore.QEventLoop()
				self.widget = ExportOpenEMSDialog()
				self.widget.show()

				return {'FINISHED'}

		CLASSES = [PYSIDE_OT_display_window, PYSIDE_PT_tools_my_panel]
		def register():
			for cls in CLASSES:
				bpy.utils.register_class(cls)
		def unregister():
			for cls in CLASSES:
				bpy.utils.unregister_class(cls)

		register()

	elif APP_CONTEXT == "None":
		try:
			app = QtWidgets.QApplication.instance()
			if app is None:
				app = QtWidgets.QApplication(sys.argv)
		except:
			pass

	if APP_CONTEXT in ["None", "FreeCAD"]:
		#
		#	Display openEMS export window.
		#
		panel = ExportOpenEMSDialog()
		panel.show()

	#
	#	If running as standalone application this will fire application and run it (probably starts Qt event loop).
	#
	if APP_CONTEXT in ['None']:
		app.exec_()

	print("ExportOpenEMSDialog.py finished.")
