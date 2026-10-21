# Frontend ToolMesh

## Connexion Keycloak

Les liens de connexion de la page publique et du header doivent conserver
`reloadDocument: true` dans leurs `linkProps`. Avec une API sur la même origine
(`VITE_API_URL=""`, comme dans l'image Docker), React Router intercepterait sinon
`/api/auth/login` comme une route de la SPA et afficherait une page 404 au lieu
de laisser le backend rediriger le navigateur vers Keycloak.

Les tests Playwright utilisent cette configuration même origine et vérifient
que le clic sur chacun des deux liens déclenche une navigation complète vers
le backend (réponse simulée), et non une navigation interne à la SPA :

```bash
bun run test:e2e e2e/login.spec.js
```

## React + Vite

This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Oxc](https://oxc.rs)
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/)

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the ESLint configuration

If you are developing a production application, we recommend using TypeScript with type-aware lint rules enabled. Check out the [TS template](https://github.com/vitejs/vite/tree/main/packages/create-vite/template-react-ts) for information on how to integrate TypeScript and [`typescript-eslint`](https://typescript-eslint.io) in your project.
