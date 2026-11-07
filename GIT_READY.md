# GitHub handoff checklist

## Repo status
- La carpeta del proyecto ya está preparada como base de demo.
- El MVP funciona localmente con FastAPI + frontend estático.
- El código ya está ordenado para ser subido a GitHub.

## Archivos principales
- README.md: presentación general del proyecto
- DEMO_PITCH.md: pitch breve para mostrar la idea
- NEXT_STEPS.md: plan siguiente
- backend/app.py: API del MVP
- frontend/index.html: vista principal
- frontend/app.js: flujo de la app
- frontend/styles.css: estilos visuales
- render.yaml: configuración para deploy gratuito
- start-demo.ps1: arranque rápido en Windows

## Siguiente paso en GitHub
1. crear el repositorio en GitHub
2. hacer commit inicial
3. hacer push
4. abrir el repo y dejarlo listo para seguir

## Commit sugerido
```
git init
git add .
git commit -m "Initial MVP demo for SuperBalon"
git branch -M main
git remote add origin <url-del-repo>
git push -u origin main
```

## Objetivo de esta primera versión
- demostrar la idea
- mostrar el flujo principal
- permitir validación con amigos
- no priorizar deploy ni arquitectura final
