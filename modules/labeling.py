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
from json import loads, dumps

from qgis.PyQt.QtCore import pyqtSignal, Qt
from qgis.PyQt.QtWidgets import QFileDialog, QListWidgetItem, QMessageBox

from qgis.core import (QgsApplication, QgsMapLayerProxyModel, QgsVectorLayer,
                       QgsProject, QgsPointXY, QgsGeometry)
from qgis.gui import QgsDockWidget, QgsFieldExpressionWidget

from ..utilities.functions import FIELDS, get_label_text, create_new_layer, generate_from_feature, get_reference_data, create_new_feature

from ..submodules.module_base.base_class import UiModuleBase
from ..submodules.module_base.pyqt.functions import set_label_status, set_label_error
from ..submodules.qgis.canvas.maptool_click_snap import MapToolQgisSnap
from ..submodules.qgis.canvas.canvas_drawing import DrawTool

FORM_CLASS, _ = UiModuleBase.get_uic_classes(__file__)


class LabelingMenu(UiModuleBase, QgsDockWidget, FORM_CLASS):
    saved = pyqtSignal(name="saved")

    def __init__(self, *args, **kwargs):
        UiModuleBase.__init__(self, *args, **kwargs)
        QgsDockWidget.__init__(self, kwargs.get('parent', None))

        self._point_feature = None
        self._draw_tool = DrawTool(self.iface.mapCanvas(), drawings=self.get_plugin().drawings)

        self.setupUi(self)

        self._setup()
        self._reset()

    def _setup(self):
        """ setup some options """

        # reload loadable layers
        self.connect(QgsProject.instance().layersAdded, self._load_layers)
        self.connect(QgsProject.instance().layersRemoved, self._load_layers)

        self.replace_widget_with_class(self.Edit_New_Expression, ExpressionWidget)
        self.replace_widget_with_class(self.Edit_Expression, ExpressionWidget)

        # set selectable layer types
        self.DrD_LabelingLayers.setFilters(QgsMapLayerProxyModel.PointLayer)
        self.DrD_ReferenceLayers.setFilters(QgsMapLayerProxyModel.VectorLayer)

        # add button icons
        self.But_Add_Point.setIcon(self.getThemeIcon("console/iconNewTabEditorConsole.svg"))
        self.But_Remove_Point.setIcon(self.getThemeIcon("mActionDeleteSelectedFeatures.svg"))
        self.But_Create_Layer.setIcon(self.getThemeIcon("console/iconNewTabEditorConsole.svg"))
        self.But_Create_From_Selection.setIcon(self.getThemeIcon("mActionProcessSelected.svg"))
        self.But_Refresch_Selected.setIcon(self.getThemeIcon("mActionProcessSelected.svg"))
        self.But_Create_Manual.setIcon(self.getThemeIcon("cursors/mCapturePoint.svg"))
        self.But_Save.setIcon(self.getThemeIcon("mActionFileSave.svg"))

        self.connect(self.Edit_Expression.exprEdited, self._show_feature_expr_result)
        self.connect(self.DrD_LabelingLayers.layerChanged, self._point_layer_changed)
        self.connect(self.DrD_ReferenceLayers.layerChanged, self._line_layer_changed)
        self.connect(self.But_Create_Layer.clicked, self._create_new_layer)
        self.connect(self.But_Create_From_Selection.clicked, self._create_from_selected)
        self.connect(self.But_Create_Manual.clicked, self._create_manual)
        self.connect(self.But_Refresch_Selected.clicked, self._refresh_selected)
        self.connect(self.List_Points.itemSelectionChanged, self._selected_point_pos_changed)
        self.connect(self.But_Remove_Point.clicked, self._remove_point_pos)
        self.connect(self.But_Add_Point.clicked, self._add_point_pos)
        self.connect(self.But_Save.clicked, self._save_point)

        self.connect(self.iface.mapCanvas().selectionChanged, self._point_feature_selected)

        self._load_layers()

    def _load_layers(self, *args):
        """ Reloads exclude list for layer dropdowns """
        exclude_labeling_layers = []
        exclude_reference_layers = []

        layers = QgsProject.instance().mapLayers().values()
        for layer in layers:
            if self.is_point_layer_valid(layer):
                # incompatible reference layers
                exclude_reference_layers.append(layer)
            else:
                # incompatible labeling layers
                exclude_labeling_layers.append(layer)

        self.DrD_LabelingLayers.setExceptedLayerList(exclude_labeling_layers)
        self.DrD_ReferenceLayers.setExceptedLayerList(exclude_reference_layers)

    def _save_point(self, checked: bool):
        set_label_error(self.Label_Status_Edit, "")

        if self._point_feature is None:
            return

        if self.Edit_Expression.isVisible():
            if not self.Edit_Expression.isValidExpression(self.Edit_Expression.currentText()):
                set_label_error(self.Label_Status_Edit, "Ausdruck fehlerhaft")
                return

        if self.Edit_Manual_Expression.isVisible():
            if not self.Edit_Manual_Expression.toPlainText().strip():
                set_label_error(self.Label_Status_Edit, "Bitte Beschriftung eingeben.")
                return

        index_map = self.point_layer.dataProvider().fieldNameMap()
        update_map = {}
        if self.Edit_Expression.isVisible():
            reference = get_reference_data(self._point_feature)
            if reference:
                text = get_label_text(reference[1], self.Edit_Expression.currentText())
                update_map[index_map["Text"]] = text
            else:
                reply = self.question(
                    "Referenz nicht gefunden",
                    "Linienreferenz nicht gefunden. Speichern fortfahren (Text wird nicht aktualisiert)?"
                )
                if reply != self.Yes:
                    return

        if self.Edit_Manual_Expression.isVisible():
            update_map[index_map["Text"]] = self.Edit_Manual_Expression.toPlainText().strip()

        if not update_map:
            set_label_error(self.Label_Status_Edit, "Keine Attribute zum gespeichern gefunden.")
            return

        points = []
        for row in range(self.List_Points.count()):
            item = self.List_Points.item(row)
            x, y = item.text().split(",")
            x = float(x)
            y = float(y)
            points.append([x, y])

        points = dumps(points)
        update_map[index_map["Points"]] = points
        if self.point_layer.isEditable():
            self.point_layer.changeAttributeValues(self._point_feature.id(), update_map)
        else:
            self.point_layer.dataProvider().changeAttributeValues({self._point_feature.id(): update_map})

        self.point_layer.triggerRepaint()

    def _add_point_pos(self, checked: bool):
        tool = MapToolQgisSnap(self.iface, self.point_layer)
        tool.clicked.connect(self._add_point_to_list)
        tool.moved.connect(self._maptool_moved)
        tool.aborted.connect(self._maptool_aborted)

    def _maptool_moved(self, point: QgsPointXY):
        self._draw_tool.remove_all_drawings()

        if not self._point_feature or not self.point_layer:
            return

        current_point = self.point_layer.getGeometry(self._point_feature.id()).asPoint()

        self._draw_tool.create_rubber_band(
            QgsGeometry.fromPolylineXY([current_point, point]),
            self.point_layer)

    def _maptool_aborted(self):
        self._draw_tool.remove_all_drawings()

    def _add_point_to_list(self, point: QgsPointXY):
        pos = point.toString(8)
        item = QListWidgetItem(pos)
        self.List_Points.addItem(item)

    def _remove_point_pos(self, checked: bool):
        items = self.List_Points.selectedItems()
        if not items:
            return

        for item in items:
            self.List_Points.takeItem(self.List_Points.row(item))

    def _selected_point_pos_changed(self):
        self.But_Remove_Point.setEnabled(False)
        items = self.List_Points.selectedItems()
        if not items:
            return

        self.But_Remove_Point.setEnabled(True)

    def _create_manual(self, *args):
        """ Create labeling point without layer referencing.
            Activates map tool to select position on map.
        """
        tool = MapToolQgisSnap(self.iface, self.point_layer)
        tool.clicked.connect(self._create_manual_point_clicked)
        tool.aborted.connect(self._maptool_aborted)

    def _create_manual_point_clicked(self, point: QgsPointXY):
        """ Tool clicked """
        set_label_error(self.Label_Status_Create, "")
        new_feature = create_new_feature(
            self.point_layer,
            "< Beschriftung fehlt >",
            "",
            None,
            [],
            point
        )

        """if self.point_layer.isEditable():
            if self.point_layer.addFeature(new_feature):
                bbox = QgsGeometry.fromPointXY(point).boundingBox()
                bbox.grow(0.01)
                self.point_layer.selectByRect(bbox)
            else:
                self.iface.messageBar().pushWarning("Easy Labeling", f"Erstellen eines neuen Punktes fehlgeschlagen.")
        else:"""
        prov = self.point_layer.dataProvider()
        ok, features = prov.addFeatures([new_feature])
        if ok:
            self.point_layer.reload()
            self.point_layer.selectByIds([features[0].id()])
        else:
            self.iface.messageBar().pushWarning("Easy Labeling", f"Erstellen eines neuen Punktes fehlgeschlagen ({prov.lastError()})")

    def _create_from_selected(self, checked: bool):
        """ Create labeling point with reference to selected feature """
        set_label_error(self.Label_Status_Create, "")

        if not self.Edit_New_Expression.isValidExpression(self.Edit_New_Expression.currentText()):
            set_label_error(self.Label_Status_Create, "Ausdruck fehlerhaft")
            return

        if not self.reference_layer.selectedFeatureCount():
            set_label_error(self.Label_Status_Create, "Keine Objekte gewählt")
            return

        if self.reference_layer.selectedFeatureCount() > 1:

            reply = self.question(
                "Beschriftungspunkte erstellen",
                f"Beschriftungspunkte für {self.reference_layer.selectedFeatureCount()} gewählte Objekte erstellen?"
            )

            if reply != self.Yes:
                return

        created = []
        for feature in self.reference_layer.selectedFeatures():
            f = generate_from_feature(self.reference_layer, feature,
                                      self.Edit_New_Expression.currentText(),
                                      self.point_layer, 10)
            ok, features = self.point_layer.dataProvider().addFeatures([f])
            if ok:
                created.extend(features)

        self.point_layer.reload()

        if len(created) == 1:
            self.point_layer.selectByIds([created[0].id()])

    def _refresh_selected(self, checked: bool):
        set_label_error(self.Label_Status, "")

        if not self.point_layer:
            return

        if not self.point_layer.selectedFeatureCount():
            set_label_error(self.Label_Status, "Keine Objekte gewählt")
            return

        if self.point_layer.selectedFeatureCount() > 1:

            reply = self.question(
                "Beschriftungspunkte aktualisieren",
                f"Beschriftungspunkte für {self.point_layer.selectedFeatureCount()} gewählte Objekte aktualisieren?"
            )

            if reply != self.Yes:
                return

        index_map = self.point_layer.dataProvider().fieldNameMap()
        update_map = {}
        errors = []
        for feature in self.point_layer.selectedFeatures():
            expression = feature['Expression']
            reference = feature['Reference']
            if not reference and not expression:
                continue

            reference = get_reference_data(feature)
            if reference is not None:
                layer, line_feature = reference
                text = get_label_text(line_feature, expression)
                update_map[feature.id()] = {index_map['Text']: text}
            else:
                errors.append(feature.id())

        if update_map:
            self.point_layer.dataProvider().changeAttributeValues(update_map)
            self.point_layer.triggerRepaint()
            self.iface.messageBar().pushSuccess("Easy Labeling", f"{len(update_map)} Objekt(e) aktualisiert.")

        if errors:
            msg = f"{len(errors)} Objekt(e) konnten nicht aktualisiert werden. Objekte in markiert."
            QMessageBox.warning(self.iface.mainWindow(), "Easy Labeling", msg)
            self.iface.messageBar().pushWarning("Easy Labeling", msg)
            self.point_layer.selectByIds(errors)

        if not update_map and not errors:
            self.iface.messageBar().pushSuccess("Easy Labeling", f"Keine Objekte aktualisiert.")

    def _create_new_layer(self, checked: bool):
        save_path, _ = QFileDialog.getSaveFileName(
            self.iface.mainWindow(),
            "Speichern unter",
            QgsProject.instance().homePath(),
            "GeoPackage (*.gpkg)"
        )
        if not save_path:
            return

        layer = create_new_layer(save_path, QgsProject.instance().crs())
        if not layer.isValid():
            set_label_error(self.Label_Status, "Fehler beim Erstellen eines neuen Layers")
            return
        QgsProject.instance().addMapLayer(layer, False)
        root = QgsProject.instance().layerTreeRoot()
        root.insertLayer(0, layer)
        self.DrD_LabelingLayers.setLayer(layer)

    def _point_layer_changed(self, layer: QgsVectorLayer):
        self._reset()

    def _line_layer_changed(self, layer: QgsVectorLayer):
        self._reset()

    def _show_feature_expr_result(self):
        set_label_status(self.Label_Edit_Preview, "")
        expression = self.Edit_Expression.currentText()
        text = get_label_text(self._point_feature, expression)
        if not text:
            set_label_error(self.Label_Edit_Preview, "Fehler in Ausdruck")
        else:
            set_label_status(self.Label_Edit_Preview, text)

    @classmethod
    def is_point_layer_valid(cls, layer: QgsVectorLayer) -> bool:
        if not layer:
            return False

        names = layer.dataProvider().fields().names()
        for field in FIELDS:
            if field.name() not in names:
                return False

        return True

    def _reset(self):
        point_layer = self.DrD_LabelingLayers.currentLayer()
        reference_layer = self.DrD_ReferenceLayers.currentLayer()

        set_label_status(self.Label_Status, "")
        set_label_status(self.Label_Status_Create, "")
        set_label_status(self.Label_Status_Edit, "")
        set_label_status(self.Label_Edit_Feature, "")

        self.Edit_New_Expression.setLayer(None)

        self._point_feature = None
        self.Edit_Expression.setExpression("")
        self.Edit_Manual_Expression.setPlainText("")
        self.Edit_Expression.setLayer(None)

        self.GroupBox_Create.setEnabled(False)
        self.GroupBox_Edit.setEnabled(False)
        self.But_Refresch_Selected.setEnabled(False)
        self.List_Points.clear()

        # 1. a point layer must be selected
        if not point_layer:
            set_label_error(self.Label_Status, "Bitte Beschriftungslayer wählen")
            return

        if not self.is_point_layer_valid(point_layer):
            set_label_error(self.Label_Status, "Beschriftungslayer ist nicht kompatibel")
            return

        self.GroupBox_Create.setEnabled(True)
        self.But_Refresch_Selected.setEnabled(True)

        if reference_layer:
            self.Edit_New_Expression.setLayer(reference_layer)
            self.Widget_Create.setEnabled(True)
            self.point_layer.selectByIds(self.point_layer.selectedFeatureIds())
        else:
            self.Widget_Create.setEnabled(False)
            set_label_error(self.Label_Status_Create, "Bitte einen Linienlayer wählen")

    def _point_feature_selected(self, layer: QgsVectorLayer):
        """ Load data from selected point feature """

        self._point_feature = None
        self.Edit_Manual_Expression.setPlainText("")
        self.Edit_Expression.setExpression("")
        self.Edit_Expression.setLayer(None)
        self.List_Points.clear()

        self.GroupBox_Edit.setEnabled(False)
        set_label_error(self.Label_Edit_Feature, "")
        set_label_error(self.Label_Status_Edit, "")

        if not layer:
            return

        if layer is not self.point_layer:
            return

        selected = layer.selectedFeatureIds()

        if not selected:
            set_label_error(self.Label_Status_Edit,
                            "Kein Objekt ausgewählt")
            return

        if len(selected) != 1:
            set_label_error(self.Label_Status_Edit,
                            "Bitte nur ein Objekt wählen")
            return

        self._point_feature = self.point_layer.getFeature(selected[0])

        expression = self._point_feature['Expression']
        reference = self._point_feature['Reference']
        text = self._point_feature['Text']
        if isinstance(expression, str):
            expression = expression.strip()

        if expression or reference:
            # expression or reference set
            self.Edit_Expression.setLayer(self.reference_layer)
            self.Edit_Expression.setExpression(expression)
            set_label_status(self.Label_Edit_Feature,
                            f"Punkt: {selected[0]}\n"
                            f"Reference: {reference}")
            self.Edit_Manual_Expression.hide()
            self.Edit_Expression.show()
        else:
            # no expression and no reference set, activate manual fields
            self.Edit_Manual_Expression.show()
            self.Edit_Expression.hide()
            self.Edit_Manual_Expression.setPlainText(text)
            set_label_status(self.Label_Edit_Feature,
                            f"Punkt: {selected[0]} (ohne Referenzlayer)\n"
                            f"Manuelle Textbearbeitung.")

        try:
            points = loads(self._point_feature['Points'])
        except:
            points = []

        # load points to view
        for point in points:
            item = QListWidgetItem(f"{point[0]},{point[1]}")
            self.List_Points.addItem(item)

        self.GroupBox_Edit.setEnabled(True)

        reference = get_reference_data(self._point_feature)
        self._selected_point_pos_changed()

        if reference is not None and reference:
            # reference found and layer reference active
            self.iface.mapCanvas().flashFeatureIds(reference[0], [reference[1].id()], flashes=4)
        elif reference:
            # reference active, but feature not found
            msg = f"Referenzierte Linie '{self._point_feature['Reference']}' nicht gefunden"
            self.iface.messageBar().pushWarning("Easy Labeling", msg)
            set_label_error(self.Label_Status_Edit, msg)

    @property
    def point_layer(self):
        return self.DrD_LabelingLayers.currentLayer()

    @property
    def reference_layer(self):
        return self.DrD_ReferenceLayers.currentLayer()

    @classmethod
    def tr_(cls, text: str):
        result = QgsApplication.translate("QgsApplication", text)
        return result

    def closeEvent(self, event) -> None:
        event.accept()
        self.unload(True)

    def unload(self, self_unload: bool = False):
        return super().unload(self_unload)

    @classmethod
    def load(cls, plugin):
        try:
            plugin['LabelingMenu'].show()
        except KeyError:
            module = plugin.add_module("LabelingMenu", cls)
            plugin.iface.addDockWidget(Qt.RightDockWidgetArea, module)
            plugin['LabelingMenu'].show()


class ExpressionWidget(QgsFieldExpressionWidget):

    exprEdited = pyqtSignal(str, name="exprEdited")

    def expressionEditingFinished(self):
        self.exprEdited.emit(self.currentText())