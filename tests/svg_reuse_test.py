# Copyright 2020 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from picosvg.geometric_types import Vector
from picosvg.svg_types import SVGCircle, SVGPath, SVGRect
from picosvg.svg_transform import Affine2D
from picosvg.svg_reuse import _affine_friendly, _vectors, normalize, affine_between
import pytest


@pytest.mark.parametrize(
    "shape, tolerance, expected_normalization",
    [
        # Real example from Noto Emoji, eyes that were normalizing everything to have 0,0 coords
        # Caused by initial M and L having same coords, creating a 0-magnitude vec
        (
            SVGPath(
                d="M44.67,45.94 L44.67,45.94 C40.48,45.94 36.67,49.48 36.67,55.36 C36.67,61.24 40.48,64.77 44.67,64.77 L44.67,64.77 C48.86,64.77 52.67,61.23 52.67,55.36 C52.67,49.49 48.86,45.94 44.67,45.94 Z"
            ),
            0.1,
            "M0,0 l0,0 c0.2,-0.3 0.6,-0.3 1,0 c0.4,0.3 0.4,0.7 0.2,1 l0,0 c-0.2,0.3 -0.6,0.3 -1,0 c-0.4,-0.3 -0.4,-0.7 -0.2,-1 z",
        ),
        # https://github.com/googlefonts/picosvg/issues/249
        (SVGPath(d="M-1,-1 L 0,1 L 1, -1 z"), 0.1, "M0,0 l1,0 l-0.6,1 z"),
    ],
)
def test_svg_normalization(shape, tolerance, expected_normalization):
    normalized = normalize(shape, tolerance)
    assert normalized.round_floats(4).d == expected_normalization


@pytest.mark.parametrize(
    "path, expected_vectors",
    [
        # vectors for a box
        (
            "M10,10 h10 v10 h-10 z",
            (
                Vector(10.0, 10.0),
                Vector(10.0, 0.0),
                Vector(0.0, 10.0),
                Vector(-10.0, 0.0),
                Vector(0.0, 0.0),
            ),
        ),
        # observed problem: an arc whose start and end share a dimension is
        # taken to have 0 magnitude in that direction even if it bulges out
        # e.g. an arc from (1, 0) to (2, 0) is taken to have 0 magnitude on y
        # this may result in affine_between failures.
        # This is particularly problemmatic due to circles and ellipses in svg
        # converting to two arcs, one for the top and one for the bottom.
        # https://github.com/googlefonts/picosvg/issues/271
        (
            # arc from 0,0 to 2,0. Apex and farthest point at 1,0.5
            # vectors formed by start => farthest, farthest => end
            "M0,0 a 1 0.5 0 1 1 2,0",
            (
                Vector(0.0, 0.0),
                Vector(2.0, 0.0),
                Vector(0.0, 0.5),
            ),
        ),
        # https://github.com/googlefonts/picosvg/issues/271
        # As above, but on move on y, none on x
        (
            # arc from 0,0 to 0,2. Apex and farthest point at 0,0.5
            # vectors formed by start => farthest, farthest => end
            "M0,0 a 0.5 1 0 1 1 0,2",
            (
                Vector(0.0, 0.0),
                Vector(0.5, 0.0),
                Vector(0.0, 2.0),
            ),
        ),
        # https://github.com/googlefonts/picosvg/issues/271
        # Arc from Noto Emoji that was resulting in sqrt of a very small negative
        (
            "M0,0 a1.75 1.73 0 1 1 -3.5,0 a1.75 1.73 0 1 1 3.5,0 z",
            (
                Vector(0.0, 0.0),
                Vector(-3.5, 0.0),
                Vector(0.0, 1.73),
                Vector(3.5, 0.0),
                Vector(0.0, 1.73),
                Vector(0.0, 0.0),
            ),
        ),
    ],
)
def test_vectors_for_path(path, expected_vectors):
    assert (
        tuple(_vectors(_affine_friendly(SVGPath(d=path)))) == expected_vectors
    ), f"Wrong vectors for {path}"


