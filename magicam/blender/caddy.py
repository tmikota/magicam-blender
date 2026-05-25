"""The Camera Caddy — a PySide6 UI for driving MagiCam rigs inside Blender.

Ported from the original multiplaneCamera ui.py, remapped onto the magicam.blender
modules. This is intentionally still PySide6 (a native bpy rebuild is future work).
PySide6 must be installed into Blender's Python.
"""

from __future__ import annotations

import math

import bpy
from mathutils import Euler, Matrix
from PySide6 import QtCore, QtGui, QtWidgets

from magicam.blender import build as mpc_build
from magicam.blender import image_plane as mpc_ip
from magicam.blender import scene as mpc_scene

_persistent_windows = []
LENSES = ["16mm", "24mm", "35mm", "50mm", "85mm", "120mm", "200mm"]


class ImagePlaneToolsWidget(QtWidgets.QWidget):
    """Per-plane tools: hide, opacity, snap-to-character, move/rotate."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.armature = None
        self.camera_rig_object = None
        self.move_delta = 30
        self.rotate_delta = 10
        self.image_plane_bone_name = None
        self.offset_x = 0.0
        self.offset_z = 0.0
        self.offset_z_rotation_degrees = 0.0
        self.setWindowTitle("Image Plane Tools")
        self.image_plane_object = None
        self.character_rig_c_pose = None
        self.setMinimumWidth(300)
        self.current_rig_object = parent.current_rig_object if parent else None

        self.hide_checkbox = QtWidgets.QCheckBox("Hide")
        self.opacity_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.snap_checkbox = QtWidgets.QCheckBox("Snap Character")
        self.move_x_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.move_z_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.rotate_z_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.imge_plane_object_label = QtWidgets.QLabel("Image Plane Object")
        self.character_rig_label = QtWidgets.QLabel("Character Rig Object")
        self.camera_rig_label = QtWidgets.QLabel("Camera Rig Object")

        self.move_x_slider.setRange(-10, 10)
        self.move_z_slider.setRange(-10, 10)
        self.rotate_z_slider.setRange(-180, 180)
        self.opacity_slider.setRange(0, 100)
        self.opacity_slider.setValue(100)

        layout = QtWidgets.QGridLayout()
        layout.addWidget(self.snap_checkbox, 1, 0)
        layout.addWidget(self.hide_checkbox, 2, 0)
        layout.addWidget(QtWidgets.QLabel("Opacity:"), 2, 1)
        layout.addWidget(self.opacity_slider, 2, 2)
        layout.addWidget(QtWidgets.QLabel("Move X:"), 3, 1)
        layout.addWidget(self.move_x_slider, 3, 2)
        layout.addWidget(QtWidgets.QLabel("Move Z:"), 3, 3)
        layout.addWidget(self.move_z_slider, 3, 4)
        layout.addWidget(QtWidgets.QLabel("Rotate Z:"), 4, 1)
        layout.addWidget(self.rotate_z_slider, 4, 2)
        layout.addWidget(self.camera_rig_label, 5, 0)
        layout.addWidget(self.imge_plane_object_label, 5, 1)
        layout.addWidget(self.character_rig_label, 5, 2)
        self.setLayout(layout)

        self.move_x_slider.valueChanged.connect(self.x_move_changed)
        self.move_z_slider.valueChanged.connect(self.z_move_changed)
        self.rotate_z_slider.valueChanged.connect(self.z_rotate_changed)
        self.hide_checkbox.toggled.connect(self.hide_toggled)
        self.snap_checkbox.toggled.connect(self.character_snap_toggled)
        self.opacity_slider.valueChanged.connect(self.opacity_changed)

    def apply_character_offset_delta(self, x=0.0, z=0.0, rotate_z_degrees=0.0):
        bone = self.character_rig_c_pose
        if not bone:
            return
        z_rad = math.radians(rotate_z_degrees)
        delta_matrix = (
            Matrix.Translation((x, 0.0, z))
            @ Euler((0.0, 0.0, z_rad), "XYZ").to_matrix().to_4x4()
        )
        bone.matrix = bone.matrix @ delta_matrix
        bone.keyframe_insert(data_path="location")
        bone.keyframe_insert(data_path="rotation_quaternion")
        bone.keyframe_insert(data_path="scale")

    def set_image_plane_object(
        self, image_plane_object, camera_rig_object=None, image_plane_bone_name=None
    ):
        self.image_plane_object = image_plane_object
        alpha = self.get_opacity(image_plane_object)
        self.opacity_slider.setValue(int(alpha * 100))
        self.get_character_rig(image_plane_object.name)
        self.armature = camera_rig_object
        self.camera_rig_object = camera_rig_object
        self.image_plane_bone_name = image_plane_bone_name
        if self.has_current_child():
            self.snap_checkbox.setChecked(True)
        self.update_selected_labels()

    def update_selected_labels(self):
        if self.image_plane_object:
            self.imge_plane_object_label.setText(
                f"Image Plane: {self.image_plane_object.name}"
            )
        else:
            self.imge_plane_object_label.setText("Image Plane: None")

        if self.character_rig_c_pose:
            self.character_rig_label.setText(
                f"Character Rig: {self.character_rig_c_pose.name}"
            )
        else:
            self.character_rig_label.setText("Character Rig: None")

        if self.camera_rig_object:
            self.camera_rig_label.setText(f"Camera Rig: {self.camera_rig_object.name}")
        else:
            self.camera_rig_label.setText("Camera Rig: None")

    @staticmethod
    def get_opacity(obj):
        for slot in obj.material_slots:
            mat = slot.material
            if mat and mat.use_nodes:
                for node in mat.node_tree.nodes:
                    if node.type == "BSDF_PRINCIPLED":
                        return node.inputs["Alpha"].default_value
        return 1.0

    def has_current_child(self):
        if not self.character_rig_c_pose or not self.image_plane_bone_name:
            return False
        for constraint in self.character_rig_c_pose.constraints:
            if (
                constraint.type == "CHILD_OF"
                and constraint.subtarget == self.image_plane_bone_name
            ):
                return True
        return False

    def get_character_rig(self, image_plane_name):
        parts = image_plane_name.split("_")
        character_name = parts[-2] if len(parts) >= 2 else image_plane_name
        self.character_rig_c_pose = mpc_scene.get_character_rig_c_pose(character_name)
        return self.character_rig_c_pose

    def parent_character_rig(self, character_bone, target_armature_obj, target_bone_name):
        if character_bone is None or target_armature_obj is None or not target_bone_name:
            print("Invalid input: missing bone, target armature, or bone name.")
            return
        for constraint in character_bone.constraints:
            if (
                constraint.type == "CHILD_OF"
                and constraint.target == target_armature_obj
                and constraint.subtarget == target_bone_name
            ):
                return
        target_bone = target_armature_obj.pose.bones.get(target_bone_name)
        if not target_bone:
            print(f"Target bone '{target_bone_name}' not found.")
            return
        target_matrix_world = target_armature_obj.matrix_world @ target_bone.matrix
        source_armature_obj = character_bone.id_data
        local_matrix = source_armature_obj.matrix_world.inverted() @ target_matrix_world
        character_bone.matrix = local_matrix
        character_bone.keyframe_insert(data_path="location")
        character_bone.keyframe_insert(data_path="rotation_quaternion")
        character_bone.keyframe_insert(data_path="scale")
        constraint = character_bone.constraints.new(type="CHILD_OF")
        constraint.name = f"Follow_{target_bone_name}"
        constraint.target = target_armature_obj
        constraint.subtarget = target_bone_name

    def unparent_character_rig(self, character_bone, target_bone_name=None):
        if not character_bone:
            return 0
        removed = 0
        armature_obj = character_bone.id_data
        current_world_matrix = armature_obj.matrix_world @ character_bone.matrix
        for constraint in list(character_bone.constraints):
            if constraint.type == "CHILD_OF":
                if target_bone_name is None or constraint.subtarget == target_bone_name:
                    character_bone.constraints.remove(constraint)
                    removed += 1
        character_bone.matrix = armature_obj.matrix_world.inverted() @ current_world_matrix
        character_bone.keyframe_insert(data_path="location")
        character_bone.keyframe_insert(data_path="rotation_quaternion")
        character_bone.keyframe_insert(data_path="scale")
        return removed

    def x_move_changed(self, value):
        if not self.character_rig_c_pose:
            return
        self.apply_character_offset_delta(x=value / self.move_delta)
        self.move_x_slider.blockSignals(True)
        self.move_x_slider.setValue(0)
        self.move_x_slider.blockSignals(False)

    def z_move_changed(self, value):
        self.apply_character_offset_delta(z=value / self.move_delta)
        self.move_z_slider.blockSignals(True)
        self.move_z_slider.setValue(0)
        self.move_z_slider.blockSignals(False)

    def z_rotate_changed(self, value):
        if not self.character_rig_c_pose:
            return
        self.apply_character_offset_delta(rotate_z_degrees=value / self.rotate_delta)
        self.rotate_z_slider.blockSignals(True)
        self.rotate_z_slider.setValue(0)
        self.rotate_z_slider.blockSignals(False)

    def character_snap_toggled(self):
        if self.snap_checkbox.isChecked():
            self.character_rig_c_pose = self.get_character_rig(
                self.image_plane_object.name
            )
            self.parent_character_rig(
                self.character_rig_c_pose, self.armature, self.image_plane_bone_name
            )
        else:
            self.unparent_character_rig(self.character_rig_c_pose)

    def hide_toggled(self):
        if self.image_plane_object:
            mpc_scene.toggle_image_plane(self.image_plane_object.name)

    def opacity_changed(self, value):
        if not self.image_plane_object:
            return
        alpha = value / 100.0
        for slot in self.image_plane_object.material_slots:
            mat = slot.material
            if mat and mat.use_nodes:
                for node in mat.node_tree.nodes:
                    if node.type == "BSDF_PRINCIPLED":
                        node.inputs["Alpha"].default_value = alpha


class CameraImportUI(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Camera Importer")
        self.setMinimumWidth(400)

        self.file_path_edit = QtWidgets.QLineEdit()
        self.file_path_edit.setPlaceholderText("Select TVPaint .json file")
        self.shot_name_edit = QtWidgets.QLineEdit()
        self.shot_name_edit.setText("SHOT_0010")

        self.browse_button = QtWidgets.QToolButton()
        self.browse_button.setText("...")
        self.browse_button.setToolTip("Browse for .json file")
        self.browse_button.clicked.connect(self.browse_for_file)

        file_layout = QtWidgets.QHBoxLayout()
        file_layout.addWidget(self.file_path_edit)
        file_layout.addWidget(self.browse_button)

        main_layout = QtWidgets.QVBoxLayout()
        main_layout.addWidget(QtWidgets.QLabel("Shot Name"))
        main_layout.addWidget(self.shot_name_edit)
        main_layout.addLayout(file_layout)

        self.import_button = QtWidgets.QPushButton("Import Camera")
        main_layout.addWidget(self.import_button)
        self.setLayout(main_layout)
        self.import_button.clicked.connect(self.import_clicked)

    def browse_for_file(self):
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select TVPaint JSON File", "", "JSON Files (*.json);;All Files (*)"
        )
        if file_path:
            self.file_path_edit.setText(file_path)

    def import_clicked(self):
        file_path = self.file_path_edit.text()
        if not file_path:
            QtWidgets.QMessageBox.warning(self, "Error", "Please select a valid file.")
            return
        mpc_build.import_multicam_rig(file_path, shot_name=self.shot_name_edit.text())
        self.accept()


class CameraCaddy(QtWidgets.QWidget):
    def __init__(self, camera_data):
        super().__init__()
        self.image_paths = []
        self.current_rig_object = None
        self.loaded_indexes = set()
        self.setWindowTitle("Camera Caddy")
        self.setLayout(QtWidgets.QVBoxLayout())

        self.camera_data = camera_data
        self.current_shot = None
        self.current_camera = None
        self.current_camera_object = None
        self.current_image_plane = None

        self.init_lists_section()
        self.init_thumbnail_strip()
        self.populate_shot_list()

    def init_lists_section(self):
        section_labels = QtWidgets.QHBoxLayout()

        shot_label_layout = QtWidgets.QVBoxLayout()
        shot_label_layout.addWidget(QtWidgets.QLabel("Shots"))
        shot_buttons_layout = QtWidgets.QHBoxLayout()
        self.start_frame_btn = QtWidgets.QPushButton("-")
        self.start_frame_btn.setMaximumSize(QtCore.QSize(40, 40))
        shot_buttons_layout.addWidget(self.start_frame_btn)
        self.end_frame_btn = QtWidgets.QPushButton("-")
        self.end_frame_btn.setMaximumSize(QtCore.QSize(40, 40))
        shot_buttons_layout.addWidget(self.end_frame_btn)
        self.view_range_btn = QtWidgets.QPushButton("View Range")
        shot_buttons_layout.addWidget(self.view_range_btn)
        shot_label_layout.addLayout(shot_buttons_layout)
        self.shot_list = QtWidgets.QListWidget()
        shot_label_layout.addWidget(self.shot_list)
        self.shot_list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.shot_list.currentItemChanged.connect(self.on_shot_selected)
        section_labels.addLayout(shot_label_layout)

        camera_label_layout = QtWidgets.QVBoxLayout()
        camera_label_layout.addWidget(QtWidgets.QLabel("Cameras"))
        camera_buttons_layout = QtWidgets.QHBoxLayout()
        self.lens_combo = QtWidgets.QComboBox()
        self.lens_combo.addItems(LENSES)
        camera_buttons_layout.addWidget(self.lens_combo)
        camera_label_layout.addLayout(camera_buttons_layout)
        self.camera_list = QtWidgets.QListWidget()
        camera_label_layout.addWidget(self.camera_list)
        self.camera_list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        section_labels.addLayout(camera_label_layout)

        plane_label_layout = QtWidgets.QVBoxLayout()
        plane_label_layout.addWidget(QtWidgets.QLabel("Image Planes"))
        plane_buttons_layout = QtWidgets.QHBoxLayout()
        self.static_btn = QtWidgets.QPushButton("Create Static")
        self.plane_list = QtWidgets.QListWidget()
        self.plane_list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        plane_buttons_layout.addWidget(self.static_btn)
        plane_label_layout.addLayout(plane_buttons_layout)
        plane_label_layout.addWidget(self.plane_list)
        section_labels.addLayout(plane_label_layout)

        self.plane_list.itemChanged.connect(self.on_plane_toggled)
        self.plane_list.clicked.connect(self.on_plane_selected)
        self.start_frame_btn.clicked.connect(self.set_current_frame)
        self.end_frame_btn.clicked.connect(self.set_current_frame)
        self.view_range_btn.clicked.connect(self.set_view_range)
        self.camera_list.clicked.connect(self.on_camera_selected)
        self.lens_combo.currentIndexChanged.connect(self.on_lens_changed)
        self.static_btn.clicked.connect(self.create_static_image_plane)

        self.image_plane_tools_widget = ImagePlaneToolsWidget(self)
        self.image_plane_tools_widget.hide()

        self.layout().addLayout(section_labels)
        self.layout().addWidget(self.image_plane_tools_widget)

    def create_static_image_plane(self):
        if not self.current_image_plane:
            return
        image_plane_obj = mpc_scene.get_image_plane_object(self.current_image_plane)
        new_plane_obj = mpc_ip.static_image_plane(image_plane_obj)
        image_frames = self.get_image_frames_from_camera_plane(self.current_image_plane)
        self.add_new_plane_to_armature_dict(new_plane_obj.name, image_frames)

    def get_image_frames_from_camera_plane(self, plane_name):
        if self.current_camera and self.current_shot:
            camera_data = self.camera_data[self.current_shot]["cameras"][self.current_camera]
            return camera_data["camera_planes"].get(plane_name, {}).get("image_frames", [])
        return []

    def add_new_plane_to_armature_dict(self, plane_name, image_frames):
        if self.current_camera and self.current_shot:
            camera_data = self.camera_data[self.current_shot]["cameras"][self.current_camera]
            camera_data["camera_planes"][plane_name] = {
                "enabled": True,
                "static_created": True,
                "image_frames": image_frames,
            }
            self.populate_plane_list()

    def set_current_frame(self, frame=None):
        if not frame:
            frame = self.sender().text()
        if frame != "-":
            mpc_scene.set_current_frame(frame)

    def on_lens_changed(self, index):
        lens = self.lens_combo.currentText()
        if self.current_camera_object:
            self.current_camera_object.data.lens = float(lens.replace("mm", ""))

    def set_view_range(self):
        start = self.start_frame_btn.text()
        end = self.end_frame_btn.text()
        print(f"Setting view range to {start} to {end}")

    def init_thumbnail_strip(self):
        self.layout().addWidget(QtWidgets.QLabel("Images"))
        self.thumbnail_scroll = QtWidgets.QScrollArea()
        self.thumbnail_scroll.setWidgetResizable(True)
        self.thumbnail_scroll.setFixedHeight(120)
        self.thumbnail_container = QtWidgets.QWidget()
        self.thumbnail_layout = QtWidgets.QHBoxLayout()
        self.thumbnail_layout.setContentsMargins(0, 0, 0, 0)
        self.thumbnail_layout.setSpacing(10)
        self.thumbnail_container.setLayout(self.thumbnail_layout)
        self.thumbnail_scroll.setWidget(self.thumbnail_container)
        self.thumbnail_scroll.viewport().installEventFilter(self)
        self.thumbnail_scroll.horizontalScrollBar().valueChanged.connect(
            self.lazy_load_visible_thumbnails
        )
        self.layout().addWidget(self.thumbnail_scroll)

    def populate_shot_list(self):
        self.shot_list.clear()
        for shot in self.camera_data:
            self.shot_list.addItem(shot)

    def on_shot_selected(self, current, previous=None):
        if current:
            self.current_shot = current.text()
            shot_data = self.camera_data.get(self.current_shot, {})
            start_frame = shot_data.get("start_frame", "-")
            end_frame = shot_data.get("end_frame", "-")
            self.start_frame_btn.setText(f"{start_frame}")
            self.end_frame_btn.setText(f"{end_frame}")
            self.populate_camera_list()

    def populate_camera_list(self):
        self.camera_list.clear()
        self.plane_list.clear()
        for i in reversed(range(self.thumbnail_layout.count())):
            widget = self.thumbnail_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
        cameras = self.camera_data[self.current_shot].get("cameras", {})
        for cam in cameras.keys():
            self.camera_list.addItem(cam)

    def on_camera_selected(self, index):
        current = self.camera_list.currentItem()
        if current:
            self.current_camera = current.text()
            rig_name = self.current_camera.replace("Cam", "ControlRig")
            self.current_camera_object = self.get_camera_object(self.current_camera)
            if self.current_camera_object:
                current_lens = f"{int(self.current_camera_object.data.lens)}mm"
                if current_lens != self.lens_combo.currentText():
                    self.lens_combo.setCurrentText(current_lens)
            self.populate_plane_list()
            mpc_scene.select_camera_root(rig_name)

    def get_camera_object(self, camera_name):
        return mpc_scene.camera_object(
            camera_name, collection_name=f"{self.current_shot}_camera"
        )

    def populate_plane_list(self):
        self.plane_list.clear()
        planes = self.camera_data[self.current_shot]["cameras"][self.current_camera].get(
            "camera_planes", {}
        )
        for plane in planes.keys():
            hidden = mpc_scene.hidden(plane)
            item = QtWidgets.QListWidgetItem(plane)
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            item.setCheckState(QtCore.Qt.Unchecked if hidden else QtCore.Qt.Checked)
            self.plane_list.addItem(item)

    def on_plane_toggled(self, item):
        if item:
            mpc_scene.toggle_image_plane(item.text())

    def on_plane_selected(self):
        current = self.plane_list.currentItem()
        if not current:
            return
        plane_name = current.text()
        ip_object = mpc_scene.get_image_plane_object(plane_name)
        armature, image_plane_bone_name = mpc_scene.get_image_plane_bone(ip_object)

        self.image_plane_tools_widget.show()
        self.image_plane_tools_widget.set_image_plane_object(
            ip_object,
            camera_rig_object=armature,
            image_plane_bone_name=image_plane_bone_name,
        )
        self.current_image_plane = plane_name

        image_data = self.camera_data[self.current_shot]["cameras"][self.current_camera][
            "camera_planes"
        ][plane_name].get("image_frames", [])
        self.image_paths = [frame["path"] for frame in image_data]
        self.loaded_indexes.clear()

        for i in reversed(range(self.thumbnail_layout.count())):
            widget = self.thumbnail_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
        for _ in self.image_paths:
            placeholder = QtWidgets.QLabel()
            placeholder.setFixedSize(120, int(120 * 9 / 16))
            self.thumbnail_layout.addWidget(placeholder)

        QtCore.QTimer.singleShot(0, self.lazy_load_visible_thumbnails)
        if armature and image_plane_bone_name:
            mpc_scene.select_image_plane(armature, image_plane_bone_name)

    def lazy_load_visible_thumbnails(self):
        visible_left = self.thumbnail_scroll.horizontalScrollBar().value()
        visible_right = visible_left + self.thumbnail_scroll.viewport().width()
        thumb_width = 130
        for i, path in enumerate(self.image_paths):
            if i >= self.thumbnail_layout.count():
                continue
            x_pos = i * thumb_width
            if i >= 5 and (x_pos + thumb_width < visible_left or x_pos > visible_right):
                continue
            if i in self.loaded_indexes:
                continue
            widget = self.thumbnail_layout.itemAt(i).widget()
            if isinstance(widget, QtWidgets.QLabel):
                if widget.pixmap() is None or widget.pixmap().isNull():
                    pixmap = QtGui.QPixmap(path).scaled(
                        120,
                        int(120 * 9 / 16),
                        QtCore.Qt.KeepAspectRatio,
                        QtCore.Qt.SmoothTransformation,
                    )
                    widget.setPixmap(pixmap)
                    self.loaded_indexes.add(i)

    def eventFilter(self, source, event):
        if (
            source == self.thumbnail_scroll.viewport()
            and event.type() == QtCore.QEvent.Paint
        ):
            current_scroll = self.thumbnail_scroll.horizontalScrollBar().value()
            if getattr(self, "_last_scroll", None) != current_scroll:
                self._last_scroll = current_scroll
                self.lazy_load_visible_thumbnails()
        return super().eventFilter(source, event)


def _qt_app():
    app = QtWidgets.QApplication.instance()
    if not app:
        app = QtWidgets.QApplication([])
    return app


def launch_caddy():
    """Gather data from MagiCam armatures and open the Camera Caddy."""
    shots = {}
    for rig in mpc_scene.get_multicam_armatures():
        rig_data = mpc_scene.load_camera_data_from_armature(rig)
        shot = rig_data.get("shot_name", rig.name)
        shots[shot] = rig_data

    if not shots:
        print("No multicam rigs found in the scene.")
        return None

    _qt_app()
    for win in list(_persistent_windows):
        win.close()
    _persistent_windows.clear()

    window = CameraCaddy(shots)
    window.show()
    _persistent_windows.append(window)
    return window


def launch_camera_importer():
    _qt_app()
    dialog = CameraImportUI()
    dialog.show()
    _persistent_windows.append(dialog)
    return dialog
