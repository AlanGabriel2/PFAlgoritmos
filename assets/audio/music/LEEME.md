# Música del juego

Coloca aquí las pistas de música. El juego las busca por nombre de archivo
(formatos: `.ogg` recomendado, también `.wav` y `.mp3`):

| Archivo      | Dónde suena                                          |
|--------------|------------------------------------------------------|
| `menu`       | Disclaimer, pantalla de título y menús               |
| `map`        | Mapa del calabozo (DAG)                              |
| `combat`     | Combate normal                                       |
| `boss`       | Salas de miniboss                                    |
| `boss_final` | Boss final (Titulación)                              |
| `win`        | Pantalla de victoria                                 |

No es obligatorio tener todas: si falta una pista se usa un fallback razonable
(`boss_final` → `boss` → `combat` → `map` → `menu`) y si no hay ninguna,
simplemente no suena música. No hace falta tocar código para agregarlas.

Fuentes gratuitas con licencia libre: OpenGameArt.org, Kenney.nl, freesound.org
(revisa la licencia de cada pista y da crédito si lo requiere).
