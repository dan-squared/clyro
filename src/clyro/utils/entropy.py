import math
from PIL import Image

def calculate_shannon_entropy(img: Image.Image) -> float:
    """
    Calculate the Shannon entropy of an image using all RGB channels.

    Computes per-channel histograms for R, G, B and sums entropy across
    all three channels (total_pixels = W * H * 3).  This gives a more
    accurate measure than grayscale-only for colour images.

    High entropy → lots of detail/noise (better for JPEG).
    Low  entropy → flat areas/simple graphics (better for PNG).
    """
    # Normalise to RGB so we always have 3 channels
    rgb = img.convert("RGB") if img.mode != "RGB" else img

    width, height = rgb.size
    total_pixels = width * height * 3  # 3 channels

    if total_pixels == 0:
        return 0.0

    # Pillow histogram() on an RGB image returns [R0..R255, G0..G255, B0..B255]
    histogram = rgb.histogram()

    entropy = 0.0
    for count in histogram:
        if count > 0:
            probability = count / total_pixels
            entropy -= probability * math.log2(probability)

    return entropy

def large_area_entropy(img: Image.Image, threshold: int = 1_000_000) -> float | None:
    """Return entropy only if the image area exceeds *threshold* pixels.

    Small images produce unreliable entropy values, so this helper mirrors
    The ``largeAreaEntropy`` property.
    """
    w, h = img.size
    if w * h > threshold:
        return calculate_shannon_entropy(img)
    return None
