"""Build and render a real Blender fruit-bowl still life without external assets.

Run:
  blender --background --python scene.py -- --output /path/to/output

The output directory receives fruit-vase.blend and color-render.png.
All geometry, materials, lights, and the camera are created by this script.
"""

import argparse
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--samples", type=int, default=48)
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return parser.parse_args(argv)


def material(name, color, roughness=0.45):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = (*color, 1.0)
    shader.inputs["Roughness"].default_value = roughness
    return mat


def fruit_material(name, low, high):
    mat = material(name, high, 0.34)
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 3.6
    noise.inputs["Detail"].default_value = 2.0
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.15
    ramp.color_ramp.elements[0].color = (*low, 1.0)
    ramp.color_ramp.elements[1].position = 0.85
    ramp.color_ramp.elements[1].color = (*high, 1.0)
    links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], nodes.get("Principled BSDF").inputs["Base Color"])
    return mat


def mesh_object(name, vertices, faces, mat):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)
    for polygon in mesh.polygons:
        polygon.use_smooth = True
    return obj


def lathe(name, profile, mat, segments=128):
    vertices = []
    for radius, z in profile:
        for j in range(segments):
            angle = 2.0 * math.pi * j / segments
            vertices.append((radius * math.cos(angle), radius * math.sin(angle), z))
    faces = []
    for row in range(len(profile) - 1):
        for j in range(segments):
            a = row * segments + j
            b = row * segments + (j + 1) % segments
            faces.append((a, b, b + segments, a + segments))
    obj = mesh_object(name, vertices, faces, mat)
    subdivision = obj.modifiers.new("Rounded ceramic profile", "SUBSURF")
    subdivision.levels = 2
    subdivision.render_levels = 2
    return obj


def fruit(name, location, radius, height, mat, pear=False, rotation=(0, 0, 0)):
    segments, rings = 80, 48
    vertices = []
    for i in range(rings + 1):
        theta = math.pi * i / rings
        z = height * math.cos(theta)
        if pear:
            radial = radius * math.sin(theta) * (1.0 - 0.42 * math.cos(theta))
            z -= 0.035 * math.exp(-((theta / 0.25) ** 2))
        else:
            radial = radius * math.sin(theta) * (1.0 + 0.035 * math.cos(theta))
            z -= 0.115 * math.exp(-((theta / 0.30) ** 2))
            z += 0.055 * math.exp(-(((math.pi - theta) / 0.28) ** 2))
        for j in range(segments):
            phi = 2.0 * math.pi * j / segments
            lobe = 1.0 + (0.018 if pear else 0.035) * math.cos(5.0 * phi) * math.sin(theta) ** 2
            vertices.append((radial * lobe * math.cos(phi), radial * lobe * math.sin(phi), z))
    faces = []
    for i in range(rings):
        for j in range(segments):
            a = i * segments + j
            b = i * segments + (j + 1) % segments
            faces.append((a, a + segments, b + segments, b))
    obj = mesh_object(name, vertices, faces, mat)
    obj.location = location
    obj.rotation_euler = rotation
    return obj


def stem(name, parent, start_z, mat, height=0.22, bend=0.055):
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 16
    curve.bevel_depth = 0.027
    curve.bevel_resolution = 4
    spline = curve.splines.new("BEZIER")
    spline.bezier_points.add(2)
    for point, coordinate in zip(spline.bezier_points, [
        (0, 0, start_z), (bend * 0.45, 0, start_z + height * 0.55),
        (bend, 0.018, start_z + height),
    ]):
        point.co = coordinate
        point.handle_left_type = "AUTO"
        point.handle_right_type = "AUTO"
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)
    obj.parent = parent
    return obj


def leaf(parent, z, mat):
    # A gently cupped leaf, modeled as a surface with thickness.
    vertices = [
        (0.02, 0.0, z), (0.23, -0.13, z + 0.055),
        (0.48, -0.105, z + 0.10), (0.70, 0.0, z + 0.08),
        (0.48, 0.105, z + 0.10), (0.23, 0.13, z + 0.055),
        (0.25, 0.0, z + 0.09), (0.48, 0.0, z + 0.14),
    ]
    faces = [(0, 1, 6), (1, 2, 7, 6), (2, 3, 7), (3, 4, 7), (4, 5, 6, 7), (5, 0, 6)]
    obj = mesh_object("Pear leaf", vertices, faces, mat)
    obj.parent = parent
    solidify = obj.modifiers.new("Leaf thickness", "SOLIDIFY")
    solidify.thickness = 0.008
    subdivision = obj.modifiers.new("Leaf curve", "SUBSURF")
    subdivision.levels = 2
    return obj


