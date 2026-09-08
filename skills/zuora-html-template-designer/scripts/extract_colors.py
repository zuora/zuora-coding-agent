#!/usr/bin/env python3
"""
Color extraction tool for Zuora Template Designer.

Extracts exact hex colors from PNG images to ensure accurate color reproduction
in HTML templates. This addresses the font color issue by providing precise
color values instead of generic defaults.

Usage:
    python extract_colors.py --image path/to/image.png --output colors.json
    python extract_colors.py --image path/to/image.png --region header --x 100 --y 50 --w 200 --h 30
"""

import argparse
import json
import logging
from typing import Dict, List, Tuple, Any
from PIL import Image
from collections import Counter
import colorsys

logger = logging.getLogger(__name__)

try:
    import numpy as np  # Optional optimization
except ImportError:  # pragma: no cover - depends on runtime image
    np = None


def _to_json_safe(value: Any) -> Any:
    """Recursively convert numpy values into JSON-safe Python types."""
    if isinstance(value, dict):
        return {k: _to_json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_json_safe(v) for v in value]
    if np is not None:
        if isinstance(value, np.integer):
            return int(value)
        if isinstance(value, np.floating):
            return float(value)
        if isinstance(value, np.ndarray):
            return _to_json_safe(value.tolist())
    return value


def _get_rgb_pixels(image: Image.Image) -> List[Tuple[int, int, int]]:
    """
    Return RGB pixels as tuples without relying on deprecated PIL APIs.
    """
    # Use raw bytes to avoid deprecated getdata() and API differences across
    # Pillow versions/runtimes.
    rgb_image = image if image.mode == "RGB" else image.convert("RGB")
    raw = rgb_image.tobytes()
    return [(raw[i], raw[i + 1], raw[i + 2]) for i in range(0, len(raw), 3)]

