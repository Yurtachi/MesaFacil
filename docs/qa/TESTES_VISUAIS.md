# Testes visuais, acessibilidade e desempenho

Ferramentas: Playwright 1.64 (Chromium headless) + `@axe-core/playwright` (tags WCAG 2.0/2.1/2.2 A e AA) + Lighthouse. Capturas são de **navegador headless com viewport do tamanho do aparelho — não de aparelhos reais**. Estados são preparados por API real (nada de mock): `qa/tests/global-setup.js`.

## Matriz

6 larguras (320, 360, 390, 768, 1024, 1440) × 17 telas/estados = **102 casos, 102 aprovados**; mais 7 jornadas E2E (390 px) → **109/109**. Cada caso falha se houver: rolagem horizontal, elemento fora da viewport, botão/link com altura <44 px, ou qualquer violação axe.

Telas: home · mesa livre · aguardando pagamento · processando · enviando crédito · aperte o botão · liberada · recusada · em análise · mesa em uso · mesa inexistente · login admin · admin (mesas, histórico, auditoria, ajustes) · placas QR. Capturas em `docs/qa/screenshots/w<largura>/` (104 PNG, 7,8 MB). Não há captura separada de "pagamento falhou por erro de rede" nem de dispositivo físico.

## Inspeção visual (imagens abertas e analisadas)
Vistas: `w390/02`, `w390/06`, `w320/07`, `w768/03`, `w1440/13`, `w320/13`. Defeitos **reais** encontrados e corrigidos:

| Achado | Onde | Correção |
|---|---|---|
| Links/brand com 40 px e texto-link com 20 px de altura (alvo de toque <44) — 17 de 17 telas falhavam | todas | `min-height:44px` no brand e links do topo/rodapé |
| Região de tabela rolável sem foco por teclado (axe `scrollable-region-focusable`, grave) | histórico, auditoria | `tabindex=0 role=region aria-label` |
| Nome da mesa quebrava em "Me/sa/02" quando o selo era largo | admin 320–1440 | `flex-basis` + `word-break:normal`, selo desce de linha |
| Espaço entre legenda e etapas sumia (`margin:0` do `.steps` anulava o espaçamento) | checkout | removido o reset |
| Barra de ação fixa cobria o recibo na tela "liberada" | checkout 320 | barra fixa só na tela de pagar; demais ações no fluxo |
| Nome hostil não era exercitado (limite de 40 caracteres rejeitava o cenário) | setup de QA | cenário ajustado; teste prova que `<img onerror>` aparece como texto e nada executa |
| `aria-label` do logo diferente do texto visível (Lighthouse `label-content-name-mismatch`) | todas | removido o `aria-label` |

Avaliação: hierarquia clara (mesa → preço → etapas → status → ação), contraste alto (texto claro sobre `#07130e`; axe `color-contrast` sem violações), CTA na primeira tela em 390×800, sem rolagem horizontal. Julgamento visual é subjetivo; não houve teste com usuários.

## Acessibilidade
axe sem violações nas 102 combinações. Manual (automatizado): skip link recebe o primeiro foco; tabulação alcança links/botões; foco visível 3 px; região `aria-live` anuncia mudanças de etapa; `prefers-reduced-motion` testado (conteúdo preservado). **Não feito:** teste com leitor de tela real (NVDA/VoiceOver) e em aparelhos físicos, zoom do navegador a 200% real.

## Desempenho (Lighthouse 13, servidor local, throttling padrão mobile)

| Página | Perf | A11y | BP | LCP | CLS | TBT | Peso |
|---|---|---|---|---|---|---|---|
| Home (mobile) | 100 | 100 | 100 | 0,9 s | 0 | 0 ms | 52 KiB |
| Mesa (mobile) | 100 | 100 | 100 | 0,9 s | 0 | 0 ms | 59 KiB |
| Admin (mobile) | 100 | 100 | 100 | 1,1 s | 0 | 10 ms | 67 KiB |
| Desktop (3 páginas) | 100 | 100 | 100 | 0,2–0,3 s | 0 | 0 ms | 52–67 KiB |

Dados brutos: `docs/qa/lighthouse/resumo.json`. Medido em **localhost**: não representa 4G real nem celular simples. Polling: 2 s no cliente (recua para 6 s após 2 min; pausa com a aba oculta; para ao concluir), 3 s no admin; ETag nos estáticos; sem fontes/CDN externos; uma fonte de 25 KB.
