# Arquitectura de SO-Sim

## Estilo

SO-Sim comienza como un simulador modular de línea de comandos. El equipo mantiene los módulos en un solo repositorio y separa cada mecanismo por responsabilidad. No introduce microservicios, base de datos ni una interfaz web porque el caso se resuelve con escenarios locales reproducibles.

## Capas y dependencias

`main.py` será el punto de entrada y delegará la ejecución al orquestador. El orquestador cargará configuración y escenarios mediante `core/`, invocará módulos y combinará resultados. `core/` contiene modelos neutrales y contratos; no importa implementaciones de módulos. Cada módulo importa contratos de `core/` y mantiene sus algoritmos dentro de su propia carpeta. Ningún módulo importa otro módulo. `tests/` puede importar componentes públicos, pero el código de producción no importa pruebas.

Dirección permitida:

```text
main.py -> orquestación -> core y módulos
módulos -> contratos y modelos de core
core -X-> módulos concretos
módulo A -X-> módulo B
```

## Contrato de ejecución

Antes de implementar, el equipo define `SimulationConfig` y `ModuleResult` en `core/modelos.py`. Cada módulo recibe una configuración validada y devuelve un resultado con estado, eventos, métricas y errores recuperables. Los módulos no usan texto impreso como canal de comunicación; la CLI presenta el resultado y las pruebas inspeccionan sus campos.

Los eventos registran instante lógico, módulo, entidad, acción y datos específicos. El núcleo ordena y reúne eventos. Las métricas propias, como fallos de página o fragmentación, se calculan en su módulo; `core/metricas.py` reúne métricas transversales y prepara exportaciones.

## Límites de los módulos

### Módulo 1 Procesos hilos y planificación

Renato implementa creación de procesos POSIX, un ejemplo de hilos y FCFS, SJF, Round Robin y prioridad. El módulo calcula tiempos de espera, retorno y respuesta usando los mismos procesos de entrada.

### Módulo 2 Sincronización de procesos

Kike implementa lectores-escritores y ejemplos de semáforos y mutex en C. Las trazas permiten reconstruir el acceso al padrón y comprobar exclusión mutua.

### Módulo 3 Paginación

Gabriel implementa traducción de direcciones lógicas, tabla de páginas, marcos, fallos de página y reemplazo FIFO, LRU y Óptimo. Cada política consume la misma traza. El módulo no realiza asignación contigua.

### Módulo 4 Gestión de memoria

Adán implementa bloques contiguos, asignación por primer, mejor y peor ajuste, liberación, mapa de bloques y fragmentación interna y externa. Este modelo se mantiene separado del mapa de páginas del Módulo 3.

### Módulo 5 Entrada salida y sistema de archivos

Implementa las operaciones de E/S del registro simulado, persistencia de archivos, métodos de asignación de archivos y permisos básicos. El responsable queda pendiente de asignación por el equipo.

### Módulo 6 Seguridad

Implementa autenticación de prueba, autorización por rol y cifrado de boletas simuladas. No guarda secretos ni credenciales reales. El responsable queda pendiente de asignación por el equipo.

### Módulo 7 Sistemas distribuidos

Simula nodos de facultades y mensajes para coordinar cursos dentro del escenario local. El responsable queda pendiente de asignación por el equipo.

## Escenarios y resultados

`escenarios/` contiene entradas CSV pequeñas, grandes, secuencias de acceso y solicitudes de memoria. Las filas son datos sintéticos. El simulador no procesa información personal real. `resultados/` almacena CSV, JSON, trazas y gráficos generados; `.gitignore` excluye esos productos salvo los archivos de control.

## Criterios de integración

- Todos los módulos aceptan entradas validadas y devuelven resultados estructurados.
- Paginación y asignación contigua usan estados distintos y exponen métricas propias.
- Las comparaciones de algoritmos usan exactamente el mismo escenario.
- Un fallo recuperable de un módulo queda registrado y no se convierte en una salida silenciosa.
- La ejecución integral conserva eventos suficientes para explicar las métricas.
