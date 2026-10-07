# Módulo 4: registro de implementaciones

## 2026-10-06 · Primera versión funcional

Rama: `feature/modulo4-memoria`.

### `py/asignacion_contigua.py`

- `Bloque`: tramo contiguo con `inicio_kb`, `tamano_kb`, `proceso_id` (o `None` si está libre) y `solicitado_kb`. `desperdicio_kb` = asignado − solicitado.
- `MemoriaContigua(total_kb, unidad_kb)`: comienza con un único hueco. Redondea cada solicitud hacia arriba a la unidad.
- Estrategias en `SELECTORES`:
  - `primer`: primer hueco suficiente de izquierda a derecha.
  - `mejor`: hueco suficiente más pequeño.
  - `peor`: hueco más grande.
  - Los empates se resuelven por dirección más baja, así que los resultados son reproducibles.
- `asignar()`: parte el hueco elegido en bloque asignado + sobrante libre.
- `liberar()`: marca el bloque como libre y fusiona huecos vecinos.
- Errores recuperables: `ErrorMemoria` (proceso duplicado o desconocido) y `SinEspacioError`. Este último indica `por_fragmentacion=True` cuando la memoria libre total alcanzaba, pero ningún hueco era suficiente.
- Invariantes: los bloques son contiguos y cubren toda la memoria, no hay dos huecos seguidos y cada proceso tiene como máximo un bloque.

### `py/fragmentacion.py`

- `fragmentacion_interna(bloques)`: desperdicio total y porcentaje sobre la memoria asignada.
- `fragmentacion_externa(bloques)`: memoria libre total, hueco mayor, cantidad de huecos y `(1 − hueco mayor / libre total) × 100`.
- `medir(bloques)` devuelve un `ReporteFragmentacion`; `como_diccionario()` lo aplana para métricas.

### `py/gestor_memoria.py`

- `cargar_solicitudes(ruta)`: lee y valida `paso,proceso_id,operacion,tamano_kb`.
- `GestorMemoria(total_kb=512, unidad_kb=64, estrategia)`:
  - `procesar()` aplica una solicitud y genera un `Evento`: instante, módulo, entidad, acción y datos con el mapa y la fragmentación del paso.
  - `ejecutar()` procesa el escenario completo y devuelve un `ResultadoMemoria` con estado, eventos, métricas y errores.
  - Al liberar, se verifica que el tamaño indicado coincida con lo que pidió el proceso.
- `comparar_estrategias()`: ejecuta las tres estrategias con el mismo escenario.
- CLI: `python -m modulo4_memoria.py.gestor_memoria [--estrategia primer|mejor|peor|todas] [--total KB] [--unidad KB] [--escenario ruta]`.

### Resultados con `escenarios/solicitudes_memoria.csv` (512 KB, unidad 64 KB)

| Estrategia | Rechazos | Fragmentación externa máxima | Fragmentación interna máxima |
| --- | --- | --- | --- |
| Primer ajuste | 0 | 50 % (pasos 5 y 6) | 64 KB |
| Mejor ajuste | 0 | 33,33 % (paso 4) | 64 KB |
| Peor ajuste | 0 | 50 % (pasos 5 y 6) | 64 KB |

En el paso 5, P004 (64 KB) va a 128 KB con primer y peor ajuste, partiendo el hueco de 128 KB. Con mejor ajuste va al hueco exacto de 64 KB en 448 KB. En este escenario el peor ajuste coincide con el primero porque el hueco más grande también es el primero.

### Pruebas

- 33 pruebas en `tests/test_asignacion_contigua.py`, `tests/test_fragmentacion.py` y `tests/test_gestor_memoria.py`, escritas con `unittest`. Las ejecutan tanto `pytest` como `python -m unittest`.
- Verificación ejecutada: `python -m unittest discover -s tests -t .` → 33 OK.
- No se ejecutó `pytest` en este entorno porque no se pudo instalar. Hay que correr `python -m pytest` localmente.

### Limitaciones conocidas

- `core/` aún no define contratos; el módulo usa clases propias (`Evento`, `ResultadoMemoria`) con los campos acordados en `docs/arquitectura.md`.
- La memoria total y la unidad son provisionales (512 KB y 64 KB).
- No hay compactación ni exportación a `resultados/` todavía.