@pytest.mark.parametrize(
    "s1, s2, expected_affine, tolerance",
    [
        # a rect and a circle can never be the same!
        (SVGRect(width=1, height=1), SVGCircle(r=1), None, 0.01),
        # same rect in the same place ftw
        (
            SVGRect(width=1, height=1),
            SVGRect(width=1, height=1),
            Affine2D.identity(),
            0.01,
        ),
        # same rect in the same place, different id
        (
            SVGRect(id="duck", width=1, height=1),
            SVGRect(id="duck", width=1, height=1),
            Affine2D.identity(),
            0.01,
        ),
        # same rect, offset
        (
            SVGRect(x=0, y=1, width=1, height=1),
            SVGRect(x=1, y=0, width=1, height=1),
            Affine2D.identity().translate(1, -1),
            0.01,
        ),
        # different rects
        (
            SVGRect(x=20, y=20, width=100, height=20),
            SVGRect(x=40, y=30, width=60, height=20),
            Affine2D(a=0.6, b=0.0, c=0.0, d=1.0, e=28.0, f=10.0),
            0.01,
        ),
        # circles that may happen to match the ones Noto clock emoji
        (
            SVGCircle(cx=15.89, cy=64.13, r=4),
            SVGCircle(cx=64.89, cy=16.13, r=4),
            Affine2D.identity().translate(49, -48),
            0.01,
        ),
        # path observed in wild to normalize but not compute affine_between
        # caused by failure to normalize equivalent d attributes in affine_between
        (
            SVGPath(
                fill="#99AAB5", d="M18 12H2 c-1.104 0-2 .896-2 2h20c0-1.104-.896-2-2-2z"
            ),
            SVGPath(
                fill="#99AAB5", d="M34 12H18c-1.104 0-2 .896-2 2h20c0-1.104-.896-2-2-2z"
            ),
            Affine2D.identity().translate(16, 0),
            0.01,
        ),
        # Triangles facing one another, same size
        (
            SVGPath(d="m60,64 -50,-32 0,30 z"),
            SVGPath(d="m68,64 50,-32 0,30 z"),
            Affine2D(-1.0, 0.0, 0.0, 1.0, 128.0, -0.0),
            0.01,
        ),
        # Triangles, different rotation, different size
        (
            SVGPath(d="m50,100 -48,-75 81,0 z"),
            SVGPath(d="m70,64 50,-32 0,54 z"),
            Affine2D(a=-0.0, b=0.6667, c=-0.6667, d=-0.0, e=136.6667, f=30.6667),
            0.01,
        ),
        # TODO triangles, one point stretched not aligned with X or Y
        # A square and a rect; different scale for each axis
        (
            SVGRect(x=10, y=10, width=50, height=50),
            SVGRect(x=70, y=20, width=20, height=100),
            Affine2D(a=0.4, b=0.0, c=0.0, d=2.0, e=66.0, f=0.0),
            0.01,
        ),
        # Squares with same first edge but flipped on Y
        (
            SVGPath(d="M10,10 10,60 60,60 60,10 z"),
            SVGPath(d="M70,120 90,120 90,20 70,20 z"),
            Affine2D(a=0.0, b=-2.0, c=0.4, d=0.0, e=66.0, f=140.0),
            0.01,
        ),
        # Real example from Noto Emoji (when tolerance was 0.1), works at 0.2
        # https://github.com/googlefonts/picosvg/issues/138
        (
            SVGPath(
                d="M98.267,28.379 L115.157,21.769 Q116.007,21.437 116.843,21.802 Q117.678,22.168 118.011,23.017 Q118.343,23.867 117.978,24.703 Q117.612,25.538 116.763,25.871 L99.873,32.481 Q99.023,32.813 98.187,32.448 Q97.352,32.082 97.019,31.233 Q96.687,30.383 97.052,29.547 Q97.418,28.712 98.267,28.379 Z"
            ),
            SVGPath(
                d="M81.097,20.35 L79.627,4.2 Q79.544,3.291 80.128,2.59 Q80.712,1.889 81.62,1.807 Q82.529,1.724 83.23,2.308 Q83.931,2.892 84.013,3.8 L85.483,19.95 Q85.566,20.859 84.982,21.56 Q84.398,22.261 83.49,22.343 Q82.581,22.426 81.88,21.842 Q81.179,21.258 81.097,20.35 Z"
            ),
            Affine2D(a=0.249, b=-0.859, c=0.859, d=0.249, e=32.255, f=97.667),
            0.2,
        ),
        # Real example from Noto Emoji, eyes that were normalizing everything to have 0,0 coords
        (
            SVGPath(
                d="M44.67,45.94L44.67,45.94 c-4.19,0-8,3.54-8,9.42 s3.81,9.41,8,9.41l0,0 c4.19,0,8-3.54,8-9.41 S48.86,45.94,44.67,45.94z"
            ),
            SVGPath(
                d="M83,45.94   L83,45.94    c-4.19,0-8,3.54-8,9.42 s3.81,9.41,8,9.41l0,0 c4.19,0,8-3.54,8-9.41 S87.21,45.94,83,45.94z"
            ),
            Affine2D.identity().translate(38.33, 0.0),
            0.1,
        ),
        # https://github.com/googlefonts/picosvg/issues/266 circles become arcs and don't normalize well
        (
            SVGCircle(r=2),
            SVGCircle(r=4),
            Affine2D.identity().scale(2.0),
            0.1,
        ),
        # Rectangles that should become one
        (
            SVGPath(d="M4,4 L8,4 L8,8 L4,8 L4,4 Z"),
            SVGPath(d="M2,2 L8,2 L8,4 L2,4 L2,2 Z"),
            Affine2D(1.5, 0, 0, 0.5, -4, 0),
            0.01,
        ),
        # https://github.com/googlefonts/picosvg/issues/271 arcs whose start/end match in a dimension fail
        # my arc is marginally taller than your arc
        (
            SVGPath(d="M0,0 a 1 0.5 0 1 1 2 0"),
            SVGPath(d="M0,0 a 1 1 0 1 1 2 0"),
            Affine2D.identity().scale(1, 2),
            0.01,
        ),
        # https://github.com/googlefonts/picosvg/issues/271 arcs whose start/end match in a dimension fail
        # Example that previously normalized the same but didn't find an affine between.
        (
            SVGPath(
                d="M104.64,10.08 A40.64 6.08 0 1 1 23.36,10.08 A40.64 6.08 0 1 1 104.64,10.08 Z"
            ),
            SVGPath(
                d="M99.63,23.34 A36.19 4.81 0 1 1 27.25,23.34 A36.19 4.81 0 1 1 99.63,23.34 Z"
            ),
            Affine2D(0.8905, 0.0, 0.0, 0.7911, 6.4479, 15.3655),
            0.01,
        ),
        # https://github.com/googlefonts/picosvg/issues/271 arcs whose start/end match in a dimension fail, ex2
        # Example that didn't even normalize the same previously.
        (
            SVGPath(
                d="M119.47,90.07 A55.47 10.49 0 1 1 8.53,90.07 A55.47 10.49 0 1 1 119.47,90.07 Z"
            ),
            SVGPath(
                d="M94.09,71.71 A12.2 3.92 0 1 1 69.69,71.71 A12.2 3.92 0 1 1 94.09,71.71 Z"
            ),
            Affine2D(0.2199, 0.0, 0.0, 0.3737, 67.8139, 38.0518),
            0.01,
        ),
    ],
)
def test_svg_reuse(s1, s2, expected_affine, tolerance):
    # if we can get an affine we should normalize to same shape
    if expected_affine:
        assert (
            normalize(s1, tolerance).d == normalize(s2, tolerance).d
        ), "should have normalized the same"
    else:
        assert (
            normalize(s1, tolerance).d != normalize(s2, tolerance).d
        ), "should NOT have normalized the same"

    affine = affine_between(s1, s2, tolerance)
    if expected_affine:
        assert (
            affine
        ), f"No affine found between {s1.as_path().d} and {s2.as_path().d}. Expected {expected_affine}"
        # Round because we've seen issues with different test environments when overly fine
        affine = affine.round(4)
    assert (
        affine == expected_affine
    ), f"Unexpected affine found between {s1.as_path().d} and {s2.as_path().d}."
