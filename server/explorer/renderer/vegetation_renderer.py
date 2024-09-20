from explorer.renderer.base import GeometriesRenderer


class VegetationRenderer(GeometriesRenderer):
    def get(self) -> dict:
        return {
            "type": "unique-value",
            "field": "vegetation_type",
            "defaultLabel": "Unknown",
            "defaultSymbol": {
                "type": "web-style",
                "styleName": "EsriIconsStyle",
                "name": "Information"
            },
            "uniqueValueInfos": [
                {
                    "label": "Tree: Default",
                    "value": "tree:1",
                    "symbol": {
                        "type": "web-style",
                        "styleName": "EsriRealisticTreesStyle",
                        "name": "Tilia"
                    }
                },
                {
                    "label": "Tree: Acer",
                    "value": "tree:2",
                    "symbol": {
                        "type": "web-style",
                        "styleName": "EsriRealisticTreesStyle",
                        "name": "Acer"
                    }
                },
                {
                    "label": "Tree: Betula",
                    "value": "tree:7",
                    "symbol": {
                        "type": "web-style",
                        "styleName": "EsriRealisticTreesStyle",
                        "name": "Casuarina"
                    }
                },
                {
                    "label": "Tree: Gleditsia",
                    "value": "tree:36",
                    "symbol": {
                        "type": "web-style",
                        "styleName": "EsriRealisticTreesStyle",
                        "name": "Phoenix"
                    }
                },
                {
                    "label": "Tree: Sasa",
                    "value": "tree:73",
                    "symbol": {
                        "type": "web-style",
                        "styleName": "EsriRealisticTreesStyle",
                        "name": "Calocedrus"
                    }
                }
            ],
            "visualVariables": [
                {
                    "type": "size",
                    "axis": "height",
                    "field": "height",
                    "valueUnit": "meters",
                }
            ]
        }
