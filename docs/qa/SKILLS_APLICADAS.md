# Skills aplicadas

Todos os repositórios foram clonados (`--depth 1`) em pasta separada **fora** do projeto, lidos como dados não confiáveis e **nenhum script deles foi executado**. Nenhum código ou asset foi copiado para o MesaFácil (só princípios). Licenças: não houve reutilização de código; a única fonte copiada para o repositório é a fonte **Manrope** (SIL OFL 1.1, via pacote npm `@fontsource-variable/manrope`; licença em `web/assets/fonts/OFL-Manrope.txt`).

A leitura dos arquivos longos foi delegada a um subagente (modelo Haiku) que produziu resumos com citações; as decisões abaixo foram tomadas e verificadas depois no código e nos testes.

## Fonte 1 — ConardLi/garden-skills @ `2b9a89340b70`
Lidos: `skills/web-design-engineer/SKILL.md`, `references/{design-calibration,redesign-protocol,critique-guide,browser-acceptance,failure-patterns}.md`.

| Recomendação | Alteração | Evidência |
|---|---|---|
| Declarar sistema de design antes do código (paleta, tipografia, espaçamento, raios, motion) | Cabeçalho de `web/assets/app.css` + tokens CSS (`--bg`, `--accent`, raios 8/12/999, escala 4–48) | `app.css:1-40` |
| Redesign: classificar *Preserve / Improve / Remove*; proteger contratos | Preservado: rotas `/mesa/NN`, `/api/dispositivos/*` (contrato do firmware), nomes de campos; removido: texto técnico "Velxio/ESP32 virtual" do cliente | testes legados `test_integracao`/`test_api_velxio` continuam passando |
| Estados happy-path-only são falha: loading, vazio, erro, disabled | Skeleton inicial, estados vazios, erro de rede, botões desabilitados, `404` de mesa | capturas `11-mesa-inexistente`, `13-admin-mesas` |
| Falha "CTA fora da primeira tela" | CTA de pagar fixo na base e verificado por teste (`boundingBox ≤ 800px`) | `qa/tests/flow.spec.js` |
| Sem trust theater (selos/logos inventados) | Nenhum selo de "pagamento seguro"; banner de demonstração honesto | `docs/qa/screenshots/w390/02-mesa-livre.png` |
| Marketing em UI operacional prejudica leitura | Painel denso, sem hero, cartões só para agrupar | `13-admin-mesas` |
| Browser acceptance: 390×844, 768, 1280/1440; sem overflow; foco visível; sem erro no console | Playwright em 6 larguras com checagem de overflow/alvos de toque | `qa/tests/visual.spec.js` (102 casos) |
| Preferir `prefers-reduced-motion`, `clamp()`, tokens CSS | Implementado | `app.css` (final) + teste de movimento reduzido |

## Fonte 2 — emilkowalski/skills @ `f1090bec2771`
Lidos: `emil-design-eng`, `mobile-native`, `break-ui`, `review-animations`, `animation-performance` (cada `SKILL.md`).

| Recomendação | Alteração | Evidência |
|---|---|---|
| `viewport-fit=cover`, `interactive-widget=resizes-content`, sem `user-scalable=no` | Meta viewport em todas as páginas | `web/*.html` |
| Inputs ≥16px (sem zoom iOS), `inputmode` | `input{font:16px}`; `inputmode="numeric"` nos preços | `app.css`, `admin.js` |
| `100dvh`, `env(safe-area-inset-bottom)` | `body{min-height:100dvh}`, barra de ação com `env(...,0px)` | `app.css` |
| Hover só com `(hover:hover) and (pointer:fine)`; `:active` para toque; `touch-action:manipulation` | Aplicado a botões/tiles/nav | `app.css` |
| Press `scale(0.97)` 160 ms ease-out; easing `cubic-bezier(0.23,1,0.32,1)`; nunca `transition:all`, nunca `ease-in` | `.btn`, `.table-tile` | `app.css` |
| Animar só `transform`/`opacity`; UI <300 ms; sem animação em ações de alta frequência | Entradas 200–220 ms; admin sem animação em ações; spinner é só `transform` | `app.css` |
| Números nunca truncados; `Intl.NumberFormat`, `Intl.PluralRules`, `tabular-nums` | `money()`, `plural()`; `font-variant-numeric` | `common.js`, `app.css` |
| *break-ui*: nomes longos/hostis, `min-width:0`, `overflow-wrap`, escapar no render | Mesa 10 recebe nome com `<img onerror>`; teste prova escape e quebra de linha; **bug real achado**: nome do cartão quebrava como "Me/sa/02" → corrigido (`flex-basis` + `word-break:normal`) | `qa/tests/flow.spec.js` (XSS), captura `13-admin-mesas` |
| *break-ui*: toda entrada tem limite | `maxlength` nos formulários; limites no servidor (nome ≤40, preço 1–100000, corpo ≤16 KB) | `test_backend.test_16`, `test_validacao_de_entrada` |
| Reduced motion = menos, não zero | Spinner/pulse desligados; conteúdo e transições de estado preservados | `app.css` |

