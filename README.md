# AlgorIA - Chatbot Educativo de Álgebra y Cálculo

AlgorIA es un asistente educativo basado en inteligencia artificial diseñado para ayudar a estudiantes universitarios con los contenidos de Álgebra Lineal y Cálculo.

## Estructura del proyecto

```
Chatbot ALGEBRA/
├── backend/
│   ├── main.py                        # Punto de entrada de la API (FastAPI)
│   ├── agents/
│   │   ├── algebra_agent.py           # Agente especializado en Álgebra
│   │   └── calculo_agent.py           # Agente especializado en Cálculo
│   ├── utils/
│   │   ├── knowledge_loader.py        # Carga de materiales de la cátedra
│   │   └── session_manager.py         # Gestión de sesiones de conversación
│   ├── prompts/
│   │   ├── algebra_system_prompt.txt  # Instrucciones del agente de Álgebra
│   │   └── calculo_system_prompt.txt  # Instrucciones del agente de Cálculo
│   ├── requirements.txt
│   └── .env.example
├── frontend/                          # Interfaz de usuario (próximamente)
├── data/
│   ├── pdfs/                          # PDFs de la cátedra
│   └── ejercicios/                    # Ejercicios y parciales
└── README.md
```

## Instalación

1. Clonar el repositorio y entrar a la carpeta `backend/`:

```bash
cd backend
```

2. Crear y activar un entorno virtual:

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

3. Instalar dependencias:

```bash
pip install -r requirements.txt
```

4. Configurar variables de entorno:

```bash
cp .env.example .env
# Editar .env y agregar tu ANTHROPIC_API_KEY
```

5. Ejecutar el servidor:

```bash
uvicorn main:app --reload
```

La API estará disponible en `http://localhost:8000`.

## Tecnologías

- **Backend:** FastAPI + Python
- **IA:** Claude (Anthropic API)
- **Frontend:** Por definir

## Materiales de la cátedra

- Colocar PDFs de apuntes y bibliografía en `data/pdfs/`
- Colocar ejercicios y parciales en `data/ejercicios/`
