# image_client.py
import os
import base64
import io
import logging
from typing import Optional

import aiohttp
from dotenv import load_dotenv
from ai_client import make_ollama_client
from config import OLLAMA_MODEL

load_dotenv()
logger = logging.getLogger("image_client")

STABLE_DIFFUSION_URL = os.getenv("STABLE_DIFFUSION_URL")

class ImageGenerationError(Exception):
    """Custom exception for image generation failures."""
    pass

async def generate_image(prompt: str, capabilities: dict) -> io.BytesIO:
    """
    Generates an image using the best available method.
    Prioritizes Ollama's built-in generation if the model supports it,
    otherwise falls back to a standalone Stable Diffusion server.
    """
    # For now, we assume models with 'dall-e' in their name can generate images
    if "dall-e" in OLLAMA_MODEL:
        try:
            return await _generate_with_ollama(prompt)
        except Exception as e:
            logger.error(f"Ollama image generation failed, falling back to Stable Diffusion. Error: {e}")
            # Fallback to Stable Diffusion if Ollama method fails
            return await _generate_with_stable_diffusion(prompt)
    else:
        # Default to Stable Diffusion if model is not a known generator
        return await _generate_with_stable_diffusion(prompt)

async def _generate_with_ollama(prompt: str) -> io.BytesIO:
    logger.info(f"Generating image with Ollama model: {OLLAMA_MODEL}")
    client = make_ollama_client()
    try:
        # NOTE: This assumes the 'ollama-python' library and model support this format.
        # This is a forward-looking implementation.
        response = await client.generate(model=OLLAMA_MODEL, prompt=prompt, format="png")
        if "image" in response:
            img_data = response["image"]
            return io.BytesIO(img_data)
        else:
            raise ImageGenerationError("Ollama response did not contain image data.")
    except Exception as e:
        logger.exception("Ollama image generation API call failed.")
        raise ImageGenerationError(f"Ollama API error: {e}")

async def _generate_with_stable_diffusion(prompt: str) -> io.BytesIO:
    """Generates an image using the Stable Diffusion API and returns it as a BytesIO object."""
    if not STABLE_DIFFUSION_URL:
        raise ImageGenerationError("Stable Diffusion URL is not configured.")

    logger.info("Generating image with Stable Diffusion fallback.")
    api_url = f"{STABLE_DIFFUSION_URL}/sdapi/v1/txt2img"
    payload = {
        "prompt": prompt,
        "steps": 25,
        "width": 1024,
        "height": 1024,
        "cfg_scale": 7,
        "sampler_name": "DPM++ 2M Karras",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(api_url, json=payload, timeout=180) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error("Stable Diffusion API returned status %d: %s", response.status, error_text)
                    raise ImageGenerationError(f"Stable Diffusion API Error (Status {response.status})")
                
                data = await response.json()
                if "images" in data and data["images"]:
                    img_data = base64.b64decode(data["images"][0])
                    return io.BytesIO(img_data)
                else:
                    raise ImageGenerationError("No images found in Stable Diffusion API response.")
    except aiohttp.ClientError as e:
        logger.exception("Failed to connect to Stable Diffusion API.")
        raise ImageGenerationError(f"Connection to Stable Diffusion failed: {e}")
    except Exception as e:
        logger.exception("An unexpected error occurred during Stable Diffusion generation.")
        raise ImageGenerationError(f"An unexpected error occurred: {e}")