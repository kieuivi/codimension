#
# -*- coding: utf-8 -*-
#
# codimension - graphics python two-way code editor and analyzer
# Copyright (C) 2010  Sergey Satskiy <sergey.satskiy@gmail.com>
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
# $Id$
#

" Update interval settings dialog "

from PyQt4.QtCore import Qt, SIGNAL
from PyQt4.QtGui import ( QDialog, QVBoxLayout, QDialogButtonBox,
                          QHBoxLayout, QLabel, QLineEdit, QIntValidator )

UPDATE_INTERVAL_DEFAULT = 30    # in seconds


class VCSUpdateIntervalConfigDialog( QDialog ):
    " Dialog to configure update interval "

    def __init__( self, value, parent = None ):
        QDialog.__init__( self, parent )
        self.interval = value

        self.__createLayout()
        self.setWindowTitle( "VCS file status update interval configuration" )

        self.__intervalEdit.setText( str( self.interval ) )
        self.__updateOKStatus()

        self.connect( self.__intervalEdit,
                      SIGNAL( "textChanged(const QString&)" ),
                      self.__updateOKStatus )
        return

    def __createLayout( self ):
        " Creates the dialog layout "

        self.resize( 640, 150 )
        self.setSizeGripEnabled( True )

        vboxLayout = QVBoxLayout( self )

        hboxLayout = QHBoxLayout()
        hboxLayout.addWidget( QLabel( "Update interval, sec." ) )
        self.__intervalEdit = QLineEdit()
        self.__intervalEdit.setValidator( QIntValidator( 1, 3600, self ) )
        hboxLayout.addWidget( self.__intervalEdit )

        # Buttons at the bottom
        self.__buttonBox = QDialogButtonBox( self )
        self.__buttonBox.setOrientation( Qt.Horizontal )
        self.__buttonBox.setStandardButtons( QDialogButtonBox.Ok |
                                             QDialogButtonBox.Cancel )
        self.connect( self.__buttonBox, SIGNAL( "accepted()" ), self.userAccept )
        self.connect( self.__buttonBox, SIGNAL( "rejected()" ), self.close )

        vboxLayout.addLayout( hboxLayout )
        vboxLayout.addWidget( self.__buttonBox )
        return

    def __updateOKStatus( self ):
        " Updates the OK button status "
        okButton = self.__buttonBox.button( QDialogButtonBox.Ok )

        if str( self.__intervalEdit.text() ) == "":
            okButton.setEnabled( False )
            okButton.setToolTip( "Interval must be defined" )
            return

        okButton.setEnabled( True )
        okButton.setToolTip( "" )
        return

    def userAccept( self ):
        " Triggered when the user clicks OK "
        self.interval = int( str( self.__intervalEdit.text() ) )
        self.accept()
        return
