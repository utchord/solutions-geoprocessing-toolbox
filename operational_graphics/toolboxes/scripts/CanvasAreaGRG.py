# coding: utf-8
#------------------------------------------------------------------------------
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
#------------------------------------------------------------------------------
#
# ==================================================
# CanvasAreaGRG.py
# --------------------------------------------------
# Built on ArcGIS 10.?
# ==================================================
#
# Creates a Gridded Reference Graphic
#
#
# ==================================================
# HISTORY:
#
# 8/24/2015 - mf - Needed to update script for non-ArcMap/Pro testing environment
#
# ==================================================

import os, sys, math, traceback, inspect
import arcpy
from arcpy import env
import Utilities

# Read in the parameters
templateExtent = arcpy.GetParameterAsText(0)
cellWidth = arcpy.GetParameterAsText(1)
cellHeight = arcpy.GetParameterAsText(2)
cellUnits = arcpy.GetParameterAsText(3)
gridSize = arcpy.GetParameterAsText(4)
labelStyle = arcpy.GetParameterAsText(5)
outputFeatureClass = arcpy.GetParameterAsText(6)
labelStartPos = arcpy.GetParameterAsText(7)
tempOutput = os.path.join("in_memory", "tempFishnetGrid")
sysPath = sys.path[0]

DEBUG = True
# GLOBALS
appEnvironment = None
mxd = None
df = None
aprx = None
mapList = None

