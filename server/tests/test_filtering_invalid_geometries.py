import os.path
import unittest
import json
from duct.bdp import DUCTBaseDataPackageDB


class GeometryFilteringTestCase(unittest.TestCase):
    def filter_invalid_features(self, test_data_path: str) -> tuple:
        with open(test_data_path, 'r') as f:
            geojson_content = json.load(f)
            features = geojson_content['features']
            filtered_features = DUCTBaseDataPackageDB.filter_invalid_geometries(test_data_path, features)
        return features, filtered_features

    def extract_id_set_from_features(self, feature_list: list) -> set:
        id_set = set()
        for feature in feature_list:
            feature_id = str(feature['properties']['id'])
            id_set.add(feature_id)
        return id_set

    def test_has_duplicated_geometries(self):
        test_data_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 'data', 'duplicate_geometries', 'duplicated'
        )
        features, filtered_features = self.filter_invalid_features(test_data_path)
        raw_set = self.extract_id_set_from_features(features)
        filtered_set = self.extract_id_set_from_features(filtered_features)

        self.assertEqual(
            raw_set - filtered_set,
            {'152598430', '172023449', '172023457', '152598430', '172023449', '172023457'}
        )

    def test_has_non_duplicated_geometries(self):
        test_data_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 'data', 'duplicate_geometries', 'non_duplicated'
        )
        features, filtered_features = self.filter_invalid_features(test_data_path)

        raw_set = self.extract_id_set_from_features(features)
        filtered_set = self.extract_id_set_from_features(filtered_features)
        self.assertEqual(raw_set, filtered_set)

    def test_has_rotated_geometries(self):
        test_data_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 'data', 'duplicate_geometries', 'rotated'
        )
        features, filtered_features = self.filter_invalid_features(test_data_path)

        raw_set = self.extract_id_set_from_features(features)
        filtered_set = self.extract_id_set_from_features(filtered_features)
        self.assertEqual(raw_set, filtered_set)

    def test_has_non_polygon_geometries(self):
        test_data_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 'data', 'non_polygon_geometries', 'building_footprints'
        )
        features, filtered_features = self.filter_invalid_features(test_data_path)

        raw_set = self.extract_id_set_from_features(features)
        filtered_set = self.extract_id_set_from_features(filtered_features)
        self.assertTrue(raw_set - filtered_set, {'451950402'})


if __name__ == '__main__':
    unittest.main()
