import math

from padamfirst import config


def test_score_weights_sum_to_one():
    assert math.isclose(sum(config.SCORE_WEIGHTS.values()), 1.0)


def test_class_thresholds_descend_to_zero():
    bounds = [bound for _, bound in config.CLASS_THRESHOLDS]
    assert bounds == sorted(bounds, reverse=True)
    assert bounds[-1] == 0


def test_bbox_is_ordered():
    west, south, east, north = config.BBOX_INDONESIA
    assert west < east and south < north
