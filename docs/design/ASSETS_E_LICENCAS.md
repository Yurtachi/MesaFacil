# Assets e licenças

## Incluídos no repositório

| Recurso | Origem | Licença | Onde |
|---|---|---|---|
| Fonte **Manrope** (variável, subconjunto latin) | pacote npm `@fontsource-variable/manrope` | SIL OFL 1.1 | `web/assets/fonts/manrope-latin.woff2`, `OFL-Manrope.txt` |
| Fonte **Big Shoulders Display** (variável, latin) | pacote npm `@fontsource-variable/big-shoulders-display` | SIL OFL 1.1 | `web/assets/fonts/bigshoulders-latin.woff2`, `OFL-BigShouldersDisplay.txt` |
| Bolas, mesas, taco, botão, logotipo, animações | **Criados para este projeto** (SVG gerado em JS, `art.js`/`stage.js`) | Do projeto | `web/assets/` |
| Ícones de status (check, relógio, alerta, QR…) | Caminhos SVG simples escritos à mão | Do projeto | `common.js` |

Não há imagens, vídeos, fotos de stock, CDN, nem scripts externos. A textura do feltro foi **descartada** (usa gradiente SVG), para manter o peso baixo.

## Pesquisados e NÃO incluídos (com motivo)

| Recurso | Licença verificada | Decisão |
|---|---|---|
| Kenney "Rolling Ball Assets" (kenney.nl; repo `shorepine/kenney`) | CC0 segundo a página (resumo; download direto retornou 403); repo `shorepine/kenney` marcado "Other" (LICENSE de outro pacote) | Não usado: são modelos 3D/sprites de jogo, estilo diferente; o tratamento artístico próprio de bolas/tacos foi pedido. Se for usar um pacote, conferir o README do pacote específico |
| Phosphor Icons (`phosphor-icons/core`) | MIT | Não usado: os poucos ícones necessários foram desenhados à mão; evita dependência |
| Lucide (`lucide-icons/lucide`) | ISC (+MIT para ícones derivados do Feather) | Idem |
| Motion (`motiondivision/motion`) | MIT | Não usado: a Web Animations API nativa cobre tacada/rolamento/caçapa; evita ~20+ KB de JS |
| Projetos de bilhar open source (ex.: `henshmi/Classic-Pool-Game`, MIT) | MIT | Apenas pesquisados; física de jogo não é necessária (animação é cenográfica, determinística) e identidade visual de terceiros não deve ser copiada |

Notas: as licenças foram consultadas por API/leitura no dia da pesquisa; não foi feito download dos pacotes. Não há nenhuma obrigação de atribuição pendente além de manter os textos OFL junto das fontes.
