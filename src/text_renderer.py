"""
Text rendering for video overlays using PIL/Pillow.
Creates visually appealing text images with keyword highlighting and channel branding.
"""
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import platform
import random


# Bright highlight colors that pop on black background
HIGHLIGHT_COLORS = [
    (255, 255, 0),    # Yellow
    (0, 255, 255),    # Cyan
    (255, 100, 100),  # Bright Red
    (100, 255, 100),  # Bright Green
    (255, 150, 50),   # Orange
    (255, 100, 255),  # Pink/Magenta
    (100, 200, 255),  # Light Blue
]


def get_system_font() -> str:
    """Get a suitable system font path based on OS."""
    system = platform.system()

    if system == "Darwin":  # macOS
        font_paths = [
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "/Library/Fonts/Arial Bold.ttf",
        ]
    elif system == "Windows":
        font_paths = [
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/arial.ttf",
        ]
    else:  # Linux
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        ]

    for path in font_paths:
        if Path(path).exists():
            return path

    # Fallback to default
    return None


class TextRenderer:
    """Renders text as images for video composition with keyword highlighting and branding."""

    def __init__(
        self,
        width: int = 1080,
        height: int = 990,  # Text area (1920 - 750 video - 180 bottom padding)
        font_size_hook: int = 54,
        font_size_fact: int = 36,
        text_color: tuple = (255, 255, 255),  # White
        highlight_color: tuple = None,  # Will be randomized if None
        bg_color: tuple = (0, 0, 0),  # Black
        padding: int = 90,  # Side padding - keeps text in safe zone away from screen edges
        logo_path: Path = None,
        channel_name: str = "Daily Incredible Facts",
        channel_handle: str = "@daily_incredible_facts",
    ):
        self.width = width
        self.height = height
        self.text_color = text_color
        # Pick a random bright highlight color for this video
        self.highlight_color = highlight_color or random.choice(HIGHLIGHT_COLORS)
        self.bg_color = bg_color
        self.padding = padding
        self.logo_path = logo_path
        self.channel_name = channel_name
        self.channel_handle = channel_handle

        # Load fonts
        font_path = get_system_font()
        try:
            self.hook_font = ImageFont.truetype(font_path, font_size_hook)
            self.fact_font = ImageFont.truetype(font_path, font_size_fact)
            self.channel_name_font = ImageFont.truetype(font_path, 44)  # Larger channel name
            self.channel_handle_font = ImageFont.truetype(font_path, 28)  # Larger handle
        except Exception:
            # Fallback to default font
            self.hook_font = ImageFont.load_default()
            self.fact_font = ImageFont.load_default()
            self.channel_name_font = ImageFont.load_default()
            self.channel_handle_font = ImageFont.load_default()

        # Store base font sizes for dynamic scaling
        self.base_hook_size = font_size_hook
        self.base_fact_size = font_size_fact

    def _calculate_text_height(self, lines: list[str], font: ImageFont.FreeTypeFont, line_spacing: int) -> int:
        """Calculate total height of wrapped text."""
        dummy_img = Image.new("RGB", (1, 1))
        draw = ImageDraw.Draw(dummy_img)
        total = 0
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            total += bbox[3] - bbox[1] + line_spacing
        return total - line_spacing  # Remove last spacing

    def render(
        self,
        hook: str,
        fact_text: str,
        highlight_words: list[str],
        output_path: Path,
    ) -> Path:
        """Render text as an image with highlighted keywords and channel branding."""
        # Create image with black background
        img = Image.new("RGB", (self.width, self.height), self.bg_color)
        draw = ImageDraw.Draw(img)

        # Calculate available width for text (more padding on sides)
        text_width = self.width - (self.padding * 2)

        # === STEP 1: Draw Logo and Channel Branding (CENTERED at top) ===
        logo_size = 100  # Larger logo
        branding_end_y = self.padding

        if self.logo_path and Path(self.logo_path).exists():
            # Load and resize logo
            logo = Image.open(self.logo_path).convert("RGBA")
            logo = logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)

            # Center the logo horizontally with more top padding to prevent cropping
            logo_x = (self.width - logo_size) // 2
            logo_y = 55  # More padding from top to prevent cropping

            # Paste logo onto image
            img.paste(logo, (logo_x, logo_y), logo)

            # Draw channel name BELOW logo (centered)
            name_bbox = draw.textbbox((0, 0), self.channel_name, font=self.channel_name_font)
            name_width = name_bbox[2] - name_bbox[0]
            name_x = (self.width - name_width) // 2
            name_y = logo_y + logo_size + 12

            # Draw channel name with shadow
            draw.text((name_x + 2, name_y + 2), self.channel_name,
                      font=self.channel_name_font, fill=(50, 50, 50))
            draw.text((name_x, name_y), self.channel_name,
                      font=self.channel_name_font, fill=self.text_color)

            # Draw handle below channel name (centered)
            handle_bbox = draw.textbbox((0, 0), self.channel_handle, font=self.channel_handle_font)
            handle_width = handle_bbox[2] - handle_bbox[0]
            handle_x = (self.width - handle_width) // 2
            handle_y = name_y + 48  # More spacing for larger fonts

            draw.text((handle_x + 1, handle_y + 1), self.channel_handle,
                      font=self.channel_handle_font, fill=(40, 40, 40))
            draw.text((handle_x, handle_y), self.channel_handle,
                      font=self.channel_handle_font, fill=(140, 140, 140))

            branding_end_y = handle_y + 40

        # === STEP 2: Calculate content area and adjust fonts if needed ===
        content_top = branding_end_y + 25  # Space after branding
        content_bottom = self.height - 50  # Leave bigger buffer at bottom to NEVER overlap video
        available_height = content_bottom - content_top

        # Wrap text with current fonts
        hook_wrapped = self._wrap_text(hook, self.hook_font, text_width)
        fact_wrapped = self._wrap_text(fact_text, self.fact_font, text_width)

        # Calculate heights
        hook_line_spacing = 12
        fact_line_spacing = 14
        gap_between = 30  # Gap between hook and fact

        hook_height = self._calculate_text_height(hook_wrapped, self.hook_font, hook_line_spacing)
        fact_height = self._calculate_text_height(fact_wrapped, self.fact_font, fact_line_spacing)
        total_content_height = hook_height + gap_between + fact_height

        # Scale down fonts iteratively to GUARANTEE text fits
        font_path = get_system_font()
        scale = 1.0
        min_scale = 0.45  # Absolute minimum to maintain readability

        # Keep reducing scale until text fits
        while total_content_height > available_height and scale > min_scale:
            scale -= 0.05  # Reduce by 5% each iteration

            try:
                new_hook_size = max(int(self.base_hook_size * scale), 28)  # Minimum 28px
                new_fact_size = max(int(self.base_fact_size * scale), 22)  # Minimum 22px
                self.hook_font = ImageFont.truetype(font_path, new_hook_size)
                self.fact_font = ImageFont.truetype(font_path, new_fact_size)

                # Re-wrap and recalculate with new fonts
                hook_wrapped = self._wrap_text(hook, self.hook_font, text_width)
                fact_wrapped = self._wrap_text(fact_text, self.fact_font, text_width)
                hook_height = self._calculate_text_height(hook_wrapped, self.hook_font, hook_line_spacing)
                fact_height = self._calculate_text_height(fact_wrapped, self.fact_font, fact_line_spacing)
                total_content_height = hook_height + gap_between + fact_height
            except Exception:
                break

        # Final safety check - if still too big, reduce gap and line spacing
        if total_content_height > available_height:
            gap_between = 15
            hook_line_spacing = 8
            fact_line_spacing = 10
            total_content_height = hook_height + gap_between + fact_height

        # === STEP 3: Calculate vertical centering ===
        # Center the content (hook + gap + fact) in the available space
        vertical_padding = (available_height - total_content_height) // 2
        current_y = content_top + vertical_padding

        # === STEP 4: Draw Hook Text (centered) ===
        for line in hook_wrapped:
            bbox = draw.textbbox((0, 0), line, font=self.hook_font)
            line_width = bbox[2] - bbox[0]
            line_height = bbox[3] - bbox[1]
            x = (self.width - line_width) // 2

            # Draw hook text in white with shadow
            draw.text((x + 2, current_y + 2), line, font=self.hook_font, fill=(50, 50, 50))
            draw.text((x, current_y), line, font=self.hook_font, fill=self.text_color)

            current_y += line_height + hook_line_spacing

        # Gap between hook and fact
        current_y += gap_between - hook_line_spacing  # Adjust for last line spacing

        # === STEP 5: Draw Fact Text with Highlighted Keywords ===
        for line in fact_wrapped:
            # Calculate line width for centering
            bbox = draw.textbbox((0, 0), line, font=self.fact_font)
            line_width = bbox[2] - bbox[0]
            line_height = bbox[3] - bbox[1]
            start_x = (self.width - line_width) // 2

            # Draw each word, highlighting keywords
            current_x = start_x
            words = line.split(" ")

            for word in words:
                # Check if this word should be highlighted (case-insensitive)
                word_lower = word.lower().strip(".,!?;:'\"")
                should_highlight = any(
                    hw.lower() in word_lower or word_lower in hw.lower()
                    for hw in highlight_words
                )

                color = self.highlight_color if should_highlight else self.text_color

                # Draw shadow
                draw.text(
                    (current_x + 2, current_y + 2),
                    word,
                    font=self.fact_font,
                    fill=(30, 30, 30),
                )

                # Draw word
                draw.text((current_x, current_y), word, font=self.fact_font, fill=color)

                # Move x position for next word
                word_bbox = draw.textbbox((0, 0), word + " ", font=self.fact_font)
                current_x += word_bbox[2] - word_bbox[0]

            # Move to next line
            current_y += line_height + fact_line_spacing

        # Save image
        img.save(output_path, "PNG")
        return output_path

    def _wrap_text(self, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
        """Wrap text to fit within max_width pixels."""
        words = text.split()
        lines = []
        current_line = []

        dummy_img = Image.new("RGB", (1, 1))
        draw = ImageDraw.Draw(dummy_img)

        for word in words:
            test_line = " ".join(current_line + [word])
            bbox = draw.textbbox((0, 0), test_line, font=font)
            if bbox[2] - bbox[0] <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                current_line = [word]

        if current_line:
            lines.append(" ".join(current_line))

        return lines
