# Changelog

## [0.7.0-rc](https://github.com/IA-Generative/toolmesh/compare/v0.6.2...v0.7.0-rc) (2026-10-22)


### Features

* **docs:** new screenshots ([0aacd36](https://github.com/IA-Generative/toolmesh/commit/0aacd36f829c06a244d83bbd319560434b975136))
* **front:** add useAppVersion component and add fetchVersion ([e283791](https://github.com/IA-Generative/toolmesh/commit/e28379143ce7b204a4e4e5144a519d10c88af8b4))
* **front:** add version in Sidebar and Footer ([68aa0fb](https://github.com/IA-Generative/toolmesh/commit/68aa0fb4fa140cc6d8eab901fecd5d50fc3b88fc))


### Bug Fixes

* **docs:** add version in screenshots ([47d13d7](https://github.com/IA-Generative/toolmesh/commit/47d13d74d97f508abe09a200d97e152f28f64ddb))
* **docs:** regenerate screenshots after rebase ([654c0f9](https://github.com/IA-Generative/toolmesh/commit/654c0f973abd68884f282af47d25bf7e4e3a39a3))
* **front:** remove bullits in home page and put footer at bottom landing page ([45571af](https://github.com/IA-Generative/toolmesh/commit/45571af59cb6337929703ab075a4e07aa560adad))

## [0.6.2](https://github.com/IA-Generative/toolmesh/compare/v0.6.1...v0.6.2) (2026-10-21)


### Bug Fixes

* **backend:** stop checking the audience of incoming tokens ([50c4d43](https://github.com/IA-Generative/toolmesh/commit/50c4d43d2818ff1337e4dffcbc7f9dc630341f50))
* **frontend:** force full navigation for Keycloak login ([1ba7204](https://github.com/IA-Generative/toolmesh/commit/1ba72048ddc05ae6bb2e289f812feaaa64a4a021))

## [0.6.1](https://github.com/IA-Generative/toolmesh/compare/v0.6.0...v0.6.1) (2026-10-21)


### Code Refactoring

* **backend:** use python-keycloak with a single Keycloak client ([ab2e8d5](https://github.com/IA-Generative/toolmesh/commit/ab2e8d5cc2805be16cefb442305cf7df9889839b))

## [0.6.0](https://github.com/IA-Generative/toolmesh/compare/v0.5.0...v0.6.0) (2026-10-21)


### Features

* **front:** add app layout with sidebar, topbar and user menu ([f807e0f](https://github.com/IA-Generative/toolmesh/commit/f807e0f3e588e50145f41f539b33606c47842af0))
* **front:** add home page, protected routes and 404 page ([b442190](https://github.com/IA-Generative/toolmesh/commit/b442190bbf768da3084c0e5f1d543fb5005cda01))
* **front:** prepare new layout and search modal ([8232d49](https://github.com/IA-Generative/toolmesh/commit/8232d494a7eddb7dc1eeffe9c6e01e405dbead24))

## [0.6.0-rc](https://github.com/IA-Generative/toolmesh/compare/v0.5.0...v0.6.0-rc) (2026-10-21)


### Features

* **front:** add app layout with sidebar, topbar and user menu ([bc24a6e](https://github.com/IA-Generative/toolmesh/commit/bc24a6e0db76af6975bc4223a0f5e2f89269b04e))
* **front:** add home page, protected routes and 404 page ([9ad2f0b](https://github.com/IA-Generative/toolmesh/commit/9ad2f0b2545f2c57668f3f45969dc3a35996f06a))
* **front:** prepare new layout and search modal ([ae534d4](https://github.com/IA-Generative/toolmesh/commit/ae534d4469dbb65db52e9745364e631138def88a))

## [0.5.0](https://github.com/IA-Generative/toolmesh/compare/v0.4.0...v0.5.0) (2026-10-20)


### Features

* **frontend:** containerize the SPA and deploy it with the chart ([4fc5775](https://github.com/IA-Generative/toolmesh/commit/4fc577519681b84b76722339127e6fe66770689d))


### Bug Fixes

* **chart:** remove a duplicated backend block in common-values ([4379e10](https://github.com/IA-Generative/toolmesh/commit/4379e104308d3cc97aa7e27584aff8dcf2cb97da))
* **frontend:** run the image as the unprivileged nginx user ([133f351](https://github.com/IA-Generative/toolmesh/commit/133f35185623cd5ba3c2399983c676500704c7de))

## [0.4.0](https://github.com/IA-Generative/toolmesh/compare/v0.3.0...v0.4.0) (2026-10-20)


### Features

* **auth:** add /api/auth/token and /refresh for non-browser clients ([293a1ff](https://github.com/IA-Generative/toolmesh/commit/293a1ffa1585b714be28ca89ca1a869328946bd8))
* **auth:** add BFF session login for web SPAs ([ce486c9](https://github.com/IA-Generative/toolmesh/commit/ce486c98a3044f1b1150c0a76b8edb76dfb5f0be))
* **chart:** rebuild helm chart on this-is-tobi component templates ([e6a4e5a](https://github.com/IA-Generative/toolmesh/commit/e6a4e5ada41c435054edc44356634d228bb12fca))
* **front:** add DSFR SPA with BFF Keycloak login ([4f80d5d](https://github.com/IA-Generative/toolmesh/commit/4f80d5d19069c759eb611121cb4d0ddc0016fa4b))

## [0.4.0-rc](https://github.com/IA-Generative/toolmesh/compare/v0.3.0...v0.4.0-rc) (2026-10-20)


### Features

* **auth:** add /api/auth/token and /refresh for non-browser clients ([f470af1](https://github.com/IA-Generative/toolmesh/commit/f470af1b7a9978881febff5f9c5912b825ef7720))
* **auth:** add BFF session login for web SPAs ([5a4cb8e](https://github.com/IA-Generative/toolmesh/commit/5a4cb8ed2c5df1f4131a11ea93cb34e7afda27b2))
* **front:** add DSFR SPA with BFF Keycloak login ([cd6dcad](https://github.com/IA-Generative/toolmesh/commit/cd6dcadf876190ce4d25fe4e7636aa0af39b9325))

## [0.3.0](https://github.com/IA-Generative/toolmesh/compare/v0.2.0...v0.3.0) (2026-10-13)


### Features

* add Keycloak authentication, token exchange and datetime MCP server ([a2ef4a9](https://github.com/IA-Generative/toolmesh/commit/a2ef4a963833c948b60344a79d8470ba21edac91))


### Bug Fixes

* **mcp-datetime:** add HEALTHCHECK to the Dockerfile ([a6e0242](https://github.com/IA-Generative/toolmesh/commit/a6e0242a389149c235744d33e479d2b87e5a8301))

## [0.3.0-rc.1](https://github.com/IA-Generative/toolmesh/compare/v0.3.0-rc...v0.3.0-rc.1) (2026-10-13)


### Bug Fixes

* **mcp-datetime:** add HEALTHCHECK to the Dockerfile ([5d98c88](https://github.com/IA-Generative/toolmesh/commit/5d98c88d6554ad1ac54277d2e25e3a49de2d58d6))

## [0.3.0-rc](https://github.com/IA-Generative/toolmesh/compare/v0.2.0...v0.3.0-rc) (2026-10-13)


### Features

* add Keycloak authentication, token exchange and datetime MCP server ([01bdd05](https://github.com/IA-Generative/toolmesh/commit/01bdd05026d176d882ccdcf8c9d9ffe4215ce680))

## [0.2.0](https://github.com/IA-Generative/toolmesh/compare/v0.1.0...v0.2.0) (2026-10-13)


### Features

* add CI/CD pipeline and FastAPI backend skeleton ([0081f67](https://github.com/IA-Generative/toolmesh/commit/0081f67711700bfd8ccbf4b6203b676ca6bcae86))
