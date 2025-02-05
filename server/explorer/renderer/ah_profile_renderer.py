from explorer.renderer.base import Renderer, hex_color_to_components


class AHProfileRenderer(Renderer):
    def type(self) -> str:
        return 'ah_profile'

    def title(self) -> str:
        return 'AH Profile Renderer'

    def renderer(self, title, field, legend_title, show_outline) -> dict:
        return {
            "type": "class-breaks",
            "title": title,
            "field": field,
            "legendOptions": {
                "showLegend": True,
                "title": legend_title
            },
            "classBreakInfos": [
                {
                    "minValue": 0,
                    "maxValue": 10,
                    "label": "0 - 10",
                    "symbol": {
                        "type": "simple-fill",
                        "color": hex_color_to_components('#BFB298', 0.6),
                        "style": "solid",
                        "outline": {
                            "color": hex_color_to_components('#ffffff', 1.0),
                            "width": 1 if show_outline else 0
                        }
                    }
                },
                {
                    "minValue": 10,
                    "maxValue": 20,
                    "label": "10 - 20",
                    "symbol": {
                        "type": "simple-fill",
                        "color": hex_color_to_components('#8AEDF3', 0.8),
                        "style": "solid",
                        "outline": {
                            "color": hex_color_to_components('#ffffff', 1.0),
                            "width": 1 if show_outline else 0
                        }
                    }
                },
                {
                    "minValue": 20,
                    "maxValue": 30,
                    "label": "20 - 30",
                    "symbol": {
                        "type": "simple-fill",
                        "color": hex_color_to_components('#00ABEC', 0.8),
                        "style": "solid",
                        "outline": {
                            "color": hex_color_to_components('#ffffff', 1.0),
                            "width": 1 if show_outline else 0
                        }
                    }
                },
                {
                    "minValue": 30,
                    "maxValue": 50,
                    "label": "30 - 50",
                    "symbol": {
                        "type": "simple-fill",
                        "color": hex_color_to_components('#049D4F', 0.8),
                        "style": "solid",
                        "outline": {
                            "color": hex_color_to_components('#ffffff', 1.0),
                            "width": 1 if show_outline else 0
                        }
                    }
                },
                {
                    "minValue": 50,
                    "maxValue": 100,
                    "label": "50 - 100",
                    "symbol": {
                        "type": "simple-fill",
                        "color": hex_color_to_components('#5B9D1C', 0.8),
                        "style": "solid",
                        "outline": {
                            "color": hex_color_to_components('#ffffff', 1.0),
                            "width": 1 if show_outline else 0
                        }
                    }
                },
                {
                    "minValue": 100,
                    "maxValue": 500,
                    "label": "100 - 500",
                    "symbol": {
                        "type": "simple-fill",
                        "color": hex_color_to_components('#AFD037', 0.8),
                        "style": "solid",
                        "outline": {
                            "color": hex_color_to_components('#ffffff', 1.0),
                            "width": 1 if show_outline else 0
                        }
                    }
                },
                {
                    "minValue": 500,
                    "maxValue": 1000,
                    "label": "500 - 1000",
                    "symbol": {
                        "type": "simple-fill",
                        "color": hex_color_to_components('#FFF000', 0.8),
                        "style": "solid",
                        "outline": {
                            "color": hex_color_to_components('#ffffff', 1.0),
                            "width": 1 if show_outline else 0
                        }
                    }
                },
                {
                    "minValue": 1000,
                    "maxValue": 12000,
                    "label": "1000 - 12000",
                    "symbol": {
                        "type": "simple-fill",
                        "color": hex_color_to_components('#FBC707', 0.8),
                        "style": "solid",
                        "outline": {
                            "color": hex_color_to_components('#ffffff', 1.0),
                            "width": 1 if show_outline else 0
                        }
                    }
                },
                {
                    "minValue": 12000,
                    "maxValue": 14000,
                    "label": "12000 - 14000",
                    "symbol": {
                        "type": "simple-fill",
                        "color": hex_color_to_components('#F7A20D', 0.8),
                        "style": "solid",
                        "outline": {
                            "color": hex_color_to_components('#ffffff', 1.0),
                            "width": 1 if show_outline else 0
                        }
                    }
                },
                {
                    "minValue": 14000,
                    "maxValue": 16000,
                    "label": "14000 - 16000",
                    "symbol": {
                        "type": "simple-fill",
                        "color": hex_color_to_components('#F37A14', 0.8),
                        "style": "solid",
                        "outline": {
                            "color": hex_color_to_components('#ffffff', 1.0),
                            "width": 1 if show_outline else 0
                        }
                    }
                },
                {
                    "minValue": 16000,
                    "maxValue": 18000,
                    "label": "16000 - 18000",
                    "symbol": {
                        "type": "simple-fill",
                        "color": hex_color_to_components('#EF551A', 0.8),
                        "style": "solid",
                        "outline": {
                            "color": hex_color_to_components('#ffffff', 1.0),
                            "width": 1 if show_outline else 0
                        }
                    }
                },
                {
                    "minValue": 18000,
                    "maxValue": 100000,
                    "label": "18000 - 100000",
                    "symbol": {
                        "type": "simple-fill",
                        "color": hex_color_to_components('#EA1C24', 0.8),
                        "style": "solid",
                        "outline": {
                            "color": hex_color_to_components('#ffffff', 1.0),
                            "width": 1 if show_outline else 0
                        }
                    }
                },
                {
                    "minValue": 100000,
                    "maxValue": 999999999999,
                    "label": ">= 100000",
                    "symbol": {
                        "type": "simple-fill",
                        "color": hex_color_to_components('#C4171E', 0.8),
                        "style": "solid",
                        "outline": {
                            "color": hex_color_to_components('#ffffff', 1.0),
                            "width": 1 if show_outline else 0
                        }
                    }
                }
            ]
        }

