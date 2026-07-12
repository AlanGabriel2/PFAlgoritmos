import os
import sys

# Pygame headless: los tests no abren ventana ni audio.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
import pytest


@pytest.fixture(scope="session", autouse=True)
def pygame_session():
    pygame.init()
    # Superficie de video necesaria para convert_alpha() al cargar hojas.
    pygame.display.set_mode((1, 1))
    yield
    pygame.quit()
