# Música del juego

El juego busca las pistas por nombre de archivo (formatos: `.ogg`, `.wav`, `.mp3`).
Para cambiar una pista basta con reemplazar el archivo — no hay que tocar código.

| Archivo      | Dónde suena                                          |
|--------------|------------------------------------------------------|
| `menu`       | Disclaimer, pantalla de título y menús               |
| `tutorial`   | Tutorial                                             |
| `map`        | Mapa del calabozo (DAG)                              |
| `combat`     | Combate, semestres 1-3                               |
| `combat_s2`  | Combate, semestres 4-6                               |
| `combat_s3`  | Combate, semestres 7-10                              |
| `boss`       | Caminos críticos con miniboss                         |
| `boss_final` | Boss final (Titulación)                              |
| `win`        | Pantalla de victoria                                 |

No es obligatorio tener todas: si falta una pista se usa un fallback razonable
(`boss_final` → `boss` → `combat` → `map` → `menu`; `combat_s3` → `combat_s2` →
`combat`...) y si no hay ninguna, simplemente no suena música.

Las pistas actuales vienen de packs CC0; ver `CREDITOS.md` en la raíz del proyecto.
