import os
import io
import logging
from PIL import Image, ImageDraw, ImageFont
from dotenv import load_dotenv

load_dotenv()
FONT_PATH = os.getenv("FONT_PATH")
logger = logging.getLogger("image_utils")

def compress_image_for_ai(image_bytes: bytes, max_dimension: int = 1024, quality: int = 85) -> bytes:
    try:
        img = Image.open(io.BytesIO(image_bytes))
        
        if img.mode != "RGB":
            img = img.convert("RGB")
            
        if img.width > max_dimension or img.height > max_dimension:
            img.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
            
        output_buffer = io.BytesIO()
        img.save(output_buffer, format="JPEG", quality=quality)
        return output_buffer.getvalue()
        
    except Exception as e:
        logger.error(f"Image compression failed: {e}")
        return image_bytes

def add_caption_to_image(image_bytes: bytes, top_text: str, bottom_text: str) -> io.BytesIO:
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        draw = ImageDraw.Draw(img)
        font_size = int(img.width / 10)
        
        try:
            if not FONT_PATH or not os.path.exists(FONT_PATH):
                raise IOError("Font file not found or path not set in .env")
            font = ImageFont.truetype(FONT_PATH, font_size)
        except IOError as e:
            logger.warning(f"Font error ({e}). Falling back to default font.")
            font = ImageFont.load_default()

        def draw_text_with_outline(text, x, y, current_font):
            for offset in [(-2, -2), (-2, 2), (2, -2), (2, 2)]:
                draw.text((x + offset[0], y + offset[1]), text, font=current_font, fill="black")
            draw.text((x, y), text, font=current_font, fill="white")

        if top_text:
            bbox = draw.textbbox((0, 0), top_text, font=font)
            text_width = bbox[2] - bbox[0]
            x = (img.width - text_width) / 2
            y = 10
            draw_text_with_outline(top_text, x, y, font)

        if bottom_text:
            bbox = draw.textbbox((0, 0), bottom_text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            x = (img.width - text_width) / 2
            y = img.height - text_height - 10
            draw_text_with_outline(bottom_text, x, y, font)
        
        output_buffer = io.BytesIO()
        img.save(output_buffer, format="JPEG")
        output_buffer.seek(0)
        return output_buffer

    except Exception as e:
        logger.error(f"Error captioning image: {e}")
        return None