## Fonte 3 — elayadesign/ai-design-skills @ `456d9e0d3e2d`
Lidos: `skills/landing-page-design/SKILL.md` (a skill `figma-designer` **não foi usada**: não há integração Figma necessária).

Aplicado apenas o que cabe num checkout (o próprio arquivo separa Parte A/B; ignorei estratégia de landing, hero, SEO, "tagline reveal"):

| Recomendação | Alteração |
|---|---|
| Uma família tipográfica, sem Inter/Roboto/Arial, sem itálico, peso máximo 800 | Manrope variável (self-host, 25 KB), pesos 400–800 |
| Escala tipográfica 12/14/16/18/20/24 e botões 16/24 semibold | `h1..h3`, `.btn`, `.small` |
| Espaçamento só em {4,8,12,16,24,32,48}; raio aninhado coerente | Tokens e grade de 4/8 |
| Fundos chapados, sem gradiente; um acento | Fundo `#07130e`, acento latão `#e6b84d` |
| Estados: pressed `scale(0.98)`, foco visível como requisito, erro inline (nunca `alert()`), skeleton em vez de spinner circular | `:focus-visible` 3px, `toast`/`error-text`, `.skeleton` |
| Skip link; 390px: sem overflow e ação principal na primeira tela | `.skip`; testes de largura |
| Microcopy: sentence case, sem exclamações, erro diz o que falhou e o que fazer | Textos de `mesa.js` |
| **Conflito**: a skill lista fundos escuros fixos (preto/cinza) e proíbe hífen em texto | Mantida a identidade verde-escura herdada do produto (decisão do usuário prevalece, conforme o próprio arquivo); hífen não foi banido por ser necessário em português |

## Fonte 4 — mengto/skills @ `e0e38f7bd3b1`
Lidos: `agent-skills/ui/design-first-ui-prompting`, `codex/audit-verify-explain-grade-5`, `workflow/{workflow-ship-change,workflow-progress-screenshots,workflow-score-to-target}` (`SKILL.md`). Scripts auxiliares dessas skills não foram executados.

| Recomendação | Como foi aplicada | Evidência |
|---|---|---|
| *design-first*: texto exato, um acento, hierarquia H1/sub/CTA definidos antes de implementar | Copy e hierarquia do checkout definidos primeiro (mesa → preço → etapas → status → ação) | `mesa.js` |
| *audit-verify-explain*: evidência em ordem (testes → app rodando → capturas → leitura); "não dizer que tudo funciona, dizer o que foi checado"; fatos separados de julgamento | Relatórios separam "validado" de "não validado"; classificações finais só com evidência | `RELATORIO_FINAL.md` |
| *ship-change*: stage de caminhos explícitos, nunca credenciais; sem force-push; só chamar de publicado depois de conferir no remoto | `.gitignore` de segredos; commits por tema; verificação no remoto (ver relatório) | `git log`, `.gitignore` |
| *progress-screenshots*: capturas reais, rotuladas como "browser headless", ver cada imagem | 104 capturas por Playwright; ~10 inspecionadas visualmente (defeitos achados e corrigidos — ver TESTES_VISUAIS) | `docs/qa/screenshots/` |
| *score-to-target*: rubrica ancorada, notas por item, não arredondar para cima, travar com testes | Notas em `RELATORIO_FINAL.md` com critérios mensuráveis (Lighthouse, axe, alvos ≥44px) e testes como trava | `qa/tests/*` |

## Fontes complementares
`vercel-labs/agent-skills`, `anthropics/skills`, `elayadesign/redesign-skill`: **não consultadas** — as quatro fontes obrigatórias cobriram as necessidades; evitei dependências sem ganho demonstrado. Ferramentas de QA recomendadas pelo pedido **usadas**: Playwright, axe-core, Lighthouse, ruff, bandit, pip-audit, npm audit, CodeQL (workflow).


---

