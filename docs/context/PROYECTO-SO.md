UNIVERSIDAD NACIONAL DE INGENIERÍA
Facultad de Ingeniería Industrial y de Sistemas — Escuela Profesional de Ingeniería de Software
Curso: SW407 — Sistemas Operativos
PROPUESTA DE PROYECTO INTEGRADOR
"SO-Sim: Simulador Educativo de un Sistema Operativo"
I. Presentación y justificación
El curso SW407 (4.º ciclo, 3 créditos, 4 horas semanales) desarrolla los fundamentos de los sistemas operativos y
exige, en su componente práctico, simular mediante programas los algoritmos estudiados en cada unidad. El presente
proyecto integrador articula esas actividades de laboratorio, ya previstas en el sílabo, en un único producto
acumulativo: un simulador de sistema operativo construido por módulos a lo largo de las 16 semanas lectivas, en lugar
de ejercicios aislados por sesión.
De este modo, cada avance reutiliza y amplía el trabajo anterior, refuerza la comprensión de cómo interactúan los
subsistemas de un SO real y da a los dos exámenes (parcial y final) y a las cuatro evaluaciones prácticas exigidas por el
sílabo (2 prácticas escritas/laboratorio + 2 trabajos domiciliarios) un hilo conductor común.
II. Objetivos
Objetivo general
Diseñar, implementar y sustentar en equipo un simulador funcional que reproduzca, mediante programas en C y/o
Python, los principales algoritmos y mecanismos de gestión de procesos, memoria, entrada/salida, archivos, seguridad
y comunicación distribuida cubiertos en el sílabo de SW407.
Objetivos específicos
• Implementar y comparar algoritmos de planificación de procesos (FCFS, SJF, Round Robin, Prioridad).
• Resolver un problema clásico de sincronización usando semáforos o mutex, evitando condiciones de carrera.
• Simular la gestión de memoria (asignación contigua, paginación) y comparar algoritmos de reemplazo de páginas
(FIFO, LRU, Óptimo).
• Simular operaciones básicas de entrada/salida y un sistema de archivos simplificado con permisos.
• Incorporar un mecanismo simple de autenticación/control de acceso y cifrado, y una demostración de
comunicación entre procesos distribuidos.
• Documentar y sustentar oralmente el diseño, la implementación y los resultados obtenidos.
III. Organización del trabajo
Equipos de 3 a 4 integrantes, constituidos en la semana 1. Lenguajes sugeridos: C (para los módulos de procesos, hilos
y sincronización, en línea con las actividades del sílabo) y Python (para los módulos de planificación, memoria y
análisis de resultados); un equipo puede usar un solo lenguaje si lo justifica en su ficha técnica. Se recomienda el uso
de un repositorio Git para evidenciar la participación individual, criterio considerado en la rúbrica.
IV. Módulos del simulador
El proyecto se construye incrementalmente en seis módulos, cada uno anclado a la unidad del sílabo correspondiente:

