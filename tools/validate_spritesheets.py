"""Valida las hojas normalizadas que consume el juego.

Usa la misma configuracion de grillas que tools/normalize_spritesheets.py, asi
que basta con registrar una hoja alli para que quede cubierta aqui.

Errores (codigo de salida 1): hoja faltante, dimensiones incorrectas, frame
vacio, frame flotando mucho sobre la linea de suelo (pipeline roto).
Advertencias (no bloquean): flotes leves, pixeles sueltos, saltos bruscos de
area entre frames consecutivos, deriva horizontal dentro de una fila.

El anclaje se mide con la union de las islas sustanciales del frame, no solo
la mayor: en entidades que vuelan (boss) el cuerpo flota pero la llama de
propulsion si toca el suelo, y eso es correcto.

Uso: python tools/validate_spritesheets.py [--quiet]
"""
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from normalize_spritesheets import ROOT, SHEETS

ALPHA_T = 8            # umbral de alfa para considerar un pixel visible
MAX_FLOAT_GAP = 2      # px de flote tolerados sin avisar
ERROR_FLOAT_GAP = 12   # a partir de aqui el flote es error (anclaje roto)
STRAY_MIN_DIST = 4     # distancia al cuerpo para considerar una isla "suelta"
AREA_JUMP_RATIO = 1.45 # salto de area visible entre frames consecutivos
DRIFT_FRACTION = 0.18  # deriva horizontal tolerada (fraccion del ancho de celda)


def _islands(mask, w, h):
    """Componentes conexas (4-conn). Devuelve [(tamano, bbox)] de mayor a menor."""
    seen = bytearray(w * h)
    comps = []
    for start in range(w * h):
        if mask[start] and not seen[start]:
            stack = [start]
            seen[start] = 1
            size = 0
            x0, y0, x1, y1 = w, h, 0, 0
            while stack:
                i = stack.pop()
                size += 1
                x, y = i % w, i // w
                x0, y0 = min(x0, x), min(y0, y)
                x1, y1 = max(x1, x), max(y1, y)
                for j in (i - 1 if x > 0 else -1, i + 1 if x < w - 1 else -1,
                          i - w if y > 0 else -1, i + w if y < h - 1 else -1):
                    if j >= 0 and mask[j] and not seen[j]:
                        seen[j] = 1
                        stack.append(j)
            comps.append((size, (x0, y0, x1, y1)))
    comps.sort(reverse=True)
    return comps


def validate_sheet(name, path, rows, cols, cell_w, cell_h):
    """Devuelve (errores, advertencias) para una hoja normalizada."""
    errors, warnings = [], []
    if not path.exists():
        return [f"no existe {path.relative_to(ROOT)}"], []

    im = Image.open(path).convert("RGBA")
    expected = (cell_w * cols, cell_h * rows)
    if im.size != expected:
        return [f"dimensiones {im.size}, esperado {expected}"], []

    for r in range(rows):
        areas, offsets = [], []
        for c in range(cols):
            cell = im.crop((c * cell_w, r * cell_h, (c + 1) * cell_w, (r + 1) * cell_h))
            alpha = cell.getchannel("A").tobytes()
            mask = [b > ALPHA_T for b in alpha]
            fid = f"frame f{r}c{c}"
            if not any(mask):
                errors.append(f"{fid}: vacio")
                areas.append(None)
                offsets.append(None)
                continue

            comps = _islands(mask, cell_w, cell_h)
            main_size, main_bbox = comps[0]
            stray_limit = max(6, main_size * 0.002)

            # Mota suelta = isla pequena Y alejada del cuerpo. Una isla pequena
            # pero adyacente (llama de propulsion, extremidad) es parte del sprite.
            # Para el anclaje tambien cuenta cualquier isla directamente debajo
            # del cuerpo (solape horizontal): llamas o goteos de entidades que
            # levitan tocan el suelo aunque el cuerpo flote.
            solid_bottom = main_bbox[3]
            for size, (x0, y0, x1, y1) in comps[1:]:
                dx = max(main_bbox[0] - x1, x0 - main_bbox[2], 0)
                dy = max(main_bbox[1] - y1, y0 - main_bbox[3], 0)
                if size <= stray_limit and dx + dy > STRAY_MIN_DIST:
                    warnings.append(f"{fid}: pixel suelto de {size}px en ({x0}, {y0})")
                    if y0 > main_bbox[3] and dx == 0:
                        solid_bottom = max(solid_bottom, y1)
                else:
                    solid_bottom = max(solid_bottom, y1)

            gap = cell_h - 1 - solid_bottom
            if gap > ERROR_FLOAT_GAP:
                errors.append(f"{fid}: flota {gap}px sobre la linea de suelo")
            elif gap > MAX_FLOAT_GAP:
                warnings.append(f"{fid}: flota {gap}px sobre la linea de suelo")

            areas.append(main_size)
            offsets.append((main_bbox[0] + main_bbox[2]) / 2 - (cell_w - 1) / 2)

        valid = [(i, a) for i, a in enumerate(areas) if a]
        for (i1, a1), (i2, a2) in zip(valid, valid[1:]):
            ratio = max(a1, a2) / max(1, min(a1, a2))
            if ratio > AREA_JUMP_RATIO:
                warnings.append(f"fila {r}: salto de area x{ratio:.2f} entre c{i1} y c{i2}")

        offs = [o for o in offsets if o is not None]
        if offs and max(offs) - min(offs) > cell_w * DRIFT_FRACTION:
            warnings.append(f"fila {r}: deriva horizontal de {max(offs) - min(offs):.0f}px")

    return errors, warnings


def main():
    quiet = "--quiet" in sys.argv
    total_errors = total_warnings = 0

    for name, (source_rel, rows, cols, (cell_w, cell_h), _ref) in SHEETS.items():
        source = Path(source_rel)
        path = ROOT / source.with_name(f"{source.stem}_normalized.png")
        errors, warnings = validate_sheet(name, path, rows, cols, cell_w, cell_h)
        total_errors += len(errors)
        total_warnings += len(warnings)
        for msg in errors:
            print(f"[ERROR] {name}: {msg}")
        if not quiet:
            for msg in warnings:
                print(f"[aviso] {name}: {msg}")

    print(f"\n{len(SHEETS)} hojas validadas: "
          f"{total_errors} errores, {total_warnings} advertencias.")
    return 1 if total_errors else 0


if __name__ == "__main__":
    sys.exit(main())
