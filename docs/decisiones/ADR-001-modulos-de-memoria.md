# ADR-001 Separar paginación y gestión de memoria contigua

## Estado

Aceptada por la estructura acordada para este proyecto.

## Contexto

La propuesta inicial agrupaba paginación, reemplazo de páginas y asignación contigua en una sola carpeta. El equipo asignó la paginación a Gabriel y la gestión de memoria contigua a Adán. Si se mantienen juntas, la carpeta no refleja la propiedad del trabajo y mezcla dos modelos de memoria diferentes.

## Decisión

El Módulo 3 implementa paginación y reemplazo de páginas. El Módulo 4 implementa asignación contigua y fragmentación. Los módulos posteriores se numeran como Módulo 5 para E/S y archivos, Módulo 6 para seguridad y Módulo 7 para sistemas distribuidos.

## Consecuencias

- Cada responsable tiene una carpeta con límites claros.
- Paginación mantiene tabla de páginas, marcos y fallos de página.
- Memoria contigua mantiene bloques, asignaciones y fragmentación.
- Ambos módulos comparten contratos de proceso definidos en `core/`, pero no comparten el mapa de memoria.
- README, pruebas, cronograma y referencias del repositorio usan la numeración del 1 al 7.
