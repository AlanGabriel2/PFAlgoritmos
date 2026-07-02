# Guía de contribución

¡Gracias por tu interés en contribuir a **Mega-Calabozo DAG**! Este documento
resume cómo colaborar de forma ordenada.

## Requisitos previos

- **Python 3.10+**
- **Pygame** (recomendado `pygame-ce`): `pip install pygame-ce`

Para ejecutar el juego:

```bash
python main.py
```

## Flujo de trabajo

1. Haz un *fork* del repositorio y clónalo.
2. Crea una rama descriptiva a partir de `main`:
   `git checkout -b feature/mi-mejora` o `fix/mi-arreglo`.
3. Realiza tus cambios en commits pequeños y con mensajes claros (en español o
   inglés).
4. Verifica que el juego arranca sin errores: `python main.py`.
5. Abre un *Pull Request* hacia `main` describiendo el qué y el porqué del cambio.

## Estilo y buenas prácticas

Consulta también [`AGENTS.md`](AGENTS.md) para entender la arquitectura antes de
tocar código. Reglas clave del proyecto:

- **Colisiones lógicas, no por píxeles.** Usa capas matemáticas (`pygame.Rect`),
  nunca los píxeles de las imágenes de fondo.
- **Escalado por superficie virtual.** Todo se dibuja sobre un lienzo de
  `1280×720` que luego se escala con letterbox. No hardcodees coordenadas para
  otras resoluciones.
- **La lógica corre a 60 Hz fijos** (*fixed timestep*). No conviertas el juego a
  delta-time variable sin entender el bucle principal.
- **Los mapas/colisiones viven en `levels/*.json`**, no en el bucle principal.
- No cambies posiciones de nodos ni la estructura del DAG salvo que sea el
  objetivo explícito del cambio.

## Reportar problemas

Usa las plantillas de *Issues* (reporte de error / solicitud de función). Incluye
pasos para reproducir, comportamiento esperado y capturas si aplica.

## Código de conducta

Al participar aceptas cumplir el [Código de Conducta](CODE_OF_CONDUCT.md).
