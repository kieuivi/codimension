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

" Provides the storage for the file system environment "

import os.path
from copy import deepcopy
from .fileutils import loadJSON, saveJSON
from .settings import Settings


# toplevel dirs: those which are added to the file system browser
# filebrowserexpandeddirs: dirs in the project browser which were expanded when
# the user closed the project
__DEFAULT_FS_PROPS = {'tabs': [],                       # [bool: active,
                                                        #  string: path, ...]
                      'recent': [],                     # [path, ...]
                      'fsbrowserexpandeddirs': [],      # [path, ...]
                      'topleveldirs': []}               # [path, ...]


class FileSystemEnvironment:
    " Loads/stores/saves the fs related environment "

    def __init__(self):
        self.__props = deepcopy(__DEFAULT_FS_PROPS)
        self.__fileName = None
        self.__limit = Settings()['maxRecentFiles']

    def reset(self):
        " Resets the binding to the file system "
        self.__props = deepcopy(__DEFAULT_FS_PROPS)
        self.__fileName = None

    def setup(self, dirName):
        " Binds the parameters to a disk file "
        # Just in case - flush the previous data if they were bound
        self.save()

        dirName = os.path.realpath(dirName)
        if not dirName.endswith(os.path.sep):
            dirName += os.path.sep
        if not os.path.isdir(dirName):
            raise Exception('Directory name is expected for the file system '
                            'environment. The given ' + dirName + ' is not.')

        self.__fileName = dirName + "fsenv.json"
        if os.path.exists(self.__fileName):
            self.load()

    def load(self):
        " Loads the saved file system environment "
        if self.__fileName:
            default = deepcopy(__DEFAULT_FS_PROPS)
            self.__props = loadJSON(self.__fileName, 'file system environment',
                                    default)

    def save(self):
        " Saves the file system environment into a file "
        if self.__fileName:
            saveJSON(self.__fileName, self.__props, 'file system environment')

    @property
    def tabStatus(self):
        " Provides the opened tabs status "
        return self.__props['tabs']

    @tabStatus.setter
    def tabStatus(self, newStatus):
        self.__props['tabs'] = newStatus
        self.save()

    @property
    def recentFiles(self):
        " Provides the recently used files list "
        return self.__props['recent']

    @recentFiles.setter
    def recentFiles(self, files):
        self.__props['recent'] = files
        self.save()

    def addRecentFile(self, path):
        " Adds a single recent file. True if a new file was inserted. "
        if path in self.__props['recent']:
            self.__props['recent'].remove(path)
            self.__props['recent'].insert(0, path)
            self.save()
            return False
        self.__props['recent'].insert(0, path)
        if len(self.__props['recent']) > self.__limit:
            self.__props['recent'] = self.__props['recent'][0:self.__limit]
        self.save()
        return True

    def removeRecentFile(self, path):
        " Removes a single recent file "
        if path in self.__props['recent']:
            self.__props['recent'].remove(path)
            self.save()

    @property
    def fsBrowserExpandedDirs(self):
        " Provides the file system browser expanded dirs "
        return self.__props['fsbrowserexpandeddirs']

    @fsBrowserExpandedDirs.setter
    def fsBrowserExpandedDirs(self, newDirs):
        self.__props['fsbrowserexpandeddirs'] = newDirs
        self.save()

    @property
    def topLevelDirs(self):
        " Provides a list of dirs in the FS browser "
        return self.__props['topleveldirs']

    @topLevelDirs.setter
    def topLevelDirs(self, newDirs):
        self.__props['topleveldirs'] = newDirs
        self.save()

    def addTopLevelDir(self, path):
        " Adds a top level dir "
        if not path.endswith(os.path.sep):
            path += os.path.sep
        if path not in self.__props['topleveldirs']:
            self.__props['topleveldirs'].append(path)
            self.save()

    def removeTopLevelDir(self, path):
        " Removes a top level dir "
        if not path.endswith(os.path.sep):
            path += os.path.sep
        if path in self.__props['topleveldirs']:
            self.__props['topleveldirs'].remove(path)
            self.save()