class ColorExtractor:
    """Extracts precise colors from PNG images for template generation."""

    def __init__(self, image_path: str):
        self.image_path = image_path
        self.image = Image.open(image_path).convert('RGB')
        self.image_array = np.array(self.image) if np is not None else None

    def rgb_to_hex(self, rgb: Tuple[int, int, int]) -> str:
        """Convert RGB tuple to hex color string."""
        return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"

    def get_dominant_colors(self, region: Any = None, n_colors: int = 5) -> List[Dict[str, Any]]:
        """Extract dominant colors from image or region."""
        if region is None:
            if self.image_array is not None:
                region = self.image_array
            else:
                region = _get_rgb_pixels(self.image)

        # Flatten pixels and normalize channels to native Python ints
        if np is not None and isinstance(region, np.ndarray):
            pixels = [tuple(int(c) for c in px) for px in region.reshape(-1, 3)]
        else:
            pixels = [tuple(int(c) for c in px[:3]) for px in region]

        # Remove white and near-white pixels (background)
        non_white_pixels = [px for px in pixels if sum(px) < 240 * 3]

        if len(non_white_pixels) == 0:
            return [{"hex": "#ffffff", "count": 1, "percentage": 100.0, "description": "white"}]

        # Count color occurrences
        top_colors = Counter(non_white_pixels).most_common(n_colors)

        total_pixels = len(non_white_pixels)
        dominant_colors = []

        for rgb, count in top_colors:
            hex_color = self.rgb_to_hex(rgb)
            percentage = (count / total_pixels) * 100

            # Generate color description
            description = self.describe_color(rgb)

            dominant_colors.append({
                "hex": hex_color,
                "rgb": rgb,
                "count": int(count),
                "percentage": float(round(percentage, 2)),
                "description": description
            })

        return dominant_colors

    def describe_color(self, rgb: Tuple[int, int, int]) -> str:
        """Generate human-readable color description."""
        r, g, b = rgb

        # Convert to HSV for better color categorization
        h, s, v = colorsys.rgb_to_hsv(r/255, g/255, b/255)
        h = h * 360  # Convert to degrees
        s = s * 100  # Convert to percentage
        v = v * 100  # Convert to percentage

        # Determine base color
        if s < 10:  # Very low saturation = grayscale
            if v > 80:
                return "very light gray"
            elif v > 60:
                return "light gray"
            elif v > 40:
                return "medium gray"
            elif v > 20:
                return "dark gray"
            else:
                return "very dark gray"

        # Color wheel mapping
        if h < 15 or h >= 345:
            base = "red"
        elif h < 45:
            base = "orange"
        elif h < 75:
            base = "yellow"
        elif h < 105:
            base = "yellow-green"
        elif h < 135:
            base = "green"
        elif h < 165:
            base = "blue-green"
        elif h < 195:
            base = "cyan"
        elif h < 225:
            base = "blue"
        elif h < 255:
            base = "blue-purple"
        elif h < 285:
            base = "purple"
        elif h < 315:
            base = "magenta"
        else:
            base = "pink"

        # Add lightness modifier
        if v > 80:
            modifier = "very light"
        elif v > 60:
            modifier = "light"
        elif v > 40:
            modifier = "medium"
        elif v > 20:
            modifier = "dark"
        else:
            modifier = "very dark"

        # Add saturation modifier
        if s < 30:
            saturation = "muted"
        elif s > 80:
            saturation = "vivid"
        else:
            saturation = ""

        # Combine descriptions
        parts = [p for p in [modifier, saturation, base] if p]
        return " ".join(parts)

    def extract_region_colors(self, x: int, y: int, width: int, height: int,
                            region_name: str = "region") -> Dict[str, Any]:
        """Extract colors from a specific region of the image."""
        # Ensure coordinates are within image bounds
        x = max(0, min(x, self.image.width - 1))
        y = max(0, min(y, self.image.height - 1))
        width = min(width, self.image.width - x)
        height = min(height, self.image.height - y)

        # Extract region
        if self.image_array is not None:
            region = self.image_array[y:y+height, x:x+width]
        else:
            region = _get_rgb_pixels(self.image.crop((x, y, x + width, y + height)))

        # Get dominant colors
        colors = self.get_dominant_colors(region)

        return {
            "region": region_name,
            "coordinates": {"x": x, "y": y, "width": width, "height": height},
            "dominant_colors": colors,
            "recommended_text_color": colors[0]["hex"] if colors else "#000000",
            "recommended_background": "#ffffff"
        }

    def analyze_text_regions(self) -> Dict[str, Any]:
        """Analyze common text regions and extract their colors."""
        width, height = self.image.size

        results = {
            "image_info": {
                "path": self.image_path,
                "dimensions": {"width": width, "height": height}
            },
            "regions": {}
        }

        # Define common regions based on typical invoice layout
        regions = {
            "header_title": {"x": width//4, "y": 20, "width": width//2, "height": 60},
            "company_info": {"x": 40, "y": height//8, "width": width//3, "height": height//4},
            "invoice_details": {"x": width*2//3, "y": height//8, "width": width//3, "height": height//4},
            "table_header": {"x": 40, "y": height//2, "width": width-80, "height": 30},
            "table_data": {"x": 40, "y": height//2 + 40, "width": width-80, "height": 100},
        }

        for region_name, coords in regions.items():
            try:
                region_result = self.extract_region_colors(
                    coords["x"], coords["y"], coords["width"], coords["height"],
                    region_name
                )
                results["regions"][region_name] = region_result
            except Exception as e:
                logger.warning(f"Failed to analyze region {region_name}: {e}")

        # Add overall image analysis
        overall_colors = self.get_dominant_colors()
        results["overall_colors"] = overall_colors

        return results

def main():
    parser = argparse.ArgumentParser(description='Extract colors from PNG images')
    parser.add_argument('--image', required=True, help='Path to PNG image')
    parser.add_argument('--output', help='Output JSON file (default: print to stdout)')
    parser.add_argument('--region', help='Region name for targeted extraction')
    parser.add_argument('--x', type=int, help='X coordinate for region extraction')
    parser.add_argument('--y', type=int, help='Y coordinate for region extraction')
    parser.add_argument('--w', '--width', type=int, help='Width for region extraction')
    parser.add_argument('--h', '--height', type=int, help='Height for region extraction')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.INFO)

    try:
        extractor = ColorExtractor(args.image)

        if all(coord is not None for coord in [args.x, args.y, args.w, args.h]):
            # Extract specific region
            result = extractor.extract_region_colors(
                args.x, args.y, args.w, args.h, args.region or "custom_region"
            )
        else:
            # Full image analysis
            result = extractor.analyze_text_regions()

        # Output results
        output_json = json.dumps(_to_json_safe(result), indent=2)

        if args.output:
            with open(args.output, 'w') as f:
                f.write(output_json)
            print(f"✅ Color analysis saved to {args.output}")
        else:
            print(output_json)

    except Exception as e:
        print(f"❌ Error: {e}")
        return 1

    return 0

if __name__ == '__main__':
    exit(main())