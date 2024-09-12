from explorer.renderer.base import NetworkRenderer


class DistrictCoolingNetworkRenderer(NetworkRenderer):
    def type(self) -> str:
        return 'district_cooling'

    def title(self) -> str:
        return 'District Cooling Network'

    def point_title(self) -> str:
        return 'Connections'

    def line_title(self) -> str:
        return 'Pipes'

    def line_color(self) -> str:
        return '#6db6d3'

    def line_thickness(self) -> str:
        return '4'

    def point_renderer(self) -> dict:
        return {
            "type": "unique-value",
            "field": "Type",
            "defaultSymbol": {
                "type": "simple-marker",
                "size": 0,
                "color": "#283244"
            },
            "defaultLabel": " ",
            "uniqueValueInfos": [
                {
                    "value": "NONE",
                    "symbol": {
                        "type": "simple-marker",
                        "size": 0
                    },
                    "label": " "
                },
                {
                    "value": "CONSUMER",
                    "symbol": {
                        "type": "point-3d",
                        "symbolLayers": [
                            {
                                "type": "icon",
                                "size": 12,
                                "resource": {"primitive": "circle"},
                                "material": {"color": "#FC921F"},
                                "outline": {"color": "white", "size": 1}
                            }
                        ]
                    },
                    "label": "Consumers"
                },
                {
                    "value": "PLANT",
                    "symbol": {
                        "type": "point-3d",
                        "symbolLayers": [
                            {
                                "type": "icon",
                                "size": 20,
                                "resource": {"primitive": "triangle"},
                                "material": {"color": "#2C98F0"},
                                "outline": {"color": "white", "size": 1}
                            }
                        ]
                    },
                    "label": "Plants"
                }
            ]
        }

    def line_renderer(self) -> dict:
        return {
            "type": "simple",
            "symbol": {
                "type": "simple-line",
                "color": self.line_color(),
                "width": self.line_thickness(),
                "style": "solid"
            },
            "visualVariables": [
                {
                    "type": "size",
                    "field": "Pipe_DN",
                    "label": " ",
                    "minDataValue": 20,
                    "maxDataValue": 1500,
                    "minSize": 2,
                    "maxSize": 10,
                    "legendOptions": {
                        "showLegend": False
                    }
                }
            ]

        }