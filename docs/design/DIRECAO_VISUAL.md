# Direção visual v2 — "Salão de bilhar"

## Diagnóstico da v1
Fundo verde quase preto, cartões planos com borda fina, ícones genéricos, linguagem de dashboard. Funcional e acessível, mas sem marca: poderia ser o checkout de qualquer serviço.

## Direções avaliadas (e por que foram descartadas ou escolhidas)

| Direção | Ideia | Veredito |
|---|---|---|
| **A. Salão de bilhar contemporâneo** (escolhida) | Noite de bar + mesa vista de cima como superfície de UI; feltro, madeira, latão, bolas numeradas; placar esportivo | Reconhecível em 1 segundo, e a *própria mesa* vira o indicador de estado (útil, não só decorativo) |
| B. Arcade / neon | Néon, pixel, scanlines | Cansa, compete com o contraste do pagamento, envelhece rápido; neon excessivo era anti-requisito |
| C. Editorial premium (tipografia grande, fotografia) | Revista de luxo, poucas ilustrações | Exige fotografia (sem licença/asset) e perde o "jogo"; seria apenas outra variação minimalista |
| D. Snooker clássico (verde-inglês, serifa, madeira escura) | Clube de cavalheiros | Bonito, mas formal demais para bar e menos legível no celular |

Decisão: **A**, com ênfase em *estados como cena*: a posição da bola branca na mesa comunica o estágio (pagamento → ponto do botão → caçapa).

## Sistema
- **Cor** (tokens em `app.css`): noite `#0a0e0d`, feltro `#146b49`, madeira `#5a331d`, latão `#dcb86f`, marfim `#f4eedd`, giz `#7cc3f4` (foco e links). Status usam verde/âmbar/vermelho/azul funcionais. **Botão primário = cor da bola branca** (marfim sobre noite): o maior contraste da tela fica na ação.
- **Tipografia**: *Big Shoulders Display* (placar, números de mesa, títulos; vem de tipografia esportiva) + *Manrope* (texto). Duas famílias, 25 KB e 35 KB, locais.
- **Forma**: raios 10 (controles) e 16 (cartões); a mesa usa cantos de 16 e caçapas circulares.
- **Arte própria** (`art.js`): bolas numeradas 1–15 com listras corretas, brilho e sombra; mesa vista de cima com losangos de latão e 6 caçapas; taco com ponteira de giz; botão físico vermelho; logotipo (bola 8 com anel de latão). Tudo SVG gerado em JS, sem imagens.
- **Movimento**: ver `docs/qa/ANIMACOES.md`.

## Telas
- **Home**: abertura com tacada que abre o triângulo (uma vez por sessão); cada mesa é uma mini-mesa com luz acesa (livre), bolas espalhadas (em uso) ou coberta (sem conexão).
- **Pagamento**: "palco" (mesa em paisagem com o número da mesa no feltro), placar com valor grande, etapas em três barras, cartão de status com `aria-live`, bloco "Aperte o botão" com a ilustração do botão físico, CTA fixo na primeira tela.
- **Admin**: mesma identidade, sem animação distrativa; bola numerada identifica cada mesa; tabelas densas com cabeçalhos em latão.
- **Placas**: faixa de madeira com número da mesa, QR em caixa branca com margem de segurança, 3 passos numerados.

## Princípios usados na decisão (fontes obrigatórias)
`garden-skills` (declarar sistema antes do código; estados completos; sem "trust theater"), `emil-skills` (movimento só com `transform`/`opacity`, <300 ms para UI, press 0,97, sem animação em ações frequentes), `ai-design-skills` (uma família de display, hierarquia, estados), `mengto/skills` (motion explica causalidade; remover o que não tem função — ver `docs/qa/SKILLS_APLICADAS.md`).
