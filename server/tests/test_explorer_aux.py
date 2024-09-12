import datetime
import logging
import os
import shutil
import time
import unittest
from zoneinfo import ZoneInfo

from saas.core.logging import Logging
from tests.base_testcase import create_wd

from duct.analyses.mesoscale_urban_climate import determine_time_period

from explorer.analysis.base import Analysis
from explorer.cache import Cache
from explorer.module.base import BuildModule
from explorer.server import ExplorerServer


Logging.initialise(logging.INFO)
logger = Logging.get(__name__, level=logging.DEBUG)

nextcloud_path = os.path.join(os.environ['HOME'], 'Nextcloud', 'DT-Lab', 'Testing')


class AuxTestCase(unittest.TestCase):
    def setUp(self):
        self._wd_path = create_wd()

    def tearDown(self):
        shutil.rmtree(self._wd_path, ignore_errors=True)

    def test_determine_time_period(self):
        date = '2016-04-17'

        t_local = date.split('-')
        t_local = datetime.datetime(int(t_local[0]), int(t_local[1]), int(t_local[2]), 0, 0, 0, 0,
                                    tzinfo=ZoneInfo('Asia/Singapore'))

        t_utc = t_local.astimezone(ZoneInfo('UTC'))
        t_utc = t_utc.strftime('%Y%m%d%H%M%S')

        dt_warmup = 0
        dt_sim = 6

        t_table, ti, t_from, t_to = determine_time_period(logger, t_utc, dt_warmup, dt_sim)
        print(t_table)
        print(ti)
        print(t_from)
        print(t_to)

    def test_search_for_classes(self):
        domains = ['duct', 'infrarisk']

        # add all known analyses
        classes = []
        for c in ExplorerServer.search_for_classes([f"{d}.analyses" for d in domains], Analysis):
            classes.append(c.__name__)
        print(f"classes({len(classes)}): {classes}")
        assert(len(classes) > 0)

        # add all build modules
        classes = []
        for c in ExplorerServer.search_for_classes([f"{d}.modules" for d in domains], BuildModule):
            classes.append(c.__name__)
        print(f"classes({len(classes)}): {classes}")
        assert(len(classes) > 0)

    def test_cache_pruning(self):
        Cache.create(self._wd_path, 2, 10)

        # create two cache objects
        id0 = "0"
        id1 = "1"
        Cache.instance().json(id0, {'a': 0})
        Cache.instance().json(id1, {'a': 1})

        time.sleep(5)

        # the cache should still find the object
        obj0 = Cache.instance().json(id0)
        obj1 = Cache.instance().json(id1)
        assert obj0 is not None
        assert obj1 is not None

        # access content of object 1 -> should reset its last seen timestamp
        obj1.content()

        time.sleep(7)

        # obj0 should have expired
        obj0 = Cache.instance().json(id0)
        obj1 = Cache.instance().json(id1)
        assert obj0 is None
        assert obj1 is not None

    # TODO: not really a test case -> move this code somewhere else eventually
    # def test_convert_geojson_to_gltf(self):
    #     import pygltflib
    #     import numpy as np
    #     from stl import mesh
    #     from math import sqrt
    #     import gmsh
    #
    #     def create_mesh(geojson_path: str, output_path: str, s_lon: float, s_lat: float, s_height: float,
    #                     lc: float) -> (float, float):
    #         # read building footprints
    #         objects = []
    #         with open(geojson_path, 'r') as f:
    #             geojson = json.load(f)
    #             for feature in geojson['features']:
    #                 geometry = feature['geometry']
    #                 properties = feature['properties']
    #
    #                 # extract height
    #                 height = float(properties['height']) if 'height' in properties else 0
    #                 if height == 0:
    #                     print(f"feature {properties['id']}/{properties['name']} does not have a height -> skipping")
    #                     continue
    #
    #                 # handle MultiPolygon
    #                 if geometry['type'] == 'MultiPolygon':
    #                     geometry['coordinates'] = geometry['coordinates'][0]
    #                     geometry['type'] = 'Polygon'
    #
    #                 # skip non-polygon geometries
    #                 if geometry['type'] != 'Polygon':
    #                     print(f"feature {properties['id']}/{properties['name']} is not a "
    #                           f"polygon geometry but '{geometry['type']}' -> skipping")
    #                     continue
    #
    #                 # iterate over all polygons
    #                 for polygon in geometry['coordinates']:
    #                     # check if first and last point are same/close -> if so, remove the last point
    #                     p0 = polygon[0]
    #                     p1 = polygon[-1]
    #                     if int(p0[0] * 1000) == int(p1[0] * 1000) and int(p0[1] * 1000) == int(p1[1] * 1000):
    #                         polygon = polygon[:-1]
    #
    #                     # determine lons/lats min/max and add object
    #                     lons = [p[0] for p in polygon]
    #                     lats = [p[1] for p in polygon]
    #                     objects.append({
    #                         'coords': polygon,
    #                         'lon_range': (min(lons), max(lons)),
    #                         'lat_range': (min(lats), max(lats)),
    #                         'height': height
    #                     })
    #
    #         # determine lon/lat offsets
    #         lon_range = (min([obj['lon_range'][0] for obj in objects]), max([obj['lon_range'][1] for obj in objects]))
    #         lat_range = (min([obj['lat_range'][0] for obj in objects]), max([obj['lat_range'][1] for obj in objects]))
    #         offset_lon = lon_range[0] + (lon_range[1] - lon_range[0]) / 2
    #         offset_lat = lat_range[0] + (lat_range[1] - lat_range[0]) / 2
    #
    #         # initialise gmsh
    #         gmsh.initialize()
    #
    #         # create solid objects
    #         all_x = []
    #         all_y = []
    #         for obj in objects:
    #             n = len(obj['coords'])
    #
    #             # create points at height 0 (bottom) and H (top - according to height)
    #             points0 = []
    #             pointsH = []
    #             for coord in obj['coords']:
    #                 # apply the offset and scaling factor to center the building footprints around (0, 0)
    #                 x = (coord[0] - offset_lon) * s_lon
    #                 y = (coord[1] - offset_lat) * s_lat
    #                 points0.append(gmsh.model.geo.add_point(x, y, 0, lc))
    #                 pointsH.append(gmsh.model.geo.add_point(x, y, obj['height'] * s_height, lc))
    #
    #                 all_x.append(x)
    #                 all_y.append(y)
    #
    #             # create lines (on bottom and top that resemble the footprint and vertical lines that connect
    #             # top and bottom)
    #             lines0 = []
    #             linesH = []
    #             linesV = []
    #             for i in range(n):
    #                 j = (i + 1) % n
    #                 lines0.append(gmsh.model.geo.add_line(points0[i], points0[j]))
    #                 linesH.append(gmsh.model.geo.add_line(pointsH[i], pointsH[j]))
    #                 linesV.append(gmsh.model.geo.add_line(points0[i], pointsH[i]))
    #
    #             # create side surfaces
    #             for i in range(n):
    #                 j = (i + 1) % n
    #                 face = gmsh.model.geo.add_curve_loop([lines0[i], linesV[j], -linesH[i], -linesV[i]])
    #                 gmsh.model.geo.add_plane_surface([face])
    #
    #             # create bottom/top surfaces
    #             face0 = gmsh.model.geo.add_curve_loop(lines0)
    #             faceH = gmsh.model.geo.add_curve_loop(linesH)
    #             gmsh.model.geo.add_plane_surface([face0])
    #             gmsh.model.geo.add_plane_surface([faceH])
    #
    #         # generate mesh
    #         gmsh.model.geo.synchronize()
    #         gmsh.model.mesh.generate()
    #
    #         # write mesh data:
    #         gmsh.write(output_path)
    #
    #         gmsh.finalize()
    #
    #         return offset_lon, offset_lat
    #
    #
    #     geojson_path = os.path.join(nextcloud_path, 'bdpimport_geo', 'output', 'building-footprints-tengah_subset1')
    #     stl_file_path = os.path.join(os.environ['HOME'], 'Desktop', 'test.stl')
    #     glb_file_path = os.path.join(os.environ['HOME'], 'Desktop', 'test.glb')
    #
    #     create_mesh(geojson_path, stl_file_path, 111000, 111000, 1, 0)
    #
    #     def normalize(vector):
    #         norm = 0
    #         for i in range(0, len(vector)):
    #             norm += vector[i] * vector [i]
    #         norm = sqrt(norm)
    #         for i in range(0, len(vector)):
    #             vector[i] = vector[i] / norm
    #
    #         return vector
    #
    #     stl_mesh = mesh.Mesh.from_file(stl_file_path)
    #
    #     stl_points = []
    #     for i in range(0, len(stl_mesh.points)): # Convert points into correct numpy array
    #         stl_points.append([stl_mesh.points[i][0],stl_mesh.points[i][1],stl_mesh.points[i][2]])
    #         stl_points.append([stl_mesh.points[i][3],stl_mesh.points[i][4],stl_mesh.points[i][5]])
    #         stl_points.append([stl_mesh.points[i][6],stl_mesh.points[i][7],stl_mesh.points[i][8]])
    #
    #     points = np.array(
    #         stl_points,
    #         dtype="float32",
    #     )
    #
    #     stl_normals = []
    #     for i in range(0, len(stl_mesh.normals)): # Convert points into correct numpy array
    #         normal_vector = [stl_mesh.normals[i][0],stl_mesh.normals[i][1],stl_mesh.normals[i][2]]
    #         normal_vector = normalize(normal_vector)
    #         stl_normals.append(normal_vector)
    #         stl_normals.append(normal_vector)
    #         stl_normals.append(normal_vector)
    #
    #     normals = np.array(
    #         stl_normals,
    #         dtype="float32"
    #     )
    #
    #     points_binary_blob = points.tobytes()
    #     normals_binary_blob = normals.tobytes()
    #
    #     gltf = pygltflib.GLTF2(
    #         scene=0,
    #         scenes=[pygltflib.Scene(nodes=[0])],
    #         nodes=[pygltflib.Node(mesh=0)],
    #         meshes=[
    #             pygltflib.Mesh(
    #                 primitives=[
    #                     pygltflib.Primitive(
    #                         attributes=pygltflib.Attributes(POSITION=0, NORMAL=1), indices=None
    #                     )
    #                 ]
    #             )
    #         ],
    #         accessors=[
    #             pygltflib.Accessor(
    #                 bufferView=0,
    #                 componentType=pygltflib.FLOAT,
    #                 count=len(points),
    #                 type=pygltflib.VEC3,
    #                 max=points.max(axis=0).tolist(),
    #                 min=points.min(axis=0).tolist(),
    #             ),
    #             pygltflib.Accessor(
    #                 bufferView=1,
    #                 componentType=pygltflib.FLOAT,
    #                 count=len(normals),
    #                 type=pygltflib.VEC3,
    #                 max=None,
    #                 min=None,
    #             ),
    #         ],
    #         bufferViews=[
    #             pygltflib.BufferView(
    #                 buffer=0,
    #                 byteOffset=0,
    #                 byteLength=len(points_binary_blob),
    #                 target=pygltflib.ARRAY_BUFFER,
    #             ),
    #             pygltflib.BufferView(
    #                 buffer=0,
    #                 byteOffset=len(points_binary_blob),
    #                 byteLength=len(normals_binary_blob),
    #                 target=pygltflib.ARRAY_BUFFER,
    #             ),
    #         ],
    #         buffers=[
    #             pygltflib.Buffer(
    #                 byteLength=len(points_binary_blob) + len(normals_binary_blob)
    #             )
    #         ],
    #     )
    #     gltf.set_binary_blob(points_binary_blob + normals_binary_blob)
    #     gltf.save(glb_file_path)


if __name__ == '__main__':
    unittest.main()