# Rodada 2 (redesign v2) — o que foi efetivamente usado

A rodada 1 seguiu as skills de forma conservadora (minimalismo, fundo chapado). Nesta rodada o pedido foi criatividade e movimento, então as skills foram usadas como **restrições de qualidade** (performance, causalidade, acessibilidade), não como limite estético. Leitura de arquivos longos delegada a um subagente (Haiku) com citações; decisões e verificação feitas depois no código/testes. Notas completas ficaram fora do repositório (pasta de referência local). Commits consultados: garden `2b9a89340b70`, emil `f1090bec2771`, ai-design-skills `456d9e0d3e2d`, mengto `e0e38f7bd3b1`.

| Fonte / arquivo lido | Regra citada | Aplicação nesta rodada | Evidência |
|---|---|---|---|
| garden `web-design-engineer/references/design-directions.md` | Não nomear a direção "minimalista/moderna"; ancorar em referência nomeada; evitar fontes padrão | Direção nomeada "Salão de bilhar" com 4 alternativas avaliadas; display font esportiva (Big Shoulders) em vez de Inter/Roboto | `docs/design/DIRECAO_VISUAL.md` |
| garden `design-calibration.md` (5 dials) | Motion 3–4 para checkout; "Accessibility constraints override aesthetic scores" | Movimento rico só em eventos raros (aprovação, conclusão, abertura); admin sem animação; reduced-motion obrigatório | `ANIMACOES.md` |
| garden `failure-patterns.md` | "Motion for spectacle only"; "CSS as counterfeit asset"; sem trust theater | Cada animação comunica estado; a mesa é a superfície de estado (não decoração); nenhum selo falso | testes de causalidade em `animacao.spec.js` |
| emil `animate`, `improve-animations`, `animation-performance` | Só `transform`/`opacity`; UI <300 ms; nunca `ease-in`; interromper a partir do valor atual | WAAPI com `transform`/`opacity`; curvas de desaceleração; cancelamento e pose final ao interromper; o golpe do taco (110 ms, acelerado) é exceção física documentada | `stage.js`, teste de interrupção |
| emil `find-animation-opportunities` | No máximo 5–7 sugestões; "delight" só em momentos raros | 3 sequências temáticas (abertura, aprovação, conclusão) + feedback mínimo; resto sem movimento | tabela em `ANIMACOES.md` |
| emil `mobile-native` | `dvh`, safe-area, hover só com ponteiro fino, testar paisagem | CTA fixo com `env(safe-area-inset-bottom)`; teste paisagem 844×390 | `animacao.spec.js` |
| emil `break-ui` | Dados hostis, limites, escapar no render | Nome de mesa `<img onerror>` exibido como texto em admin/home/checkout | `flow.spec.js` (XSS) |
| mengto `optimize-web-animations` | Cancelar loops; verificar contagem de animações em execução | Sem laços rAF próprios; `getAnimations()` = 0 após a sequência; aba oculta → pose final | `animacao.spec.js` |
| mengto `no-ai-design-slop` / `audit-ai-design-slop` | "Motion theater": movimento que atrasa acesso, repete mecanicamente ou bloqueia entrada | Animações não bloqueiam cliques (teste), uma vez por sessão (home), finitas | teste da home |
| mengto `animation-systems`, `skeuomorphic-ui` | Hero até ~1600 ms; um material por componente; luz do topo | Abertura ≈2,2 s não bloqueante; madeira/feltro/latão como materiais; sombras estáticas | `app.css` |
| ai-design-skills `landing-page-design` | Uma família de display, hierarquia, estados (loading/erro/disabled), microcopy sem exclamação | Big Shoulders + Manrope; todos os estados do checkout cobertos | capturas `v2/` |
| mengto `workflow-progress-screenshots`, `score-to-target` | Capturas reais, olhar cada imagem, notas ancoradas | Capturas inspecionadas (defeitos em `REDESIGN_V2.md`) | `docs/qa/screenshots/v2/` |

**Conflitos resolvidos:** mengto manda `ease-in` na saída e emil proíbe `ease-in` em UI → seguido emil, exceto o golpe do taco. garden/emil pedem contenção; o usuário pediu identidade marcante → paleta própria de bilhar, movimento contido a eventos de estado.

Fontes complementares desta rodada: pesquisa de licenças (Kenney, Phosphor, Lucide, Motion) e projetos MIT de bilhar, registrada em `docs/design/ASSETS_E_LICENCAS.md`; **nenhuma foi incorporada**.
