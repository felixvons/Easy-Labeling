# -*- coding: utf-8 -*-
"""
/***************************************************************************
        copyright            : (C) 2022 Felix von Studsinske
        email                : felix.vons@gmail.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from ..plugin import EasyLabeling


def load_tool_bar(plugin: EasyLabeling):
    """ loads default action for your plugin """
    from qgis.PyQt.QtGui import QIcon

    from ..modules.labeling import LabelingMenu

    icon = QIcon(plugin.get_icon_path("icon.png"))
    plugin.add_action("Easy Labeling öffnen",
                      icon,
                      False,
                      lambda: LabelingMenu.load(plugin),
                      True,
                      plugin.plugin_menu_name,
                      plugin.plugin_menu_name,
                      True,
                      True)
