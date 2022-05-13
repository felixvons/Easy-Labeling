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

from qgis.core import (QgsCoordinateReferenceSystem, QgsDistanceArea,
                       QgsProject)


def get_distance_area(crs: QgsCoordinateReferenceSystem, ellipsoid: str = "WGS84") -> QgsDistanceArea:
    """ Gets distance are object for calculating length in meters.

        .. code-block:: python

            distance = get_distance_area(layer.dataProvider().crs())
            print("measured feature length in meters", distance.measureLength(feature.geometry()))

        :param crs: coordinate reference system
        :param ellipsoid: ellipsoid name, keep empty when using from crs
        :return: distance area object
        :rtype: QgsDistanceArea
    """

    dist_area = QgsDistanceArea()
    crs = QgsCoordinateReferenceSystem(crs)
    dist_area.setSourceCrs(crs, QgsProject.instance().transformContext())
    dist_area.setEllipsoid(ellipsoid if ellipsoid else crs.ellipsoidAcronym())

    return dist_area
