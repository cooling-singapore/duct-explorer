from explorer.renderer.base import GeometriesRenderer


class LanduseRenderer(GeometriesRenderer):
    def get(self) -> dict:
        return {
            "type": "unique-value",
            "field": "landuse_type",
            "defaultLabel": "Other",
            "defaultSymbol": {
                "type": "simple-fill",
                "color": [255, 255, 255, 0.3],
                "style": "solid",
                "outline": {
                    "color": [110, 179, 240, 1.0],
                    "width": 1
                }
            },
            "uniqueValueInfos": [
            ]
        }