def RotateFeatureClass(inputFC, outputFC,
                       angle=0, pivot_point=None):
    """Rotate Feature Class

    inputFC     Input features
    outputFC    Output feature class
    angle       Angle to rotate, in degrees
    pivot_point X,Y coordinates (as space-separated string)
                Default is lower-left of inputFC

    As the output feature class no longer has a "real" xy locations,
    after rotation, it no coordinate system defined.
    """

    def RotateXY(x, y, xc=0, yc=0, angle=0, units="DEGREES"):
        """Rotate an xy cooordinate about a specified origin

        x,y      xy coordinates
        xc,yc   center of rotation
        angle   angle
        units    "DEGREES" (default) or "RADIANS"
        """
        import math
        x = x - xc
        y = y - yc
        # make angle clockwise (like Rotate_management)
        angle = angle * -1
        if units == "DEGREES":
            angle = math.radians(angle)
        xr = (x * math.cos(angle)) - (y * math.sin(angle)) + xc
        yr = (x * math.sin(angle)) + (y * math.cos(angle)) + yc
        return xr, yr

    # temp names for cleanup
    env_file = None
    lyrFC, lyrTmp, lyrOut   = [None] * 3  # layers
    tmpFC  = None # temp dataset
    Row, Rows, oRow, oRows = [None] * 4 # cursors

    try:
        # process parameters
        try:
            xcen, ycen = [float(xy) for xy in pivot_point.split()]
            pivot_point = xcen, ycen
        except:
            # if pivot point was not specified, get it from
            # the lower-left corner of the feature class
            ext = arcpy.Describe(inputFC).extent
            xcen, ycen  = ext.XMin, ext.YMin
            pivot_point = xcen, ycen

        angle = float(angle)

        # set up environment
        env_file = arcpy.CreateScratchName("xxenv",".xml","file",
                                           os.environ["TEMP"])
        arcpy.SaveSettings(env_file)

        # Disable any GP environment clips or project on the fly
        arcpy.ClearEnvironment("extent")
        arcpy.ClearEnvironment("outputCoordinateSystem")
        WKS = env.workspace
        if not WKS:
            if os.path.dirname(outputFC):
                WKS = os.path.dirname(outputFC)
            else:
                WKS = os.path.dirname(
                    arcpy.Describe(inputFC).catalogPath)
        env.workspace = env.scratchWorkspace = WKS

        # Disable GP environment clips or project on the fly
        arcpy.ClearEnvironment("extent")
        arcpy.ClearEnvironment("outputCoordinateSystem")

        # get feature class properties
        lyrFC = "lyrFC"
        arcpy.MakeFeatureLayer_management(inputFC, lyrFC)
        dFC = arcpy.Describe(lyrFC)
        shpField = dFC.shapeFieldName
        shpType = dFC.shapeType
        FID = dFC.OIDFieldName

        # create temp feature class
        tmpFC = arcpy.CreateScratchName("xxfc","","featureclass")
        arcpy.CreateFeatureclass_management(os.path.dirname(tmpFC),
                                            os.path.basename(tmpFC),
                                            shpType)
        lyrTmp = "lyrTmp"
        arcpy.MakeFeatureLayer_management(tmpFC, lyrTmp)

        # set up id field (used to join later)
        TFID = "XXXX_FID"
        arcpy.AddField_management(lyrTmp, TFID, "LONG")
        arcpy.DeleteField_management(lyrTmp, "ID")

        # rotate the feature class coordinates
        # only points, polylines, and polygons are supported

        # open read and write cursors
        Rows = arcpy.SearchCursor(lyrFC, "", "",
                                  "%s;%s" % (shpField,FID))
        oRows = arcpy.InsertCursor(lyrTmp)
        if shpType  == "Point":
            for Row in Rows:
                shp = Row.getValue(shpField)
                pnt = shp.getPart()
                pnt.X, pnt.Y = RotateXY(pnt.X,pnt.Y,xcen,ycen,angle)
                oRow = oRows.newRow()
                oRow.setValue(shpField, pnt)
                oRow.setValue(TFID,Row.getValue(FID))
                oRows.insertRow(oRow)
        elif shpType in ["Polyline","Polygon"]:
            parts = arcpy.Array()
            rings = arcpy.Array()
            ring = arcpy.Array()
            for Row in Rows:
                shp = Row.getValue(shpField)
                p = 0
                for part in shp:
                    for pnt in part:
                        if pnt:
                            x, y = RotateXY(pnt.X, pnt.Y, xcen, ycen, angle)
                            ring.add(arcpy.Point(x, y, pnt.ID))
                        else:
                            # if we have a ring, save it
                            if len(ring) > 0:
                                rings.add(ring)
                                ring.removeAll()
                    # we have our last ring, add it
                    rings.add(ring)
                    ring.removeAll()
                    # if only one, remove nesting
                    if len(rings) == 1: rings = rings.getObject(0)
                    parts.add(rings)
                    rings.removeAll()
                    p += 1

                # if only one, remove nesting
                if len(parts) == 1: parts = parts.getObject(0)
                if dFC.shapeType == "Polyline":
                    shp = arcpy.Polyline(parts)
                else:
                    shp = arcpy.Polygon(parts)
                parts.removeAll()
                oRow = oRows.newRow()
                oRow.setValue(shpField, shp)
                oRow.setValue(TFID,Row.getValue(FID))
                oRows.insertRow(oRow)
        else:
            #raise Exception, "Shape type {0} is not supported".format(shpType) #UPDATE
            raise Exception("Shape type {0} is not supported".format(shpType))

        del oRow, oRows # close write cursor (ensure buffer written)
        oRow, oRows = None, None # restore variables for cleanup

        # join attributes, and copy to output
        arcpy.AddJoin_management(lyrTmp, TFID, lyrFC, FID)
        env.qualifiedFieldNames = False
        arcpy.Merge_management(lyrTmp, outputFC)
        lyrOut = "lyrOut"
        arcpy.MakeFeatureLayer_management(outputFC, lyrOut)
        # drop temp fields 2,3 (TFID, FID)
        fnames = [f.name for f in arcpy.ListFields(lyrOut)]
        dropList = ";".join(fnames[2:4])
        arcpy.DeleteField_management(lyrOut, dropList)

    #except MsgError, xmsg: #UPDATE
    except MsgError as xmsg:
        arcpy.AddError(str(xmsg))
    except arcpy.ExecuteError:
        tbinfo = traceback.format_tb(sys.exc_info()[2])[0]
        arcpy.AddError(tbinfo.strip())
        arcpy.AddError(arcpy.GetMessages())
        numMsg = arcpy.GetMessageCount()
        for i in range(0, numMsg):
            arcpy.AddReturnMessage(i)
    #except Exception, xmsg: #UPDATE
    except Exception as xmsg:
        tbinfo = traceback.format_tb(sys.exc_info()[2])[0]
        arcpy.AddError(tbinfo + str(xmsg))
    finally:
        # reset environment
        if env_file: arcpy.LoadSettings(env_file)
        # Clean up temp files
        for f in [lyrFC, lyrTmp, lyrOut, tmpFC, env_file]:
            try:
                if f: arcpy.Delete_management(f)
            except:
                pass
        # delete cursors
        try:
            for c in [Row, Rows, oRow, oRows]: del c
        except:
            pass

        # return pivot point
        try:
            pivot_point = "{0} {1}".format(*pivot_point)
        except:
            pivot_point = None

        return pivot_point