Módulo Contenido técnico (según sílabo) Resultado esperado
Procesos, hilos y planificación (fork/exec, Planificador que recibe una lista de procesos y calcula
1
threading, FCFS, SJF, Round Robin, Prioridad). tiempos de espera/respuesta por algoritmo.
Sincronización: semáforos, mutex, un problema
Programa concurrente sin condiciones de carrera ni
2 clásico (productor-consumidor, filósofos o
interbloqueo, con evidencia de ejecución correcta.
lectores-escritores).
Gestión de memoria: asignación contigua,
Simulador que calcula fallos de página y compara los
3 fragmentación, paginación y algoritmos de
tres algoritmos con un mismo patrón de acceso.
reemplazo (FIFO, LRU, Óptimo).
Entrada/Salida y sistemas de archivos: sondeo,
Simulación de operaciones de E/S y un sistema de
4 interrupciones, DMA, métodos de asignación de
archivos simplificado con permisos básicos.
archivos (contigua, enlazada, indexada).
Seguridad: autenticación, control de acceso, cifrado
Módulo de control de acceso funcional y una
5 simétrico/asimétrico básico; nociones de
demostración de cifrado/descifrado de un archivo.
virtualización.
Sistemas distribuidos: comunicación entre Demostración de intercambio de mensajes entre dos o
6
procesos/nodos (RPC o paso de mensajes simulado). más procesos simulando nodos distintos.
V. Calendario de entregas
El calendario respeta las semanas de evaluación fijadas en el sílabo (Examen Parcial en la semana 8 y Examen Final en
la semana 16) y ubica las cuatro entregas calificadas del proyecto de modo que cada una cierre un bloque temático
antes del examen correspondiente.
Semana Unidad del sílabo Entregable del proyecto Tipo de evaluación Peso
Formación de equipos (3–4 integrantes) y
elección del caso a simular. Entrega de ficha Avance sin nota (control
1 Introducción a los SO —
técnica del proyecto (alcance y lenguaje: C y/o de inicio)
Python).
Diseño de la arquitectura del simulador: módulos Avance sin nota (control
2 Estructura de un SO —
a construir y diagrama de componentes. de inicio)
Trabajo en el Módulo 1: creación/terminación de
3 Procesos e Hilos procesos (fork/exec) y simulación de hilos con Trabajo en clase —
threading.
Práctica de Laboratorio 1: Módulo 1 completo —
Planificación de procesos, hilos y planificador (FCFS, SJF, Round Práctica
4 12,5 %
Procesos Robin, Prioridad) con métricas de tiempo de escrita/laboratorio N.º 1
espera y respuesta.
Trabajo en el Módulo 2: solución de un problema
Sincronización de
5 clásico (productor-consumidor, filósofos o Trabajo en clase —
Procesos
lectores-escritores) con semáforos/mutex.
Trabajo en el Módulo 3: simulación de asignación
6 Gestión de Memoria Trabajo en clase —
contigua, fragmentación y tablas de páginas.
Trabajo Domiciliario 1: entrega consolidada de
Algoritmos de los Módulos 2 y 3 — sincronización + gestión de Trabajo domiciliario N.º
7 12,5 %
Reemplazo de Páginas memoria y reemplazo de páginas (FIFO, LRU, 1
Óptimo) con informe comparativo.
— (semana de evaluación; puede incluir
8 EXAMEN PARCIAL Examen Parcial según fórmula
preguntas sobre el diseño del simulador)
Trabajo en el Módulo 4: simulación de manejo de
9 Entrada/Salida (E/S) Trabajo en clase —
E/S (sondeo, interrupciones, DMA, buffering).

Semana Unidad del sílabo Entregable del proyecto Tipo de evaluación Peso
Práctica de Laboratorio 2: Módulo 4 completo —
E/S simulada + sistema de archivos simplificado Práctica
10 Sistemas de Archivos 12,5 %
(asignación contigua/enlazada/indexada, escrita/laboratorio N.º 2
permisos).
Trabajo en el Módulo 5: autenticación simulada,
11 Seguridad y Protección control de acceso y cifrado básico (uso de GPG u Trabajo en clase —
otra librería).
Avance del Módulo 5 y comparación conceptual
12 Virtualización de virtualización (VM vs. contenedores) aplicada Avance sin nota (control) —
al simulador.
Avance del Módulo 6: simulación simplificada de
13 SO Distribuidos comunicación entre "nodos" (RPC o paso de Avance sin nota (control) —
mensajes).
Preparación de la sustentación y del informe final
14 Casos de Estudio Avance sin nota (control) —
integrador (todos los módulos).
Trabajo Domiciliario 2: entrega final del
Trabajo domiciliario N.º
15 Desarrollo Práctico simulador integrado (Módulos 1 a 6) + 12,5 %
2 + sustentación
sustentación oral grupal (10–15 min por equipo).
16 EXAMEN FINAL — (semana de evaluación) Examen Final según fórmula
17 Examen Sustitutorio — (aplica solo a quienes rindan sustitutorio) Examen Sustitutorio según fórmula
Nota: las cuatro entregas calificadas (semanas 4, 7, 10 y 15) equivalen a las "2 prácticas escritas sobre los laboratorios" y a los "2
trabajos domiciliarios sobre el análisis del sistema operativo" que exige el sílabo, y su promedio constituye el Promedio de
Prácticas de la fórmula oficial:
Nota Final = (Examen Parcial + Examen Final + Promedio de Prácticas) / 3
VI. Rúbrica de evaluación
La siguiente rúbrica se aplica, con los mismos criterios y pesos, a cada una de las cuatro entregas calificadas; en las
prácticas de laboratorio (semanas 4 y 10) el criterio "Sustentación oral" no aplica y su peso (15 %) se redistribuye
proporcionalmente entre los demás criterios. La entrega de la semana 15 es la única que incluye sustentación oral
obligatoria.
Deficiente
Criterio Peso Excelente (18–20) Bueno (14–17) Regular (11–13)
(0–10)
El módulo implementa
correctamente todos Implementa la mayoría Implementa No implementa
los algoritmos exigidos de los algoritmos con parcialmente los los algoritmos
Correctitud funcional y
30 % (p. ej. FCFS/SJF/RR, resultados correctos; algoritmos o con exigidos o los
algorítmica
FIFO/LRU/Óptimo, fallas menores en casos errores que afectan resultados son
semáforos) y produce límite. algunos resultados. incorrectos.
resultados verificables.
Código modular,
Código difícil
legible, comentado, Código ordenado y Código funcional pero
de leer, sin
Calidad y organización con manejo de errores funcional, con desordenado o con
15 % comentarios ni
del código y control de versiones comentarios y control comentarios/versionad
control de
(commits claros en de versiones básico. o insuficientes.
versiones.
Git).
Informe completo: Informe incompleto o
Informe completo con No presenta
diseño, diagramas con
Documentación técnica 15 % diagramas básicos y informe o es
(procesos, memoria o diagramas/explicacion
conclusiones. mínimo.
E/S según el módulo), es insuficientes.

