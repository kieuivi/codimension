#
# -*- coding: utf-8 -*-
#
# codimension - graphics python two-way code editor and analyzer
# Copyright (C) 2010-2016  Sergey Satskiy <sergey.satskiy@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#


""" codimension project """

import logging
import uuid
import re
import copy
import json
import shutil
import os
from os.path import realpath, islink, isdir, sep, exists, dirname, isabs, join
from PyQt5.QtCore import QObject, pyqtSignal
from .runparamscache import RunParametersCache
from .settings import Settings, settingsDir
from .watcher import Watcher
from .config import DEFAULT_ENCODING
from .debugenv import DebuggerEnvironment
from .searchenv import SearchEnvironment
from .fsenv import FileSystemEnvironment


# Saved in .cdm3 file
__DEFAULT_PROJECT_PROPS = {'scriptname': '',    # Script to run the project
                           'creationdate': '',
                           'author': '',
                           'license': '',
                           'copyright': '',
                           'version': '',
                           'email': '',
                           'description': '',
                           'uuid': '',
                           'importdirs': []}



class CodimensionProject(QObject,
                         DebuggerEnvironment, SearchEnvironment,
                         FileSystemEnvironment):
    " Provides codimension project singleton facility "

    # Constants for the projectChanged signal
    CompleteProject = 0     # It is a completely new project
    Properties = 1          # Project properties were updated

    projectChanged = pyqtSignal(int)
    fsChanged = pyqtSignal(list)
    restoreProjectExpandedDirs = pyqtSignal()
    projectAboutToUnload = pyqtSignal()
    recentFilesChanged = pyqtSignal()

    def __init__(self):
        QObject.__init__(self)
        DebuggerEnvironment.__init__(self)
        SearchEnvironment.__init__(self)
        FileSystemEnvironment.__init__(self)

        self.__dirWatcher = None

        # Avoid pylint complains
        self.fileName = ""
        self.userProjectDir = ""    # Directory in ~/.codimension/uuidNN/
        self.filesList = set()

        self.props = copy.deepcopy(__DEFAULT_PROJECT_PROPS)

        # Coming from separate files from ~/.codimension/uuidN/
        self.runParamsCache = RunParametersCache()

        # Precompile the exclude filters for the project files list
        self.__excludeFilter = []
        for flt in Settings().projectFilesFilters:
            self.__excludeFilter.append(re.compile(flt))
        return

    def shouldExclude(self, name):
        " Tests if a file must be excluded "
        for excl in self.__excludeFilter:
            if excl.match(name):
                return True
        return False

    def __resetValues(self):
        """ Initializes or resets all the project members """

        # Empty file name means that the project has not been loaded or
        # created. This must be an absolute path.
        self.fileName = ""
        self.userProjectDir = ""

        # Generated having the project dir Full paths are stored.
        # The set holds all files and directories. The dirs end with os.path.sep
        self.filesList = set()

        self.props = copy.deepcopy(__DEFAULT_PROJECT_PROPS)

        # Coming from separate files from ~/.codimension/uuidN/
        self.runParamsCache = RunParametersCache()

        DebuggerEnvironment.reset(self)
        SearchEnvironment.reset(self)
        FileSystemEnvironment.reset(self)

        # Reset the dir watchers if so
        if self.__dirWatcher is not None:
            del self.__dirWatcher
        self.__dirWatcher = None
        return

    def createNew(self, fileName, props):
        " Creates a new project "

        # Try to create the user project directory
        projectUuid = str(uuid.uuid1())
        userProjectDir = settingsDir + projectUuid + sep
        if not exists(userProjectDir):
            try:
                os.makedirs(userProjectDir)
            except Exception:
                logging.error('Cannot create user project directory: ' +
                              self.userProjectDir + '. Please check the '
                              'available disk space, permissions and '
                              're-create the project.')
                raise
        else:
            logging.warning('The user project directory exists! '
                            'The content will be overwritten.')
            self.__removeProjectFiles(userProjectDir)

        # Basic pre-requisites are met. We can reset the current project.
        self.__resetValues()

        self.fileName = fileName
        self.props = props
        self.userProjectDir = userProjectDir

        self.__createProjectFile()  # ~/.codimension/uuidNN/project
        DebuggerEnvironment.setup(self, self.userProjectDir)
        SearchEnvironment.setup(self, self.userProjectDir)
        FileSystemEnvironment.setup(self, self.userProjectDir)

        self.__generateFilesList()

        self.saveProject()

        # Update the watcher
        self.__dirWatcher = Watcher(Settings().projectFilesFilters,
                                    self.getProjectDir())
        self.__dirWatcher.fsChanged.connect(self.onFSChanged)

        self.projectChanged.emit(self.CompleteProject)
        return

    def __removeProjectFiles(self, userProjectDir):
        " Removes user project files "

        for root, dirs, files in os.walk(userProjectDir):
            for f in files:
                try:
                    os.unlink(join(root, f))
                except Exception:
                    pass
            for d in dirs:
                try:
                    shutil.rmtree(join(root, d))
                except Exception:
                    pass
        return

    def __createProjectFile(self):
        " Helper function to create the user project file "
        try:
            with open(self.userProjectDir + 'project', 'w',
                      encoding=DEFAULT_ENCODING) as diskfile:
                diskfile.write(self.fileName)
        except Exception as exc:
            logging.error('Could not create the ' + self.userProjectDir +
                          'project file: ' + str(exc))
            return

    def saveProject(self):
        " Writes all the settings into the file "
        if not self.isLoaded():
            return

        # It could be another user project file without write permissions
        skipProjectFile = False
        if exists(self.fileName):
            if not os.access(self.fileName, os.W_OK):
                skipProjectFile = True
        else:
            if not os.access(dirname(self.fileName), os.W_OK):
                skipProjectFile = True

        if not skipProjectFile:
            with open(self.fileName, 'w',
                      encoding=DEFAULT_ENCODING) as diskfile:
                json.dump(self.props, diskfile, indent=4)
        else:
            logging.warning('Skipping updates in ' + self.fileName +
                            ' due to writing permissions')

        self.serializeRunParameters()
        self.__saveTopLevelDirs()

        return

    def serializeRunParameters(self):
        " Saves the run parameters cache "
        self.runParamsCache.serialize(self.userProjectDir + "runparamscache")
        return

    @staticmethod
    def __save(fileName, values, errorWhat):
        " Saves the general settings "
        try:
            with open(fileName, 'w', encoding=DEFAULT_ENCODING) as diskfile:
                json.dump(values, diskfile, indent=4)
        except Exception as exc:
            logging.error('Error saving ' + errorWhat + ': ' + str(exc))
        return

    def loadProject(self, projectFile):
        """ Loads a project from the given file """

        path = realpath(projectFile)
        if not exists(path):
            raise Exception('Cannot open project file ' + projectFile)
        if not path.endswith('.cdm3'):
            raise Exception('Unexpected project file extension. '
                            'Expected: .cdm3')

        try:
            with open(path, 'r', encoding=DEFAULT_ENCODING) as diskfile:
                props = json.load(diskfile)
        except:
            # Bad error - cannot load project file at all
            raise Exception('Bad project file ' + projectFile)

        self.__resetValues()
        self.fileName = path
        self.props = props

        if self.props['uuid'] == '':
            logging.warning('Project file does not have UUID. '
                            'Re-generate it...')
            self.props['uuid'] = str(uuid.uuid1())
        self.userProjectDir = settingsDir + self.props['uuid'] + sep
        if not exists(self.userProjectDir):
            os.makedirs(self.userProjectDir)

        # Read the other config files
        DebuggerEnvironment.setup(self, self.userProjectDir)
        SearchEnvironment.setup(self, self.userProjectDir)
        FileSystemEnvironment.setup(self, self.userProjectDir)

        self.__loadTopLevelDirs()
        self.__loadProjectBrowserExpandedDirs()

        # The project might have been moved...
        self.__createProjectFile()  # ~/.codimension/uuidNN/project
        self.__generateFilesList()

        if exists(self.userProjectDir + 'runparamscache'):
            self.runParamsCache.deserialize(self.userProjectDir +
                                            'runparamscache')

        # Update the recent list
        Settings().addRecentProject(self.fileName)

        # Setup the new watcher
        self.__dirWatcher = Watcher(Settings().projectFilesFilters,
                                    self.getProjectDir())
        self.__dirWatcher.fsChanged.connect(self.onFSChanged)

        self.projectChanged.emit(self.CompleteProject)
        self.restoreProjectExpandedDirs.emit()
        return

    def getImportDirsAsAbsolutePaths(self):
        " Provides a list of import dirs as absolute paths "
        result = []
        for path in self.importDirs:
            if isabs(path):
                result.append(path)
            else:
                result.append(self.getProjectDir() + path)
        return result

    def onFSChanged(self, items):
        " Triggered when the watcher detects changes "
        for item in items:
            try:
                if item.startswith('+'):
                    self.filesList.add(item[1:])
                else:
                    self.filesList.remove(item[1:])
            except:
                pass
        self.fsChanged.emit(items)
        return

    @staticmethod
    def __loadValuesFromFile(fileName, errorWhat, defaultValue):
        " Generic value loading "
        try:
            with open(fileName, 'r',
                      encoding=DEFAULT_ENCODING) as diskfile:
                return json.load(diskfile)
        except Exception as exc:
            logging.error('Error loading ' + errorWhat + ': ' + str(exc))
            return defaultValue

    def unloadProject(self, emitSignal=True):
        """ Unloads the current project if required """
        self.projectAboutToUnload.emit()
        if self.isLoaded():
            self.__saveProjectBrowserExpandedDirs()
        self.__resetValues()
        if emitSignal:
            # No need to send a signal e.g. if IDE is closing
            self.projectChanged.emit(self.CompleteProject)
        return

    def setImportDirs(self, paths):
        " Sets a new set of the project import dirs "
        if self.props['importdirs'] != paths:
            self.props['importdirs'] = paths
            self.saveProject()
            self.projectChanged.emit(self.Properties)
        return

    def __generateFilesList(self):
        """ Generates the files list having the list of dirs """
        self.filesList = set()
        path = self.getProjectDir()
        self.filesList.add(path)
        self.__scanDir(path)
        return

    def __scanDir(self, path):
        """ Recursive function to scan one dir """
        # The path is with '/' at the end
        for item in os.listdir(path):
            if self.shouldExclude(item):
                continue

            # Exclude symlinks if they point to the other project
            # covered pieces
            candidate = path + item
            if islink(candidate):
                realItem = realpath(candidate)
                if isdir(realItem):
                    if self.isProjectDir(realItem):
                        continue
                else:
                    if self.isProjectDir(dirname(realItem)):
                        continue

            if isdir(candidate):
                self.filesList.add(candidate + sep)
                self.__scanDir(candidate + sep)
                continue
            self.filesList.add(candidate)
        return

    def isProjectDir(self, path):
        " Returns True if the path belongs to the project "
        if not self.isLoaded():
            return False
        path = realpath(path)     # it could be a symlink
        if not path.endswith(sep):
            path += sep
        return path.startswith(self.getProjectDir())

    def isProjectFile(self, path):
        " Returns True if the path belongs to the project "
        if not self.isLoaded():
            return False
        return self.isProjectDir(dirname(path))

    def isTopLevelDir(self, path):
        " Checks if the path is a top level dir "
        if not path.endswith(sep):
            path += sep
        return path in self.topLevelDirs

    def updateProperties(self, props):
        " Updates the project properties "
        if self.props != props:
            self.props = props
            self.saveProject()
            self.projectChanged.emit(self.Properties)
        return

    def onProjectFileUpdated(self):
        " Called when a project file is updated via direct editing "
        self.props = getProjectProperties(self.fileName)

        # no need to save, but signal just in case
        self.projectChanged.emit(self.Properties)
        return

    def isLoaded(self):
        " returns True if a project is loaded "
        return self.fileName != ''

    def getProjectDir(self):
        " Provides an absolute path to the project dir "
        if not self.isLoaded():
            return None
        return dirname(realpath(self.fileName)) + sep

    def getProjectScript(self):
        " Provides the project script file name "
        if not self.isLoaded():
            return None
        if self.scriptName == '':
            return None
        if isabs(self.scriptName):
            return self.scriptName
        return realpath(self.getProjectDir() + self.scriptName)

    def addRecentFile(self, path):
        " Adds a single recent file. True if a new file was inserted. "
        ret = FileSystemEnvironment.addRecentFile(self, path)
        if ret:
            self.recentFilesChanged.emit()
        return ret


def getProjectProperties(projectFile):
    """ Provides project properties or throws an exception """

    path = realpath(projectFile)
    if not exists(path):
        raise Exception("Cannot find project file " + projectFile)

    try:
        with open(path, 'r', encoding=DEFAULT_ENCODING) as diskfile:
            return json.load(diskfile)
    except Exception as exc:
        logging.error('Error reading project file ' + projectFile +
                      ': ' + str(exc))
        return {}


def getProjectFileTooltip(fileName):
    " Provides a project file tooltip "
    props = getProjectProperties(fileName)
    return '\n'.join(['Version: ' + props.get('version', 'n/a'),
                      'Description: ' + props.get('description', 'n/a'),
                      'Author: ' + props.get('author', 'n/a'),
                      'e-mail: ' + props.get('email', 'n/a'),
                      'Copyright: ' + props.get('copyright', 'n/a'),
                      'License: ' + props.get('license', 'n/a'),
                      'Creation date: ' + props.get('creationdate', 'n/a'),
                      'UUID: ' + props.get('uuid', 'n/a')])
