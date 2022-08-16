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
import os.path

from pathlib import Path

from qgis.core import (QgsVectorLayer, QgsFeature, QgsExpression,
                       QgsExpressionContextUtils, QgsTriangle, QgsPointXY,
                       QgsField, QgsVectorFileWriter, QgsWkbTypes,
                       QgsCoordinateTransform, QgsProject,
                       QgsGeometry, QgsCoordinateReferenceSystem)
from qgis.PyQt.QtCore import QVariant

from typing import Optional, Tuple, List

from easy_labeling.submodules.qgis.geometry.functions import get_distance_area
from easy_labeling.submodules.qgis.geometry.line import get_polyline, is_point_in_polylist
from easy_labeling.submodules.qgis.geometry.transform import transform_geometry
from easy_labeling.submodules.qgis.tools.poly_line_wrapper import PolylineWrapper
from easy_labeling.submodules.qgis.constants import EPSILON, EPSILON_METRES


FIELDS = [
        # Text to label
        QgsField("Text", QVariant.String),
        # list of points [[x, y], [x, y]]
        # per point an arrow from features point
        QgsField("Points", QVariant.String),
        # expression to evaluate on reference feature
        QgsField("Expression", QVariant.String),
        # reference feature from "Layername.FeatureId"
        QgsField("Reference", QVariant.String),
]


def get_new_position(source_layer: QgsVectorLayer, feature: QgsFeature, dest_layer: QgsVectorLayer,
                     offset: Optional[float] = None) -> Optional[QgsPointXY]:
    """ Returns new point position.
        Valid for:
            - line geometries (only single typ)
            - point geometries (on multi point geometries the first point)
            - polygons (only center as default)


        :param layer: source layer
        :param feature: source feature
        :param dest_layer: destination layer
        :param offset: offset in meters from centroid point feature
    """
    crs = source_layer.dataProvider().crs()
    dest_crs = dest_layer.dataProvider().crs()
    geom = transform_geometry(feature.geometry(),
                              crs,
                              dest_layer.dataProvider().crs())
    area = get_distance_area(dest_crs)

    epsilon = EPSILON if dest_crs.isGeographic() else EPSILON_METRES

    if geom.type() == QgsWkbTypes.PointGeometry:
        if geom.isMultipart():
            return geom.asMultiPoint()[0]
        return geom.asPoint()

    if geom.type() == QgsWkbTypes.PolygonGeometry:
        return geom.center()

    poly = get_polyline(geom)

    if not poly:
        return None

    wrapper = PolylineWrapper.from_point_list(poly)
    center_on_line = wrapper.insert_point_in_line(wrapper.length() / 2)
    if offset is None or offset == 0:
        point = center_on_line
    else:
        # calculate new point position
        start = poly[0]
        end = poly[-1]
        if start.compare(end, epsilon) or center_on_line.compare(start, epsilon) or center_on_line.compare(end, epsilon):
            return None

        triangle = QgsTriangle(start, end, center_on_line)
        points = [[QgsPointXY(c) for c in a] for a in triangle.altitudes()]
        altitude = [a for a in points if is_point_in_polylist(center_on_line, a, epsilon)][0]
        distance = center_on_line.distance(altitude[1])  # relative distance
        length = area.measureLine(center_on_line, altitude[1])  # distance in meters

        factor = distance / length
        new_distance = factor * offset
        point = center_on_line.project(new_distance, center_on_line.azimuth(altitude[1]))

    """# add found poly line to project as memory layer
    layer = QgsVectorLayer(f"LineString?crs={dest_crs.authid()}", "test", "memory")
    f = QgsFeature()
    f.setGeometry(QgsGeometry.fromPolylineXY([center_on_line, point]))
    layer.dataProvider().addFeatures([f])
    QgsProject.instance().addMapLayer(layer)"""

    return point


