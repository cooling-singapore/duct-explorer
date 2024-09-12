from explorer.renderer.base import GeometriesRenderer


class ZoneRenderer(GeometriesRenderer):
    def get(self) -> dict:
        return {
            "type": "class-breaks",
            "classBreakInfos": [
                {
                    "minValue": 2,
                    "maxValue": 100,
                    "label": "Alternative zone configurations available",
                    "symbol": {
                        "type": "simple-fill",
                        "color": [75, 158, 244, 0.3],
                        "style": "solid",
                        "outline": {
                            "color": [75, 158, 244, 1.0],
                            "width": 1
                        }
                    }
                },
                {
                    # not used for rendering. Exists purely to appear on the legend and change the color of the mapz
                    "minValue": -1,
                    "maxValue": -1,
                    "label": "Alternative zone configuration selected",
                    "symbol": {
                        "type": "simple-fill",
                        "color": [233, 124, 76, 0.3],
                        "style": "solid",
                        "outline": {
                            "color": [233, 124, 76, 1.0],
                            "width": 1
                        }
                    }
                }
            ],
            "defaultLabel": "No alternative zone configurations available",
            "defaultSymbol": {
                "type": "simple-fill",
                "color": [255, 255, 255, 0],
                "style": "solid",
                "outline": {
                    "color": [255, 255, 255, 0.25],
                    "width": 1
                }
            },
            "field": "config_count",
            "legendOptions": {
                "title": "Alternative zone configurations"
            }
        }