def labelFeatures(layer, field):
    ''' set up labeling for layer '''
    if appEnvironment == "ARCGIS_PRO":
        if layer.supports("SHOWLABELS"):
            for lblclass in layer.listLabelClasses():
                lblclass.visible = True
                lblclass.expression = " [" + str(field) + "]"
            layer.showLabels = True
    elif appEnvironment == "ARCMAP":
        if layer.supports("LABELCLASSES"):
            for lblclass in layer.labelClasses:
                lblclass.showClassLabels = True
                lblclass.expression = " [" + str(field) + "]"
            layer.showLabels = True
            arcpy.RefreshActiveView()
    else:
        pass # if returns "OTHER"

def findLayerByName(layerName):
    '''  '''
    global mapList
    global mxd
    #UPDATE
    #if isPro: #Update for automated test
    if appEnvironment == "ARCGIS_PRO":
        for layer in mapList.listLayers():
            if layer.name == layerName:
                arcpy.AddMessage("Found matching layer [" + layer.name + "]")
                return layer
            else:
                arcpy.AddMessage("Incorrect layer: [" + layer.name + "]")
    #else: #Update for automated test
    elif appEnvironment == "ARCMAP":
        for layer in arcpy.mapping.ListLayers(mxd):
            if layer.name == layerName:
                arcpy.AddMessage("Found matching layer [" + layer.name + "]")
                return layer
            else:
                arcpy.AddMessage("Incorrect layer: [" + layer.name + "]")
    else:
        arcpy.AddWarning("Non-map environment")

def ColIdxToXlName(index):
    ''' Converts an index into a letter, labeled like excel columns, A to Z, AA to ZZ, etc. '''
    if index < 1:
        raise ValueError("Index is too small")
    result = ""
    while True:
        if index > 26:
            index, r = divmod(index - 1, 26)
            result = chr(r + ord('A')) + result
        else:
            return chr(index + ord('A') - 1) + result

def CalculatePointDistance(firstPoint, secondPoint):
    ''' Calculates distance between two points '''
    return math.sqrt(math.pow((firstPoint.X - secondPoint.X),2) + math.pow((firstPoint.Y - secondPoint.Y),2))

