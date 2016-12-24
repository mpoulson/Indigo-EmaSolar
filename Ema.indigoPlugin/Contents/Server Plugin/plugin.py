#! /usr/bin/env python
# -*- coding: utf-8 -*-
####################

import indigo
import os
import sys
import random
import re
import urllib2
import urllib
import time
from Ema import Ema
from copy import deepcopy
from ghpu import GitHubPluginUpdater
# Need json support; Use "simplejson" for Indigo support
try:
	import simplejson as json
except:
	import json

################################################################################
class Plugin(indigo.PluginBase):
	########################################
	def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
		super(Plugin, self).__init__(pluginId, pluginDisplayName, pluginVersion, pluginPrefs)
		self.Ema = Ema(self)
		self.debug = pluginPrefs.get("debug", False)
		self.UserID = None
		self.Password = None
		self.loginFailed = False

	def _refreshStatesFromHardware(self, dev, logRefresh, commJustStarted):

		emaId = dev.pluginProps["emaId"]
		self.debugLog(u"Getting data for device: %s" % emaId)

		device = Ema.refreshData(self.Ema,emaId)

		try: self.updateStateOnServer(dev, "PowerCurrent", device.current)
		except: self.de (dev, "PowerCurrent")
		try: self.updateStateOnServer(dev, "EnergyDay", device.day)
		except: self.de (dev, "EnergyDay")
		try: self.updateStateOnServer(dev, "EnergyMonth", device.month)
		except: self.de (dev, "EnergyMonth")
		try: self.updateStateOnServer(dev, "EnergyYear", device.year)
		except: self.de (dev, "EnergyYear")
		

	def updateStateOnServer(self, dev, state, value):
		if dev.states[state] != value:
			self.debugLog(u"Updating Device: %s, State: %s, Value: %s" % (dev.name, state, value))
			dev.updateStateOnServer(state, value)

	def de (self, dev, value):
		self.errorLog ("[%s] No value found for device: %s, field: %s" % (time.asctime(), dev.name, value))

		########################################
	def startup(self):
		self.debugLog(u"Ema startup called")
		self.debug = self.pluginPrefs.get('showDebugInLog', False)

		self.updater = GitHubPluginUpdater(self)
		self.updater.checkForUpdate()
		self.updateFrequency = float(self.pluginPrefs.get('updateFrequency', 24)) * 60.0 * 60.0
		self.debugLog(u"updateFrequency = " + str(self.updateFrequency))
		self.next_update_check = time.time()
		self.login(False)

	def login(self, force):
		if self.Ema.startup(force) == False:
			indigo.server.log(u"Login to EMA site failed.  Canceling processing!", isError=True)
			self.loginFailed = True
			return
		else:
			self.loginFailed = False

		self.buildAvailableDeviceList()

	def shutdown(self):
		self.debugLog(u"shutdown called")

	########################################
	def runConcurrentThread(self):
		try:
			while True:
				if self.loginFailed == False:
					if (self.updateFrequency > 0.0) and (time.time() > self.next_update_check):
						self.next_update_check = time.time() + self.updateFrequency
						self.updater.checkForUpdate()

					for dev in indigo.devices.iter("self"):
						if not dev.enabled:
							continue

						self._refreshStatesFromHardware(dev, False, False)

				self.debugLog("Sleep interval: %s" % self.updateFrequency)
				self.sleep(self.updateFrequency)
		except self.StopThread:
			pass	# Optionally catch the StopThread exception and do any needed cleanup.

	########################################
	def validateDeviceConfigUi(self, valuesDict, typeId, devId):
		indigo.server.log(u"validateDeviceConfigUi \"%s\"" % (valuesDict))
		return (True, valuesDict)

	def validatePrefsConfigUi(self, valuesDict):
		self.debugLog(u"Vaidating Plugin Configuration")
		errorsDict = indigo.Dict()
		if len(errorsDict) > 0:
			self.errorLog(u"\t Validation Errors")
			return (False, valuesDict, errorsDict)
		else:
			self.debugLog(u"\t Validation Succesful")
			return (True, valuesDict)
		return (True, valuesDict)

	########################################
	def deviceStartComm(self, dev):
		if self.loginFailed == True:
			return
		self.initDevice(dev)

		dev.stateListOrDisplayStateIdChanged()
		#self._refreshStatesFromHardware(dev, True, True)

	def deviceStopComm(self, dev):
		# Called when communication with the hardware should be shutdown.
		pass

	def closedPrefsConfigUi(self, valuesDict, userCancelled):
		if not userCancelled:
			#Check if Debugging is set
			try:
				self.debug = self.pluginPrefs[u'showDebugInLog']
			except:
				self.debug = False

			try:
				if (self.UserID != self.pluginPrefs["UserID"]) or \
					(self.Password != self.pluginPrefs["Password"]):
					indigo.server.log("[%s] Replacting Username/Password." % time.asctime())
					self.UserID = self.pluginPrefs["UserID"]
					self.Password = self.pluginPrefs["Password"]
			except:
				pass

			indigo.server.log("[%s] Processed plugin preferences." % time.asctime())
			self.login(True)
			return True
	def validateDeviceConfigUi(self, valuesDict, typeId, devId):
		self.debugLog(u"validateDeviceConfigUi called with valuesDict: %s" % str(valuesDict))
		# Set the address
		valuesDict["ShowCoolHeatEquipmentStateUI"] = True
		return (True, valuesDict)

	def initDevice(self, dev):
		new_props = dev.pluginProps
		self.debugLog("Initializing device: %s" % dev.name)

	def buildAvailableDeviceList(self):
		self.debugLog("Building Available Device List")

		self.deviceList = self.Ema.GetDevices()

		indigo.server.log("Number of Ema Devices found: %i" % (len(self.deviceList)))
		for (k, v) in self.deviceList.iteritems():
			indigo.server.log("\tSN: %s" % (v[0]))

	def showAvailableDevices(self):
		indigo.server.log("Number of devices found: %i" % (len(self.deviceList)))
		for (id, details) in self.deviceList.iteritems():
			indigo.server.log("\tSN:%s" % (details[0]))

	def deviceList1(self, filter, valuesDict, typeId, targetId):
		self.debugLog("deviceList called")
		deviceArray = []
		deviceListCopy = deepcopy(self.deviceList)
		for existingDevice in indigo.devices.iter("self"):
			for id in self.deviceList:
		 		self.debugLog("    comparing %s against deviceList item %s" % (existingDevice.pluginProps["emaId"],id))
				if existingDevice.pluginProps["emaId"] == id:
					self.debugLog("    removing item %s" % (id))
					del deviceListCopy[id]
					break

		if len(deviceListCopy) > 0:
			for (id,value) in deviceListCopy.iteritems():
				deviceArray.append((id,value[0]))
		else:
			if len(self.deviceList):
				indigo.server.log("All devices found are already defined")
			else:
				indigo.server.log("No devices were discovered on the network")

		self.debugLog("\tdeviceArray:\n%s" % (str(deviceArray)))
		return deviceArray

	def deviceSelectionChanged(self, valuesDict, typeId, devId):
		self.debugLog("deviceSelectionChanged")

		if valuesDict["device"] in self.deviceList:
			selectedDeviceData = self.deviceList[valuesDict["device"]]
			valuesDict["address"] = valuesDict["device"]
			valuesDict["emaId"] = valuesDict["device"]
		self.debugLog("\tdeviceSelectionChanged valuesDict to be returned:\n%s" % (str(valuesDict)))
		return valuesDict

	def checkForUpdates(self):
		self.updater.checkForUpdate()

	def updatePlugin(self):
		self.updater.update()

	def forceUpdate(self):
		self.updater.update(currentVersion='0.0.0')