def aim(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


def area_light(name, location, power, size, color, target=(0, 0, 1)):
    light = bpy.data.lights.new(name, "AREA")
    light.energy = power
    light.shape = "DISK"
    light.size = size
    light.color = color
    obj = bpy.data.objects.new(name, light)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    aim(obj, target)


def main():
    args = arguments()
    output = args.output.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)

    ceramic = material("Burnished terracotta ceramic", (0.40, 0.16, 0.075), 0.31)
    red = fruit_material("Red apple skin", (0.18, 0.018, 0.012), (0.48, 0.070, 0.027))
    gold = fruit_material("Golden pear skin", (0.39, 0.35, 0.075), (0.75, 0.64, 0.22))
    leaf_mat = material("Olive green leaf", (0.12, 0.20, 0.045), 0.55)
    stem_mat = material("Natural brown stems", (0.10, 0.045, 0.018), 0.70)
    table_mat = material("Warm limestone tabletop", (0.72, 0.64, 0.51), 0.72)

    # One continuous, solid lathed section: pedestal -> outside -> thick lip -> interior.
    bowl_profile = [
        (0.0, 0.045), (0.38, 0.045), (0.52, 0.070), (0.55, 0.13),
        (0.52, 0.20), (0.36, 0.23), (0.30, 0.27), (0.30, 0.45),
        (0.45, 0.55), (0.65, 0.62), (1.00, 0.78), (1.30, 1.00),
        (1.50, 1.28), (1.54, 1.42), (1.52, 1.49), (1.46, 1.52),
        (1.40, 1.48), (1.38, 1.40), (1.22, 1.14), (0.98, 0.96),
        (0.65, 0.85), (0.30, 0.80), (0.0, 0.79),
    ]
    lathe("Thick-rimmed pedestal fruit bowl", bowl_profile, ceramic)

    left = fruit("Apple in bowl left", (-0.65, -0.28, 1.49), 0.58, 0.56, red,
                 rotation=(0.03, -0.11, -0.2))
    right = fruit("Apple in bowl right", (0.64, -0.25, 1.49), 0.56, 0.54, red,
                  rotation=(-0.08, 0.15, 0.3))
    pear = fruit("Pear in bowl back", (0.0, 0.59, 1.73), 0.52, 0.78, gold,
                 pear=True, rotation=(0.04, -0.15, -0.25))
    loose = fruit("Apple resting on table", (2.05, -0.70, 0.49), 0.49, 0.49, red,
                  rotation=(0.08, -0.22, -0.12))
    bpy.context.view_layer.update()
    lowest_point = min((loose.matrix_world @ vertex.co).z for vertex in loose.data.vertices)
    loose.location.z -= lowest_point
    stem("Left apple stem", left, 0.44, stem_mat)
    stem("Right apple stem", right, 0.42, stem_mat)
    stem("Pear stem", pear, 0.74, stem_mat, height=0.23, bend=0.065)
    stem("Table apple stem", loose, 0.37, stem_mat, height=0.19)
    leaf(pear, 0.84, leaf_mat)

    bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, 0))
    table = bpy.context.object
    table.name = "Seamless limestone table"
    table.data.materials.append(table_mat)

    scene = bpy.context.scene
    scene.world.use_nodes = True
    background = scene.world.node_tree.nodes.get("Background")
    background.inputs["Color"].default_value = (0.78, 0.74, 0.66, 1.0)
    background.inputs["Strength"].default_value = 0.45
    area_light("Large warm window key", (-3.5, -4.5, 7.0), 700, 4.0, (1.0, 0.88, 0.73))
    area_light("Soft neutral fill", (4.0, -1.0, 4.5), 140, 5.0, (0.84, 0.91, 1.0))
    area_light("Soft back rim", (0.0, 4.5, 6.0), 240, 3.5, (1.0, 0.94, 0.82))

    camera_data = bpy.data.cameras.new("Still-life camera")
    camera = bpy.data.objects.new("Still-life camera", camera_data)
    bpy.context.collection.objects.link(camera)
    camera.location = (5.8, -10.0, 6.4)
    aim(camera, (0.32, 0.0, 1.15))
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = 6.5
    camera_data.lens = 50
    scene.camera = camera

    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = max(1, args.samples)
    scene.cycles.seed = 19
    scene.cycles.use_denoising = True
    scene.render.resolution_x = 480
    scene.render.resolution_y = 360
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "8"
    scene.render.film_transparent = False
    scene.display_settings.display_device = "sRGB"
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.exposure = 0.25
    scene.render.filepath = str(output / "color-render.png")

    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(output / "fruit-vase.blend"))
    bpy.ops.render.render(write_still=True)
    print(f"FRUIT_VASE_RENDER_OK: {scene.render.filepath}; 480x360; Cycles CPU; {scene.cycles.samples} samples")


if __name__ == "__main__":
    main()
