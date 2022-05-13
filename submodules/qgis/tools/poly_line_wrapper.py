# -*- coding: utf-8 -*-
"""
/***************************************************************************

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

from qgis.core import (QgsPointXY)
from ..geometry.line import is_point_on_segment
from typing import List


class PolylineWrapper:
    """ Eine (Poly-)Linie, die intern aus Segmenten besteht,
        die jeweils nur zwei Punkte enthalten (also Geradenstücke sind).

        :param segment_list: list of poly segments
    """

    def __init__(self, segment_list: List[List[QgsPointXY]]):
        self.segment_list: List[List[QgsPointXY]]
        # Check, ob Listen-Element alle nur zwei Elemente haben (es sollen einfach Segmente sein):
        if len(segment_list) != len([l for l in segment_list if len(l) == 2]):
            raise AttributeError("Segment-Liste darf nur Segmente mit 2 Punkten enthalten:" + str(segment_list))
        for i in range(0, len(segment_list) - 1):
            if segment_list[i][1] != segment_list[i + 1][0]:
                raise AttributeError("Nicht zusammenhängende Linie: " + str(segment_list))
        self.segment_list = segment_list

    def get_distance_on_line(self, point: QgsPointXY) -> float:
        """ Gibt die Entfernung eines Punktes auf der Linie vom Linienanfang entlang der Linie zurück,
            d.h. die Länge des Teilstücks vom Linienanfang bis zu dem übergebenen Punkt.

            :param point: point

            :return: calculated distance along segments
            :rtype: float

        """
        distance: float = 0
        for segment in self.segment_list:
            if not is_point_on_segment(point, segment):
                distance += segment[1].distance(segment[0])
            else:
                distance += point.distance(segment[0])
                return distance

        raise AttributeError("Punkt " + str(point) + " liegt nicht auf Polylinie " + str(self.segment_list))

    def length(self) -> float:
        """ Returns geometry length.

            :return: length of geometry
            :rtype: float
        """
        return self.get_distance_on_line(self.segment_list[-1][-1])

    def insert_point_in_line(self, distance: float) -> QgsPointXY:
        """ Insert new point at given distance.

            :param distance: distance from start, where to insert a new point
            :type distance: float

            :return: inserted point
            :rtype: QgsPointXY

            :raises AttributeError: Given distance higher then `length`
        """
        if distance == 0:
            return self.segment_list[0][0]

        if distance == self.length():
            return self.segment_list[-1][-1]

        for i in range(0, len(self.segment_list)):
            segment = self.segment_list[i]
            seg_length = segment[1].distance(segment[0])
            if distance > seg_length:
                distance -= seg_length
                continue
            else:
                factor: float = distance / seg_length
                new_pt: QgsPointXY = QgsPointXY(segment[0].x() + factor * (segment[1].x() - segment[0].x()),
                                                segment[0].y() + factor * (segment[1].y() - segment[0].y()))
                new_segment: List[QgsPointXY] = [new_pt, segment[1]]
                segment[1] = new_pt
                self.segment_list.insert(i + 1, new_segment)
                return new_pt
        raise AttributeError("übergebene Entfernung länger als Linie!")

    def as_point_list(self) -> List[QgsPointXY]:
        """ Returns line segments as new poly line.

            :return: list of points
            :rtype: List[QgsPointXY]
        """
        return [seg[0] for seg in self.segment_list] + [self.segment_list[-1][-1]]

    @classmethod
    def from_point_list(cls, points: List[QgsPointXY]) -> 'PolylineWrapper':
        """ Creates new `PolylineWrapper` object from given poly line.

            :param points: poly line
            :type points: List[QgsPointXY]

            :return: PolylineWrapper
            :rtype: PolylineWrapper
        """
        segment_list: List[List[QgsPointXY]] = []
        for i in range(0, len(points) - 1):
            segment_list.append([points[i], points[i + 1]])
        return cls(segment_list)
