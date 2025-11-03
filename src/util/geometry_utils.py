from affine import Affine
from shapely.affinity import affine_transform


def _to_shapely_matrix_from_affine(affine: Affine) -> list[float]:
    return [affine.a, affine.b, affine.d, affine.e, affine.xoff, affine.yoff]


def transform(geometry, matrix: Affine):
    return affine_transform(geometry, _to_shapely_matrix_from_affine(matrix))
