"""Read a north-up minimap heading from the player's yellow arrow silhouette."""

from math import sqrt

import cv2
import numpy as np


def arrow_silhouette(image):
    if image is None or image.ndim != 3 or image.shape[2] != 3:
        return None
    height, width = image.shape[:2]
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    yellow = cv2.inRange(hsv, np.array([15, 100, 190]), np.array([40, 255, 255]))
    # The arrow has a white highlight connected to its yellow border. Dropping
    # that core changes its silhouette as the lighting/antialiasing animates.
    white = cv2.inRange(hsv, np.array([0, 0, 220]), np.array([180, 100, 255]))
    mask = cv2.bitwise_or(yellow, white)
    count, labels, stats, centers = cv2.connectedComponentsWithStats(mask)
    if count < 2:
        return None
    index = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    area = stats[index, cv2.CC_STAT_AREA]
    center = centers[index]
    if (not .03 <= area / (height * width) <= .4
            or np.count_nonzero((labels == index) & (yellow > 0)) < area * .1
            or np.linalg.norm((center - [width / 2, height / 2]) / [width, height]) > .25):
        return None
    # Area normalization is independent of angle, unlike bounding-box resizing.
    scale = sqrt(600 / area)
    matrix = np.float64([[scale, 0, 32 - scale * center[0]], [0, scale, 32 - scale * center[1]]])
    component = np.where(labels == index, 255, 0).astype(np.uint8)
    return cv2.warpAffine(component, matrix, (64, 64)).astype(np.float32) / 255


def arrow_heading(image, east_template, cancel_check=None):
    """Return clockwise degrees from east and evidence, or a rejected heading.

    Uses the existing east-facing arrow asset. Both silhouettes share the same
    normalization; terrain and brightness outside yellow pixels have no vote.
    """
    query, template = arrow_silhouette(image), arrow_silhouette(east_template)
    if query is None or template is None:
        return None, {"reason": "missing_arrow"}
    scores = []
    for angle in range(360):
        if cancel_check:
            cancel_check()
        rotated = cv2.warpAffine(template, cv2.getRotationMatrix2D((32, 32), -angle, 1), (64, 64))
        denominator = np.sqrt(np.sum(rotated ** 2) * np.sum(query ** 2))
        scores.append(float(np.sum(rotated * query) / denominator) if denominator else 0)
    angle = int(np.argmax(scores))
    competitor = max(score for other, score in enumerate(scores)
                     if abs((other - angle + 180) % 360 - 180) > 30)
    evidence = {"angle": angle, "confidence": scores[angle], "margin": scores[angle] - competitor}
    accepted = scores[angle] >= .8 and evidence["margin"] >= .1
    evidence["reason"] = "corroborated_shape" if accepted else "weak_or_ambiguous_arrow"
    return (angle if accepted else None), evidence
