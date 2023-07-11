import bpy
import math
import random

from bpy.props import *
from bpy_types import PropertyGroup
from mathutils import Vector
import bmesh

"""
    HELPER FUNCTIONS START HERE
"""


def measure_chars(chars):
    width = 0
    for char in chars:
        width += char.dimensions.x
    return width


def normal_in_direction(normal, direction, limit=0.5):
    return direction.dot(normal) > limit


def going_up(normal, limit=0.5):
    return normal_in_direction(normal, Vector((0, 0, 1)), limit)


def going_down(normal, limit=0.5):
    return normal_in_direction(normal, Vector((0, 0, -1)), limit)


def going_side(normal, limit=0.5):
    return going_up(normal, limit) is False and going_down(normal, limit) is False


"""
    HELPER FUNCTIONS END HERE
"""

"""
    steps:
        1. create characters
        2. extrude characters
        3. add materials 
        4. connect characters
        5. create backplate
"""


def create_text_object(text, offset=0.02, extrude=0.0, bevel_res=3, bevel_depth=0.008, fill_mode="NONE", y_offset=0):
    selected_objects = bpy.context.selected_objects

    for obj in selected_objects:
        obj.select_set(False)

    font_curve = bpy.data.curves.new(type="FONT", name="font_curve")
    text_obj = bpy.data.objects.new("font_curve", font_curve)

    text_obj.data.body = text

    text_obj.rotation_euler.x = math.radians(90)
    text_obj.data.size = 2.0
    text_obj.data.fill_mode = fill_mode
    text_obj.data.bevel_depth = bevel_depth
    text_obj.data.bevel_resolution = bevel_res
    text_obj.data.align_x = 'CENTER'
    text_obj.data.offset = offset
    text_obj.location.y += y_offset
    text_obj.location.z = 0.5
    text_obj.data.extrude = extrude

    bpy.context.collection.objects.link(text_obj)
    bpy.context.view_layer.objects.active = text_obj

    selection = text_obj.select_get()
    text_obj.select_set(True)

    bpy.ops.object.convert(target="MESH")
    text_obj.select_set(selection)

    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.beautify_fill()
    bpy.ops.object.mode_set(mode="OBJECT")

    return text_obj


# Adds the emission material to the object and creates a new material if it doesn't exist
def add_material(obj, color, emission, name):
    mat_neon = bpy.data.materials.new(f"Text_{name}")
    mat_neon.use_nodes = True
    bdsf_node = mat_neon.node_tree.nodes["Principled BSDF"]
    bdsf_node.inputs[0].default_value = (color[0], color[1], color[2], 1)
    bdsf_node.inputs[19].default_value = (
        emission[0], emission[1], emission[2], 1)
    bdsf_node.inputs[20].default_value = 15.0

    if len(obj.data.materials) == 0:
        obj.data.materials.append(mat_neon)
    else:
        obj.data.materials[0] = mat_neon


def create_character_mesh(char, color, x_loc):
    # create the inside character mesh
    text_obj = create_text_object(char)
    add_material(text_obj, color=(1, 1, 1, 1), emission=color, name="inside")

    # create the outside character mesh
    text_obj_outside = create_text_object(
        char, offset=0.04, fill_mode="BACK", extrude=0.06, y_offset=0.06)
    add_material(text_obj_outside, color=(0, 0, 0, 1),
                 emission=(0, 0, 0, 0), name="outside")

    # Deselect all objects and join the inside and outside character mesh
    bpy.ops.object.select_all(action='DESELECT')
    text_obj.select_set(True)
    text_obj_outside.select_set(True)
    bpy.context.view_layer.objects.active = text_obj
    bpy.ops.object.join()

    # Move the character to the offset position
    so = bpy.context.active_object
    so.location.x = x_loc + so.dimensions.x / 2
    bpy.context.view_layer.update()
    return text_obj


def add_bezier(p1, p2):
    # Convert points to vectors
    v0, v1 = Vector(p1), Vector(p2)

    # Calculate center between two vectors
    center = (v1 + v0) / 2

    # create curve object and bezier curve
    curve = bpy.data.curves.new('Curve', 'CURVE')
    spline = curve.splines.new('BEZIER')

    # add two bezier points
    bp0 = spline.bezier_points[0]
    bp0.co = v0 - center
    spline.bezier_points[0].handle_right[2] -= 0.5
    spline.bezier_points.add(count=1)
    bp1 = spline.bezier_points[1]
    bp1.co = v1 - center

    # create object and set location
    ob = bpy.data.objects.new('Curve', curve)
    ob.matrix_world.translation = center
    return ob


