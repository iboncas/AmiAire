import cv2
import numpy as np

ROI_SETTINGS = {
    "gaussian_blur_kernel": (9, 9),
    "adaptive_thresh_block_size": 121,
    "adaptive_thresh_c": 2,
    "morph_open_kernel": (11, 11),
    "morph_close_kernel": (21, 21),
    "contour_area_min_ratio": 0.1,
    "contour_area_max_ratio": 0.7,
    "contour_similarity_threshold": 0.85,
    "corner_adjust_margin": 15,
}


def extract_roi_from_image_array(image_bgr: np.ndarray):
    if image_bgr is None or not isinstance(image_bgr, np.ndarray):
        raise ValueError("Input must be a valid BGR image")

    def order_points(pts):
        rect = np.zeros((4, 2), dtype="float32")

        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]
        rect[2] = pts[np.argmax(s)]

        diff = np.diff(pts, axis=1)
        rect[1] = pts[np.argmin(diff)]
        rect[3] = pts[np.argmax(diff)]

        return rect

    def warp_perspective(image, corners):
        corners = np.array(corners, dtype="float32").reshape(-1, 2)
        if corners.shape[0] != 4:
            raise ValueError("Expected exactly 4 corner points")

        rect = order_points(corners)
        (tl, tr, br, bl) = rect

        width_bottom = np.linalg.norm(br - bl)
        width_top = np.linalg.norm(tr - tl)
        max_width = int(max(width_bottom, width_top))

        height_right = np.linalg.norm(tr - br)
        height_left = np.linalg.norm(tl - bl)
        max_height = int(max(height_right, height_left))

        dst = np.array([
            [0, 0],
            [max_width - 1, 0],
            [max_width - 1, max_height - 1],
            [0, max_height - 1],
        ], dtype="float32")

        matrix = cv2.getPerspectiveTransform(rect, dst)
        return cv2.warpPerspective(image, matrix, (max_width, max_height))

    def refine_corners(gray_image, corners):
        corners = np.array(corners, dtype=np.float32)
        win_size = (5, 5)
        zero_zone = (-1, -1)
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 40, 0.001)
        corners_reshaped = corners.reshape(-1, 1, 2)
        refined = cv2.cornerSubPix(gray_image, corners_reshaped, win_size, zero_zone, criteria)
        return refined.reshape(-1, 2)

    def adjust_corners(corners, margin=15):
        centroid = np.mean(corners, axis=0)
        distances = np.linalg.norm(corners - centroid, axis=1, keepdims=True)
        if np.any(distances == 0):
            return corners
        return corners + margin * (centroid - corners) / distances

    color_image = image_bgr.copy()
    gray = cv2.cvtColor(color_image, cv2.COLOR_BGR2GRAY)
    gray_blurred = cv2.GaussianBlur(gray, ROI_SETTINGS["gaussian_blur_kernel"], 0)

    binary = cv2.adaptiveThreshold(
        gray_blurred,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        ROI_SETTINGS["adaptive_thresh_block_size"],
        ROI_SETTINGS["adaptive_thresh_c"],
    )

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, ROI_SETTINGS["morph_open_kernel"])
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=1)

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, ROI_SETTINGS["morph_close_kernel"])
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=1)

    contours, _ = cv2.findContours(binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    h, w = gray.shape[:2]
    max_image_area = h * w

    candidate_contours = []
    min_area = ROI_SETTINGS["contour_area_min_ratio"] * max_image_area
    max_area = ROI_SETTINGS["contour_area_max_ratio"] * max_image_area
    for cnt in contours:
        perimeter = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.02 * perimeter, True)
        if len(approx) == 4 and cv2.isContourConvex(approx):
            area = cv2.contourArea(approx)
            if min_area < area < max_area:
                candidate_contours.append(approx)

    candidate_contours.sort(key=cv2.contourArea, reverse=True)

    similarity_threshold = ROI_SETTINGS["contour_similarity_threshold"]
    inner_contour = None

    if len(candidate_contours) >= 2:
        chosen_pair_found = False
        for i in range(len(candidate_contours) - 1):
            area1 = cv2.contourArea(candidate_contours[i])
            area2 = cv2.contourArea(candidate_contours[i + 1])
            ratio = area2 / area1
            if ratio >= similarity_threshold:
                inner_contour = candidate_contours[i + 1]
                chosen_pair_found = True
                break
        if not chosen_pair_found:
            inner_contour = candidate_contours[0]
    elif len(candidate_contours) == 1:
        inner_contour = candidate_contours[0]
    elif len(contours) > 0:
        # Fallback: try minAreaRect on largest contours so photos with perspective can still work.
        largest_sorted = sorted(contours, key=cv2.contourArea, reverse=True)[:10]
        for largest in largest_sorted:
            rect = cv2.minAreaRect(largest)
            box = cv2.boxPoints(rect).astype(np.int32).reshape(-1, 1, 2)
            area = cv2.contourArea(box)
            if min_area < area < max_area:
                inner_contour = box
                break

    roi = None
    if inner_contour is not None:
        try:
            corners = np.squeeze(inner_contour, axis=1).astype(np.float32)
            refined_corners = refine_corners(gray_blurred, corners)
            adjusted_corners = adjust_corners(refined_corners, margin=ROI_SETTINGS["corner_adjust_margin"])
            roi = warp_perspective(color_image, adjusted_corners)
        except cv2.error:
            roi = None

    image_with_contour = color_image.copy()
    if inner_contour is not None:
        cv2.drawContours(image_with_contour, [inner_contour], -1, (0, 255, 0), 2)

    if roi is None:
        return None, None

    return image_with_contour, roi