Deficiente
Criterio  Peso  Excelente (18–20)  Bueno (14–17)  Regular (11–13)
(0–10)
instrucciones de
ejecución y
conclusiones claras.
Compara
cuantitativamente los
|     | algoritmos (tiempos de  | Compara los  | Presenta datos sin  | No presenta  |
| --- | ----------------------- | ------------ | ------------------- | ------------ |
Análisis y comparación
15 %  espera, fallos de  algoritmos con datos,  comparación o análisis  análisis de
de resultados
|     | página, etc.) con  | discusión breve.  | superficial.  | resultados.  |
| --- | ------------------ | ----------------- | ------------- | ------------ |
gráficos y una
discusión crítica.
Explicación clara y
|     | ordenada del diseño e  | Explicación clara;  |     | No sustenta o  |
| --- | ---------------------- | ------------------- | --- | -------------- |
Explicación confusa o
Sustentación oral  implementación;  responde la mayoría de  no domina el
|     | 15 %  |     | dominio parcial del  |     |
| --- | ----- | --- | -------------------- | --- |
(aplica en semana 15)  responde con dominio  las preguntas con  proyecto
tema.
|     | las preguntas del  | seguridad.  |     | desarrollado.  |
| --- | ------------------ | ----------- | --- | -------------- |
jurado.
Entrega puntual,
Entrega fuera
|                         | participación  | Entrega puntual con  |                       |                |
| ----------------------- | -------------- | -------------------- | --------------------- | -------------- |
|                         |                |                      | Entrega con retraso   | de plazo o     |
| Trabajo en equipo y     | equilibrada y  | participación        |                       |                |
|                         | 10 %           |                      | leve o participación  | participación  |
| cumplimiento de plazos  | evidenciada    | mayoritariamente     |                       |                |
desigual.
|     |                     | equilibrada.  |     | de un solo   |
| --- | ------------------- | ------------- | --- | ------------ |
|     | (commits/roles) de  |               |     | integrante.  |
todos los integrantes.
VII. Recomendaciones para los docentes
•  Publicar la ficha técnica y las plantillas de informe junto con el sílabo desde la semana 1.
•  Usar las sesiones de laboratorio del sílabo (fork/exec en C, threading en Python, semáforos, simulación de
reemplazo de páginas) como espacio guiado para avanzar cada módulo antes de la fecha de entrega.
•  Reservar 10–15 minutos por equipo en la semana 15 ("Desarrollo Práctico") para la sustentación final, antes del
Examen Final de la semana 16.
•  Registrar las notas de las cuatro entregas como las prácticas/trabajos domiciliarios del sistema de evaluación
oficial del curso.