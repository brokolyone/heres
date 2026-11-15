"""Shared scene contract for the corridor-landscape Blender scene (Blender/bpy 5.3).

Units: metres, Z up. The corridor runs along +Y. The glass curtain wall is the
plane X = GLASS_X (left side when looking down +Y); everything with X < GLASS_X
is outdoors. The corridor floor is Z = 0; the outdoor field lies below it.

Every module exposes `build() -> dict` that ADDS objects to the current scene
(never resets it, never touches objects of other collections) and puts them in
its own collection obtained with `get_collection(NAME)`.
"""
import math
import bpy

# ---- corridor -------------------------------------------------------------
GLASS_X = -1.6          # glass plane (left wall)
RIGHT_WALL_X = 1.6      # solid right wall
FLOOR_Z = 0.0
CEILING_Z = 2.8
CORRIDOR_Y_MIN = -8.0   # behind the camera
CORRIDOR_Y_MAX = 70.0   # far end wall
MULLION_PITCH = 1.6     # spacing of vertical mullions along Y

# ---- outdoors -------------------------------------------------------------
GROUND_Z = -2.6                 # mean field level (building is raised)
FIELD_X_MIN, FIELD_X_MAX = -700.0, GLASS_X - 0.4
FIELD_Y_MIN, FIELD_Y_MAX = -150.0, 600.0
TREELINE_DISTANCE = 380.0       # approx. distance of the forest strip from origin
TERRAIN_OBJECT_NAME = "Terrain"  # mesh the grass is scattered on

# ---- camera (defaults, render module may fine tune) -------------------------
CAMERA_LOCATION = (0.95, 0.0, 1.55)
CAMERA_YAW_LEFT_DEG = 32.0      # rotated from +Y towards -X
CAMERA_PITCH_DEG = 0.0
CAMERA_LENS_MM = 24.0
RES_X, RES_Y = 2018, 946        # reference aspect 1009x473

# ---- sun ------------------------------------------------------------------
# Direction the light TRAVELS (from sun into scene): comes from outdoors (-X),
# from ahead-left of the camera, fairly high -> sun patches on the floor.
SUN_ELEVATION_DEG = 52.0
SUN_AZIMUTH_DEG = 300.0   # compass-style, 0 = +Y, 90 = +X  (i.e. sun sits towards -X/+Y)


def sun_direction_to_sun():
    """Unit vector pointing from the scene towards the sun."""
    el, az = math.radians(SUN_ELEVATION_DEG), math.radians(SUN_AZIMUTH_DEG)
    return (math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el))


def get_collection(name):
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(col)
    return col


def link_only_to(obj, col):
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    col.objects.link(obj)
