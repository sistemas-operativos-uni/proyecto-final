# Experimento del Módulo 4

Generado con `python -m modulo4_memoria.py.experimento`.
100 jornadas aleatorias (semillas 1–100) × 300 operaciones, memoria de 1024 KB. Un rechazo no se reintenta.

## 1. Estrategias (paquete de 64 KB, misma carga para las tres)

| Métrica | primer | mejor | peor |
|---|---:|---:|---:|
| Procesos que pidieron memoria | 17929 | 17929 | 17929 |
| Rechazados aunque había memoria, cada 100 | 10,1 | 8,2 | 12,8 |
| Rechazados en total (%) | 32,9 | 32,8 | 33,1 |
| Fragmentación externa promedio (%) | 21,6 | 18,3 | 26,6 |
| Fragmentación interna promedio (%) | 19,9 | 19,8 | 20,0 |
| Huecos separados (promedio) | 1,69 | 1,56 | 1,87 |

## 2. Tamaño del paquete (estrategia mejor ajuste)

| Paquete (KB) | Interna (%) | Externa (%) | Rechazados en total (%) |
|---:|---:|---:|---:|
| 1 | 0,0 | 33,7 | 31,5 |
| 16 | 6,3 | 29,6 | 31,9 |
| 32 | 11,3 | 25,7 | 32,2 |
| 64 | 19,8 | 18,3 | 32,8 |
| 128 | 31,5 | 10,0 | 34,4 |
