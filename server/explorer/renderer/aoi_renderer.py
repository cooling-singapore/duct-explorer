from explorer.renderer.base import GeometriesRenderer


class AreaOfInterestRenderer(GeometriesRenderer):
    def get(self) -> dict:
        return {
            "type": "simple",
            "label": "Area of Interest",
            "symbol": {
                "type": "simple-fill",
                "color": [255, 50, 50, 0.25],
                "style": "solid",
                "outline": {
                    "color": [255, 50, 50, 0.75],
                    "width": 1
                }
            }
        }