def generate_from_feature(source_layer: QgsVectorLayer, feature: QgsFeature, expression: str, dest_layer: QgsVectorLayer,
                          offset: Optional[float] = None) -> Optional[QgsFeature]:
    """ Creates a new point feature from given line feature.
        Only valid for LineString geometries. Multitype not allowed/possible.

        :param layer: source layer
        :param feature: source feature
        :param expression: expression to evaluate on feature
        :param dest_layer: destination layer
        :param offset: offset in meters from centroid point feature
    """
    # gets text from feature
    text = get_label_text(feature, expression)

    point = get_new_position(source_layer, feature, dest_layer, offset)
    if point is None:
        return None
    geom = transform_geometry(feature.geometry(),
                              source_layer.dataProvider().crs(),
                              dest_layer.dataProvider().crs())

    if geom.type() == QgsWkbTypes.LineGeometry:
        poly = get_polyline(geom)
        start = poly[0]
        end = poly[-1]
    else:
        start = None
        end = None

    new_feature = create_new_feature(
        dest_layer,
        text,
        expression,
        f"{source_layer.name()}.{feature.id()}",
        [[start], [end]] if start else [],
        point
    )

    return new_feature


def create_new_feature(dest_layer: QgsVectorLayer, text: str, expression: str,
                       reference: Optional[str], points: List[List[QgsPointXY]],
                       point: QgsPointXY):
    """ Create a new labeling feature from given attributes. """

    new_feature = QgsFeature(dest_layer.fields())
    new_feature['Text'] = text
    new_feature['Expression'] = expression
    new_feature['Reference'] =reference
    new_feature['Points'] = str([[p.toString(8) for p in part] for part in points])
    new_feature.setGeometry(QgsGeometry.fromPointXY(point))

    return new_feature


def get_label_text(feature: QgsFeature, expression: str) -> str:
    """ Gets evaluated text from given feature """

    context = QgsExpressionContextUtils.createFeatureBasedContext(
        feature, feature.fields())
    expression = QgsExpression(expression)
    result = expression.evaluate(context)

    return result


def create_new_layer(location: str, crs: QgsCoordinateReferenceSystem):
    name = os.path.basename(location)
    layer = QgsVectorLayer(f"Point?crs={crs.authid()}", name, "memory")
    layer.dataProvider().addAttributes(FIELDS)
    layer.updateFields()

    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName = "GPKG"
    # create options, list.append does not work on empty/default layerOptions
    options.layerOptions = ["GEOMETRY_NULLABLE=NO"]
    options.layerName = layer.name()
    options.overrideGeometryType = QgsWkbTypes.Point
    options.forceMulti = False

    # transform
    transform_params = QgsCoordinateTransform(
        layer.dataProvider().crs(),
        layer.dataProvider().crs(),
        QgsProject.instance())
    options.ct = transform_params

    options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteFile

    QgsVectorFileWriter.writeAsVectorFormatV2(
        layer,
        location,
        QgsProject.instance().transformContext(),
        options
    )

    style = str(Path(__file__).parent.parent / "templates" / "default_style.qml")
    layer = QgsVectorLayer(location, name, "ogr")
    layer.loadNamedStyle(style)

    return layer


def get_reference_data(point_feature) -> Optional[Tuple[QgsVectorLayer, QgsFeature]]:
    reference = point_feature['Reference']
    if not isinstance(reference, str):
        return None

    if "." not in reference:
        return None

    splitted = reference.split(".")
    if len(splitted) != 2:
        return None

    name, fid = splitted

    layers = QgsProject.instance().mapLayersByName(name)

    if len(layers) != 1:
        return None

    if not fid.isdigit():
        return None

    fid = int(fid)

    layer = layers[0]
    feature = layer.getFeature(fid)
    if not feature.isValid():
        return None

    return layer, feature


if __name__ in ("__main__", "__console__"):
    layer = iface.activeLayer()
    dest_layer = QgsProject.instance().mapLayersByName("Punkte")[0]
    for sf in layer.selectedFeatures():
        f = generate_from_feature(layer, sf, """'osm_id: ' || "osm_id" """, dest_layer, 10)
        if f:
            dest_layer.dataProvider().addFeatures([f])