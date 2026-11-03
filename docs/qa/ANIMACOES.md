# Animações

## Tecnologia
**SVG + Web Animations API (WAAPI) + CSS.** Sem biblioteca e sem Canvas/3D: o movimento é cenográfico e determinístico (não é simulação de física), então 2D nativo entrega a mesma qualidade, com 0 KB extra, execução no compositor para `transform`/`opacity` e cancelamento limpo (`Animation.cancel()`). Three.js, Motion e Canvas foram avaliados e descartados (ver `docs/design/ASSETS_E_LICENCAS.md`).

## Sequências implementadas

| # | Onde | Gatilho | Coreografia | Duração |
|---|---|---|---|---|
| 1 | Home | 1ª visita da sessão | Taco recua (520 ms, `cubic-bezier(.3,0,.2,1)`), golpeia (110 ms), bola branca rola e **abre o triângulo**; 10 bolas se espalham com desaceleração e giro | ≈2,2 s |
| 2 | Pagamento | `etapa` passa a `aguardando_botao` (**pagamento aprovado**) | Tacada; a bola branca rola 120 px, desacelera (`cubic-bezier(.12,.7,.25,1)`) e **para no ponto do botão** (anel de latão). Não vai à caçapa | ≈1,6 s |
| 3 | Pagamento | `etapa` passa a `concluido` (**acionamento concluído confirmado pelo backend**) | Bola rola até a caçapa, cai (escala 1→0,5 + fade) e a caçapa acende em verde | ≈0,9 s |
| 4 | Pagamento | `processando` | Anéis de giz expandem 5×; spinner no ícone (limitado) | finito |
| 5 | Pagamento | `aguardando_botao` e comando recebido | Anéis pulsantes ao redor do botão físico (6 ciclos, depois parado) | ≈ 8 s, finito |
| 6 | Geral | clique/entrada | Press `scale(.97)` 160 ms; entrada de status 260 ms `ease-out` | <300 ms |

## Regras de honestidade (causalidade)
- A caçapa **só** existe para `etapa === 'concluido'`, que o backend só emite após o controlador reportar o acionamento concluído. Pagamento aprovado leva a bola **ao ponto do botão**, nunca à caçapa.
- O palco **lê** o estado; nunca o decide. Sem animação, o estado continua legível pelo texto, ícone, barras de etapa e `aria-live`.
- Carga de página com estado já avançado (reload) → **pose final direta**, sem replay.
- Estado muda durante a animação → animações canceladas e pose final correta aplicada.
- Aba oculta, `prefers-reduced-motion`, ou erro de WAAPI → pose final imediata; fluxo transacional não depende da animação.
- Nenhuma animação infinita: ciclos finitos (`animation-iteration-count` 5–40 para spinners) e `iterations: 1` no restante; o polling (2 s) para ao concluir.

## Testes (`qa/tests/animacao.spec.js`, Chromium 390 px) — 7/7
1. Aprovação → animação roda, bola para em x≈190 (ponto do botão), opacidade 1, `getAnimations()` = 0; **só depois do ACK** a bola some na caçapa; reload mantém pose sem animar.
2. ACK durante a tacada (250 ms) → pose final `concluido`, 0 animações órfãs.
3. Movimento reduzido → 0 animações do palco, pose final imediata.
4. Duplo clique em "aprovar" → **1** requisição; rede offline durante a transição → aviso "Sem conexão", sem erro de página; redimensionar 390→360 sem overflow.
5. Paisagem 844×390 (home e checkout) sem rolagem horizontal.
6. Home: animação roda, clique na mesa funciona durante ela, 2ª visita sem animação.
7. Fluidez durante a sequência: **157 quadros, média 16,6 ms, máx. 17 ms, 0 tarefas longas** (Chromium headless, máquina de desenvolvimento).

Capturas: `docs/qa/screenshots/v2/animacao/` (bola no ponto do botão, bola na caçapa, paisagem).

## Limites
Medido em Chromium headless desktop; **não** em celular simples real (GPU/CPU fracas) nem com throttling de CPU. Quadros em Safari/iOS e Firefox não foram testados. Se o aparelho for muito lento, a defesa é a pose final imediata quando WAAPI falha ou a aba está oculta; não há detecção de "baixo desempenho".
