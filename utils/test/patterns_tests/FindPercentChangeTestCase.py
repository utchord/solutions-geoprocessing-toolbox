# coding: utf-8
# -----------------------------------------------------------------------------
# Copyright 2015 Esri
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# -----------------------------------------------------------------------------

# ==================================================
# FindPercentChangeTestCase.py
# --------------------------------------------------
# requirments: ArcGIS X.X, Python 2.7 or Python 3.4
# author: ArcGIS Solutions
# company: Esri
# ==================================================
# history:
# 12/16/2015 - JH - initial creation
# ==================================================

import unittest
import arcpy
import os
import UnitTestUtilities
import Configuration

class FindPercentChangeTestCase(unittest.TestCase):
    ''' Test all tools and methods related to the Find Percent Change tool
    in the Incident Analysis toolbox'''
    
    
    def setUp(self):
        if Configuration.DEBUG == True: print("     FindPercentChangeTestCase.setUp")
        UnitTestUtilities.checkArcPy()
        UnitTestUtilities.checkFilePaths([Configuration.incidentDataPath, Configuration.incidentInputGDB, Configuration.patterns_ProToolboxPath, Configuration.patterns_DesktopToolboxPath])
        if (Configuration.incidentScratchGDB == None) or (not arcpy.Exists(Configuration.incidentScratchGDB)):
            Configuration.incidentScratchGDB = UnitTestUtilities.createScratch(Configuration.incidentDataPath)
            
    def tearDown(self):
        if Configuration.DEBUG == True: print("     FindPercentChangeTestCase.tearDown")
        UnitTestUtilities.deleteScratch(Configuration.incidentScratchGDB)
        
    def test_percent_change_pro(self):
        if Configuration.DEBUG == True: print("     FindPercentChangeTestCase.test_percent_change_pro")
        arcpy.AddMessage("Testing Find Percent Change (Pro).")
        self.test_percent_change(Configuration.patterns_ProToolboxPath)
        
    def test_percent_change_desktop(self):
        if Configuration.DEBUG == True: print("     FindPercentChangeTestCase.test_percent_change_desktop")
        arcpy.AddMessage("Testing Find Percent Change (Desktop).")
        self.test_percent_change(Configuration.patterns_DesktopToolboxPath)
        
    def test_percent_change(self, toolboxPath):
        try:
            if Configuration.DEBUG == True: print("     FindPercentChangeTestCase.test_percent_change")
                
        except arcpy.ExecuteError:
            UnitTestUtilities.handleArcPyError()
            
        except:
            UnitTestUtilities.handleGeneralError()
            