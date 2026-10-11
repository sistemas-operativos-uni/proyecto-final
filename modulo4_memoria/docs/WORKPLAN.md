# Módulo 4: plan de trabajo

Responsable: Adán. Rama: `feature/modulo4-memoria`.

## Objetivo

Simular la gestión de memoria contigua de SO-Sim: asignar bloques a procesos con primer, mejor y peor ajuste, liberarlos y medir la fragmentación interna y externa. El modelo es independiente de la paginación del Módulo 3 (ver `docs/decisiones/ADR-001-modulos-de-memoria.md`).

## Archivos del módulo

| Archivo | Responsabilidad |
| --- | --- |
| `py/asignacion_contigua.py` | Mapa de bloques, estrategias de ajuste, asignación y liberación con fusión de huecos |
| `py/fragmentacion.py` | Cálculo de fragmentación interna y externa a partir del mapa |
| `py/gestor_memoria.py` | Lectura del escenario, ejecución paso a paso, eventos, métricas y comparación de estrategias |
| `tests/test_asignacion_contigua.py` | Pruebas de estrategias, liberación e invariantes del mapa |
| `tests/test_fragmentacion.py` | Pruebas de las fórmulas de fragmentación |
| `tests/test_gestor_memoria.py` | Pruebas sobre `escenarios/solicitudes_memoria.csv` y errores recuperables |

Dependencias: `asignacion_contigua` no depende de nada; `fragmentacion` lee bloques de `asignacion_contigua`; `gestor_memoria` usa ambos. El módulo no importa otros módulos del proyecto.

## Entregables

### Reunión del miércoles 7 de octubre de 2026 (avance del parcial)

- [x] `asignacion_contigua.py` con primer, mejor y peor ajuste y liberación.
- [x] `fragmentacion.py` con fragmentación interna y externa.
- [x] `gestor_memoria.py` con ejecución del escenario y comparación de estrategias.
- [x] Pruebas de los tres archivos.

### Próximas reuniones

- [ ] Adaptar `ResultadoMemoria` al contrato `ModuleResult` cuando Renato defina `core/modelos.py` y `core/contratos.py`.
- [ ] Leer la configuración (memoria total, unidad, estrategia) desde `SimulationConfig` en lugar de las constantes provisionales.
- [ ] Usar `core/cargador_escenarios.py` y `core/reloj.py` cuando existan, en lugar del lector CSV y el número de paso propios.
- [ ] Exportar las métricas a `resultados/` (CSV o JSON) y, si el equipo lo pide, un gráfico de fragmentación por paso con `matplotlib`.
- [ ] Probar con escenarios más grandes que provoquen rechazos por fragmentación externa.

## Decisiones pendientes con el equipo

- Memoria total y unidad de asignación definitivas. Hoy se usan 512 KB y 64 KB.
- Si se incluye compactación como mejora opcional.
