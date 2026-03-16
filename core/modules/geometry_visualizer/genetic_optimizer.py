from vpython import scene, quad, curve, vertex, color, vector
from Geometry3D import Point

from core.models.geometry import Geometry
from core.pipeline.base import Module


def point_to_vector(point: Point) -> vector:
    return vector(point.x, point.y, point.z)


class GeometryVisualizerModule(Module[Geometry, Geometry]):
    def process(self, data: Geometry) -> Geometry:
        scene.title = "Geometry 3D view"
        scene.range = 10
        scene.background = color.gray(0.8)
        scene.width = 1200
        scene.height = 800
        scene.up = vector(0, 0, 1)
        scene.forward = point_to_vector(data.cuts[0].start_bottom)

        top_color = color.yellow
        bottom_color = color.red

        for i, cut in enumerate(data.cuts):
            cut_vectors = [
                point_to_vector(point)
                for point in [
                    cut.start_top,
                    cut.start_bottom,
                    cut.end_bottom,
                    cut.end_top,
                ]
            ]

            cut_vectors = {
                k: v
                for k, v in zip(
                    ["start_top", "start_bottom", "end_bottom", "end_top"], cut_vectors
                )
            }

            if cut.is_straight_cut():
                quad(
                    vs=[
                        vertex(pos=vec, color=color.orange)
                        for vec in cut_vectors.values()
                    ],
                    opacity=1,
                    retain=1,
                )
            else:
                quad(
                    v0=vertex(pos=cut_vectors["start_bottom"], color=bottom_color),
                    v1=vertex(pos=cut_vectors["end_bottom"], color=bottom_color),
                    v2=vertex(pos=cut_vectors["end_top"], color=top_color),
                    v3=vertex(pos=cut_vectors["start_top"], color=top_color),
                    opacity=1,
                    retain=1,
                )

            outline_points = list(cut_vectors.values())
            outline_points.append(outline_points[0])
            curve(pos=outline_points, color=color.black, radius=0.03)

        return data
