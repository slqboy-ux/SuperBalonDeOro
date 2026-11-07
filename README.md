# SuperBalon

SuperBalon es un prototipo de liga casual para grupos de amigos que quieren organizar partidos, armar equipos al azar, registrar resultados y seguir una tabla de posiciones.

La idea central: simplificar la experiencia para que una temporada se pueda jugar sin planillas ni WhatsApp caóticas.

## Qué incluye este MVP
- carga de jugadores
- generación aleatoria de equipos
- registro de partidos con goles
- cálculo de tabla de posiciones
- resumen de campeón
- edición del nombre de la temporada

## Estado del proyecto
Este es un MVP de validación pensado para mostrar la idea, probarla con amigos y decidir si conviene seguir con una segunda versión más completa.

## Requisitos
- Python 3.12+

## Cómo correrlo localmente

```powershell
cd backend
python -m pip install -r requirements.txt
python -m uvicorn app:app --host 0.0.0.0 --port 8000
```

Luego abrir:

- http://localhost:8000/

## API principal

- GET /health
- GET /config
- POST /config
- GET /players
- POST /players
- DELETE /players
- POST /teams/generate
- GET /teams
- POST /matches
- GET /matches
- GET /standings
- GET /summary

## Texto para compartir con amigos

> Probá SuperBalon: la app para armar equipos, jugar una temporada y ver quién queda campeón entre amigos.

También podés usar el archivo [friend-share.md](friend-share.md).

## Deploy gratis

1. Subir este proyecto a GitHub.
2. Crear un servicio Web en Render.
3. Conectar el repo.
4. Usar la configuración del archivo [render.yaml](render.yaml).
5. Hacer deploy.

El backend sirve también el frontend estático desde la misma app.

## Próximo paso recomendado

- probar con 3 a 5 amigos reales
- pedir feedback de flujo y utilidad
- definir si conviene una segunda iteración con mejor UX y persistencia más robusta