def create_connector(loc, scale=0.02):
    bpy.ops.mesh.primitive_cube_add(scale=(scale, scale, scale))
    connector = bpy.context.active_object
    bpy.ops.object.transform_apply(scale=True)
    connector.location = loc
    add_material(connector, color=(0, 0, 0, 1),
                 emission=(0, 0, 0, 0), name="connector")


def create_chars(text, color):
    x_loc = 0
    chars = list()
    for char in text:
        chars.append(create_character_mesh(char, color, x_loc))
        x_loc += bpy.context.active_object.dimensions.x
    return chars


def connect_chars(chars):
    for count, value in enumerate(chars):
        if count + 1 < len(chars):
            # get random points for connecting two characters
            p1 = random.choice(chars[count].data.vertices)
            p2 = random.choice(chars[count + 1].data.vertices)

            # convert points to vectors
            v1 = Vector((p1.co[0], p1.co[1], -0.15))
            v2 = Vector((p2.co[0], p2.co[1], -0.15))

            # get the world position of the points
            pv1 = chars[count].matrix_world @ v1
            pv2 = chars[count + 1].matrix_world @ v2

            # create the connector sockets and connect them with a Bezier curve
            create_connector(pv1)
            create_connector(pv2)

            curve = add_bezier(pv1, pv2)
            bpy.context.collection.objects.link(curve)

            add_material(curve, color=(0.1, 0.1, 0.1, 1),
                         emission=(0, 0, 0, 0), name="curve")

            curve.data.dimensions = '3D'
            curve.data.bevel_depth = 0.022
            curve.data.bevel_resolution = 3


def create_back_cover(chars):
    width = measure_chars(chars)
    bpy.ops.mesh.primitive_cube_add(scale=(width * 0.55, 0.25, 1))
    obj = bpy.context.object
    bpy.ops.object.transform_apply(scale=True)
    obj.location.x += width * 0.5
    obj.location.z = 1.18
    add_material(obj, color=(0, 0, 0, 1),
                 emission=(0, 0, 0, 0), name="cover")

    bpy.ops.object.modifier_add(type='BEVEL')
    bpy.context.object.modifiers["Bevel"].width = 0.1
    bpy.context.object.modifiers["Bevel"].segments = 32
    bpy.ops.object.modifier_add(type='SOLIDIFY')
    bpy.context.object.modifiers["Solidify"].thickness = -0.05

    prev_mode = obj.mode

    # Will need to be in object mode
    bpy.ops.object.mode_set(mode='OBJECT', toggle=False)

    # Create a bmesh mesh
    bm = bmesh.new()
    bm.from_mesh(obj.data)

    # Get faces 
    bm.faces.ensure_lookup_table()

    # Identify the wanted faces
    faces = [f for f in bm.faces if normal_in_direction(
        f.normal, Vector((0, -1, 0)), 0.5)]

    # Delete them
    bmesh.ops.delete(bm, geom=faces, context='FACES_ONLY')

    # Push the geometry back to the mesh
    bm.to_mesh(obj.data)

    # Back to the initial mode
    bpy.ops.object.mode_set(mode=prev_mode, toggle=False)


def create_neon_sign(text="neon", color=(1, 0, 0, 0)):
    chars = create_chars(text, color)
    connect_chars(chars)
    create_back_cover(chars)


class NeonOperator(bpy.types.Operator):
    bl_idname = "object.neon_operator"
    bl_label = "Create Text"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.generator_settings
        create_neon_sign(text=props["neon_text"],
                         color=props["neon_color"])
        return {'FINISHED'}


class GeneratorSettings(PropertyGroup):
    neon_text: StringProperty(
        name="neon",
        default="NEON",
        maxlen=1024,
        description="text to display"
    )

    neon_color: FloatVectorProperty(
        name="neon color",
        subtype='COLOR',
        default=(1.0, 1.0, 1.0),
        min=0.0, max=1.0,
        description="color picker"
    )


class ToolPanel(bpy.types.Panel):
    bl_label = "Neon sign generator"
    bl_idname = "GeneratorPanel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Neon sign generator"

    object_color: FloatVectorProperty(
        name="object_color",
        subtype='COLOR',
        default=(1.0, 1.0, 1.0, 1.0),
        min=0.0, max=1.0,
        description="color picker"
    )

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        generator_settings = scene.generator_settings

        layout.prop(generator_settings, "neon_text", text="Text")
        layout.prop(generator_settings, "neon_color", text="Light color")
        row = layout.row()
        row.operator('object.neon_operator')


classes = (
    ToolPanel,
    GeneratorSettings,
    NeonOperator
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.generator_settings = PointerProperty(
        type=GeneratorSettings)


def unregister():
    del bpy.types.Scene.generator_settings

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == '__main__':
    register()
