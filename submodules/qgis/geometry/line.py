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

from qgis.core import (QgsPointXY, QgsGeometry,
                       QgsWkbTypes)

from typing import List

from .. import constants


def get_polyline(geometry: QgsGeometry) -> List[QgsPointXY]:
    """ returns first available and valid poly line.
        From multi line geometry the first valid line will be returned!

        :param geometry: line geometry
        :return: found poly line list
    """
    geom_type = QgsWkbTypes.geometryDisplayString(geometry.type())
    assert geometry.type() == QgsWkbTypes.LineGeometry, f"geometry '{geom_type}' is not a line geometry"

    # empty geometry
    if geometry.isEmpty() or geometry.isNull():
        return []

    if geometry.isMultipart():
        multi_poly_lines = geometry.asMultiPolyline()
        if not multi_poly_lines[0]:
            if len(multi_poly_lines) > 1:
                return multi_poly_lines[1]
        return multi_poly_lines[0]
    else:
        return geometry.asPolyline()


def is_point_on_segment(point: QgsPointXY, line: List[QgsPointXY], epsilon: float = constants.EPSILON) -> bool:
    """ checks, if point is between two points with epsilon value

        :param point: point
        :param line: point list
        :param epsilon: tolerance for comparing points, defaults to _constants.EPSILON
        :return: True = point is on "line", otherwise False
    """
    # works only for segments, use is_point_on_line otherwise
    assert len(line) == 2
    # point x is on line (x_1, x_2) exactly if dist(x_1, x) + dist(x,x_2) = dist(x_1,x_2)
    dist1 = point.distance(line[0]) + point.distance(line[1])
    dist2 = line[0].distance(line[1])
    return abs(dist1 - dist2) < epsilon


def is_point_in_polylist(point: QgsPointXY, line: List[QgsPointXY], epsilon: float = constants.EPSILON) -> bool:
    """ checks, if point is on line

        :param point: point
        :param line: point list
        :param epsilon: tolerance for comparing points, defaults to _constants.EPSILON
        :return: True = point is on line-vertex, otherwise False
    """
    for p in line:
        if p.compare(point, epsilon):
            return True
    return False
