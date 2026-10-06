# Instalación y ejecución

## Plataforma

Usa Python 3.11 o superior para el entorno del simulador. Los componentes C dependen de POSIX, por lo que deben compilarse y ejecutarse en Linux o WSL. En Linux, instala GCC, GNU Make y el paquete de desarrollo de Python desde el gestor de paquetes de la distribución.

## Entorno Python

En PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

En Linux o WSL:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Estado de los comandos

`Makefile` declara tareas de instalación, pruebas y limpieza. Las fuentes C y Python parten como comentarios de diseño. El equipo añadirá los comandos de ejecución y pruebas funcionales al implementar cada módulo.
