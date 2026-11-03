# Redesign v2 — QA da nova interface

Branch `redesign-v2`. Backend, contratos da API do dispositivo, autenticação, CSRF, idempotência, auditoria e estados de comando **não foram alterados** (única mudança no backend: margem de segurança do QR de 2 para 4 módulos, o mínimo recomendado). Todo o frontend foi substituído.

## Antes / depois

| Tela | Antes (v1) | Depois (v2) |
|---|---|---|
| Home | `screenshots/v1/w390/01-home.png`, `v1/w1440/01-home.png` | `screenshots/v2/w390/01-home.png`, `v2/w1440/01-home.png` |
| Mesa livre | `v1/w390/02-mesa-livre.png` | `v2/w390/02-mesa-livre.png` |
| Aperte o botão | `v1/w390/06-aperte-o-botao.png` | `v2/w390/06-aperte-o-botao.png` |
| Liberada | `v1/w390/07-liberada.png` | `v2/w390/07-liberada.png` |
| Admin | `v1/w1440/13-admin-mesas.png` | `v2/w1440/13-admin-mesas.png` |
| Placas | `v1/w390/17-placas.png` | `v2/w768/17-placas.png` |
| Animação | — | `v2/animacao/bola-no-ponto-do-botao.png`, `bola-na-cacapa.png`, `paisagem-844x390.png` |

(capturas em `docs/qa/screenshots/`; o repositório guarda 320/390/768/1440 px; 360 e 1024 são geradas e testadas, mas só vão como artifact do CI.)

## Resultados

| Verificação | Resultado |
|---|---|
| Backend/integração (`unittest`) | **34/34** |
| Playwright: 17 telas/estados × 6 larguras (320, 360, 390, 768, 1024, 1440) com overflow, alvos ≥44 px e axe WCAG 2.2 AA | **102/102** |
| Playwright: jornadas (cliente, recusa, teclado, XSS, admin, CSP/requisições externas, API admin sem sessão) | **9/9** |
| Playwright: animação (7 cenários, ver `ANIMACOES.md`) | **7/7** |
| Total navegador | **118/118** |
| Lighthouse mobile (home / mesa / admin) | 100 / 100 / 100 desempenho; acessibilidade 100; boas práticas 100; **LCP 0,9 / 0,9 / 1,5 s; CLS 0** |
| Peso por página | 112–121 KiB (v1: 52–67 KiB) |
| ruff · bandit · pip-audit · npm audit | 0 · 0 · 0 · 0 |

Lighthouse v1 → v2 (mobile): desempenho 100 → 100/100/100, LCP 0,9–1,1 s → 0,9–1,5 s, peso quase dobrou (segunda fonte + ~35 KB de JS de arte). Regressão aceita e justificada: nenhuma queda de nota, LCP igual nas páginas do cliente. Medido em localhost; não representa 4G real. Dados: `docs/qa/lighthouse/resumo.json` (v1) e `resumo_v2.json`.

## Defeitos encontrados na v2 e correção (ciclo implementar → executar → inspecionar → corrigir → retestar)

| Defeito | Detecção | Correção | Reteste |
|---|---|---|---|
| Violação de CSP (`style` inline) ao montar os gradientes | console no 1º teste manual | removido `setAttribute('style')` | `flow.spec` (sem violação) |
| `SyntaxError: Identifier 'S' has already been declared` (scripts clássicos dividem escopo global) | `pageerror` | `art.js` e `stage.js` em IIFE | mesa/home carregam; 118/118 |
| Texto "false" e "undefined" visíveis (`replaceChildren` com valores falsos) | inspeção da captura | `.filter(Boolean)` | captura refeita |
| Moldura de madeira da home estourava a largura (texto cortado à direita) | inspeção da captura 390 | `.hero-art` sem `aspect-ratio` próprio | captura refeita; teste de overflow |
| Nome da mesa quebrava em "MESA/02" no admin | inspeção da captura 390 | cabeçalho do cartão em grade; selo abaixo do nome | captura refeita |
| Home em desktop com palco gigante (500 px) | inspeção da captura 1440 | layout em 2 colunas ≥960 px | captura refeita |
| Captura tirada no meio da tacada | inspeção | teste espera `getAnimations()` finito acabar | capturas estáveis |
| Home re-renderizava a cada 6 s (reiniciava animação de entrada) | revisão do código | assinatura dos dados; só re-renderiza se mudou; `reveal` só na 1ª vez | teste "uma vez por sessão" |
| Segunda fonte atrasava LCP (1,8 s) e causava CLS 0,025 | Lighthouse | `<link rel=preload>` da fonte de display | LCP 0,9 s, CLS 0 |
| Testes de animação reutilizavam mesas ocupadas | falha do teste | 5 mesas extras livres no setup de QA | 7/7 |

## Inspeção visual (imagens abertas e analisadas)
Vistas: home (390, 1440), pagamento livre/aguardando/aperte o botão/liberada (390), admin (390, 1440), placas (768), mais capturas intermediárias da tacada. Conclusões:
- Identidade reconhecível; mesa como indicador de estado; botão marfim é o maior contraste da tela; CTA na primeira tela em 390×800.
- Contraste: axe sem violações; textos claros sobre noite/feltro.
- Placa impressa: QR em caixa branca com margem, sem efeitos sobre os módulos. **Leitura automática:** `qa/tools/decode_qr.py` (OpenCV) decodificou os 16 QR codes de cada captura de placas (320, 768, 1440 px) apontando para `/mesa/NN`. Leitura por câmera de celular e impressão física **não** foram testadas.
- O nome hostil `<img onerror>` aparece como texto, quebrando linha sem estourar o cartão.
- Julgamento estético é subjetivo; sem teste com usuários.

## Segurança do novo frontend
Sem `innerHTML`/`eval`/`document.write`; DOM por `textContent`; CSP `script-src 'self'; style-src 'self'` sem inline; **0 requisições externas** e 0 erros de console nas 4 páginas públicas (teste); nenhuma credencial de dispositivo em respostas públicas (teste); todas as rotas `/api/admin/*` respondem 401 sem sessão (teste); `pip-audit` e `npm audit` sem vulnerabilidades.

## Não testado
Safari/iOS e Firefox (só Chromium); aparelhos reais e CPU/GPU fracas; leitor de tela real; câmera de celular lendo o QR impresso; impressão física (apenas CSS `@media print`).