def main():
    ''' Main tool method '''
    try:
        #UPDATE
        gisVersion = arcpy.GetInstallInfo()["Version"]
        global appEnvironment
        appEnvironment = Utilities.GetApplication()
        if DEBUG == True: arcpy.AddMessage("App environment: " + appEnvironment)
        global mxd
        global df
        global aprx
        global mapList
        #mxd, df, aprx, mapList = None, None, None, None
        isPro = False

        #if gisVersion == "1.0": #Pro: #Update for automated test
        if appEnvironment == "ARCGIS_PRO":
            from arcpy import mp
            aprx = arcpy.mp.ArcGISProject("CURRENT")
            mapList = aprx.listMaps()[0]
            isPro = True
        #else: #Update for automated test
        if appEnvironment == "ARCMAP":
            from arcpy import mapping
            mxd = arcpy.mapping.MapDocument('CURRENT')
            df = arcpy.mapping.ListDataFrames(mxd)[0]
            isPro = False

        # From the template extent, get the origin, y axis, and opposite corner corrdinates
        if DEBUG == True: arcpy.AddMessage("Getting extent info...")
        extents = str.split(str(templateExtent))
        originCoordinate = extents[0] + " " + extents[1]
        yAxisCoordinate = extents[0] + " " + extents[1]
        oppCornerCoordinate = extents[2] + " " + extents[3]
        centerPoint = str((float(extents[0]) + float(extents[2]))/2.0) + " " + str((float(extents[1]) + float(extents[3]))/2.0)

        # If grid size is drawn on the map, use this instead of cell width and cell height
        inputExtentDrawnFromMap = False
        angleDrawn = 0
        workspace = arcpy.env.workspace
        global cellWidth
        global cellHeight
        if float(cellWidth) == 0 and float(cellHeight) == 0:
            if DEBUG == True: arcpy.AddMessage("Cell extent from features...")
            inputExtentDrawnFromMap = True
            tempGridFC = os.path.join(arcpy.env.scratchWorkspace, "GridSize")
            arcpy.CopyFeatures_management(gridSize, tempGridFC)
            pts = None
            with arcpy.da.SearchCursor(tempGridFC, 'SHAPE@XY', explode_to_points=True) as cursor:
                pts = [r[0] for r in cursor][0:4]
            arcpy.Delete_management(tempGridFC)

            cellWidth = math.sqrt((pts[0][0] - pts[1][0]) ** 2 + (pts[0][1] - pts[1][1]) ** 2)
            cellHeight = math.sqrt((pts[1][0] - pts[2][0]) ** 2 + (pts[1][1] - pts[2][1]) ** 2)
            highestPoint = None
            nextHighestPoint = None
            for pt in pts:
                if highestPoint is None or pt[1] > highestPoint[1]:
                    nextHighestPoint = highestPoint
                    highestPoint = pt
                elif nextHighestPoint is None or pt[1] > nextHighestPoint[1]:
                    nextHighestPoint = pt

            topLeft = highestPoint if highestPoint[0] < nextHighestPoint[0] else nextHighestPoint
            topRight = highestPoint if highestPoint[0] > nextHighestPoint[0] else nextHighestPoint
            yDiff = topRight[1] - topLeft[1]
            xDiff = topRight[0] - topLeft[0]

            # Calculate angle
            hypotenuse = math.sqrt(math.pow(topLeft[0] - topRight[0], 2) + math.pow(topLeft[1] - topRight[1], 2))
            adjacent = topRight[0] - topLeft[0]
            numberToCos = float(adjacent)/float(hypotenuse)
            angleInRadians = math.acos(numberToCos)
            angleDrawn = math.degrees(angleInRadians)
            if (topRight[1] > topLeft[1]):
                angleDrawn = 360 - angleDrawn
        else:
            if DEBUG == True:
                arcpy.AddMessage("Cell extent from (" + str(cellWidth) + "," + str(cellHeight) + ")")
            if (cellUnits == "Feet"):
                cellWidth = float(cellWidth) * 0.3048
                cellHeight = float(cellHeight) * 0.3048

        # Set the start position for labeling
        startPos = None
        if (labelStartPos == "Upper-Right"):
            startPos = "UR"
        elif (labelStartPos == "Upper-Left"):
            startPos = "UL"
        elif (labelStartPos == "Lower-Left"):
            startPos = "LL"
        elif (labelStartPos == "Lower-Right"):
            startPos = "LR"

        # Import the custom toolbox with the fishnet tool in it, and run this. This had to be added to a model.
        # because of a bug, which will now allow you to pass variables to the Create Fishnet tool.
        #UPDATE
        toolboxPath = None
        if appEnvironment == "ARCGIS_PRO":
            toolboxPath = os.path.join(os.path.dirname(sysPath), "Clearing Operations Tools.tbx")
        else:
            toolboxPath = os.path.join(os.path.dirname(sysPath), "Clearing Operations Tools_10.4.tbx")

        arcpy.ImportToolbox(toolboxPath)
        arcpy.AddMessage("Creating Fishnet Grid...")
        arcpy.Fishnet_ClearingOperations(tempOutput, originCoordinate, yAxisCoordinate, str(cellWidth), str(cellHeight), 0, 0, oppCornerCoordinate, "NO_LABELS", templateExtent, "POLYGON")

        # Sort the grid upper left to lower right, and delete the in memory one
        arcpy.AddMessage("Sorting the grid for labeling")
        tempSort = os.path.join("in_memory","tempSort")
        arcpy.Sort_management(tempOutput, tempSort, [["Shape", "ASCENDING"]], startPos)
        #arcpy.Delete_management("in_memory") # Not sure why we are deleteing in_memory

        # Add a field which will be used to add the grid labels
        arcpy.AddMessage("Adding field for labeling the grid")
        gridField = "Grid"
        arcpy.AddField_management(tempSort, gridField, "TEXT")

        # Number the fields
        arcpy.AddMessage("Numbering the grids")
        letterIndex = 1
        secondLetterIndex = 1
        letter = 'A'
        secondLetter = 'A'
        number = 1
        lastY = -9999
        #TODO: update to use DA cursor
        cursor = arcpy.UpdateCursor(tempSort)
        for row in cursor:
            yPoint = row.getValue("SHAPE").firstPoint.Y
            if (lastY != yPoint) and (lastY != -9999):
                letterIndex += 1
                letter = ColIdxToXlName(letterIndex)
                if (labelStyle != "Numeric"):
                    number = 1
                secondLetter = 'A'
                secondLetterIndex = 1
            lastY = yPoint

            if (labelStyle == "Alpha-Numeric"):
                row.setValue(gridField, str(letter) + str(number))
            elif (labelStyle == "Alpha-Alpha"):
                row.setValue(gridField, str(letter) + str(secondLetter))
            elif (labelStyle == "Numeric"):
                row.setValue(gridField, str(number))

            cursor.updateRow(row)
            number += 1
            secondLetterIndex += 1
            secondLetter = ColIdxToXlName(secondLetterIndex)
        del row
        del cursor

        # Rotate the shape, if needed.
        if (inputExtentDrawnFromMap):
            arcpy.AddMessage("Rotating the feature")
            RotateFeatureClass(tempSort, outputFeatureClass, angleDrawn, centerPoint)
        else:
            arcpy.CopyFeatures_management(tempSort, outputFeatureClass)
        arcpy.Delete_management(tempSort)

        # Get and label the output feature
        #TODO: Update once applying symbology in Pro is fixed.
        #UPDATE
        targetLayerName = os.path.basename(outputFeatureClass)
        if appEnvironment == "ARCGIS_PRO":
            results = arcpy.MakeFeatureLayer_management(outputFeatureClass, targetLayerName).getOutput(0)
            mapList.addLayer(results, "AUTO_ARRANGE")
            layer = findLayerByName(targetLayerName)
            if(layer):
                labelFeatures(layer, gridField)
        elif appEnvironment == "ARCMAP":
            layerToAdd = arcpy.mapping.Layer(outputFeatureClass)
            arcpy.mapping.AddLayer(df, layerToAdd, "AUTO_ARRANGE")
            targetLayerName = os.path.basename(outputFeatureClass)
            layer = findLayerByName(targetLayerName)
            if(layer):
                arcpy.AddMessage("Labeling grids")
                labelFeatures(layer, gridField)
        else:
            arcpy.AddMessage("Non-map environment, skipping labeling...")

        # Set tool output
        arcpy.SetParameter(6, outputFeatureClass)

        ### Apply symbology to the GRG layer
        ###UPDATE
        ###symbologyPath = os.path.dirname(workspace) + "\\Layers\GRG.lyr"
        ###arcpy.ApplySymbologyFromLayer_management(layer, symbologyPath)

    except arcpy.ExecuteError: 
        # Get the tool error messages
        msgs = arcpy.GetMessages()
        arcpy.AddError(msgs)
        print(msgs)

    except:
        # Get the traceback object
        tb = sys.exc_info()[2]
        tbinfo = traceback.format_tb(tb)[0]

        # Concatenate information together concerning the error into a message string
        pymsg = "PYTHON ERRORS:\nTraceback info:\n" + tbinfo + "\nError Info:\n" + str(sys.exc_info()[1])
        msgs = "ArcPy ERRORS:\n" + arcpy.GetMessages() + "\n"

        # Return python error messages for use in script tool or Python Window
        arcpy.AddError(pymsg)
        arcpy.AddError(msgs)
    
        # Print Python error messages for use in Python / Python Window
        print(pymsg + "\n")
        print(msgs)

# MAIN =============================================
if __name__ == "__main__":
    main()
