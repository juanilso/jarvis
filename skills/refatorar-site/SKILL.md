---
name: refatorar-site
description: Método do Jarvis para refatorar ou construir um site com qualidade visual de agência - inventário do conteúdo, direção visual, sistema de design, home completa primeiro, página por página, nota visual e testes. Use em qualquer pedido de refatorar, redesenhar, modernizar, "deixar bonito" ou construir site/landing page.
---

# Refatorar (ou construir) um site

Objetivo: o usuário ver um site **bonito e funcionando cedo**, e não horas de preparação sem nada na tela.
Carregue também a skill `frontend-design` (direção visual) e siga as duas.

## Regras que evitam os erros mais comuns
1. **Nunca perca conteúdo.** Refatorar muda a cara, não apaga textos, páginas, imagens, links ou SEO do site antigo.
2. **Nada de HTML aparecendo como texto.** Conteúdo que já é HTML (posts, descrições do banco/CMS) é renderizado como
   HTML (sanitizado), nunca escapado de novo. `<p>`, `&copy;`, `</strong>` visíveis na página = erro grave.
3. **Nada de aparência padrão do navegador.** Todo elemento visível tem estilo do sistema de design: links (nada de
   azul/roxo sublinhado padrão), listas, tabelas, formulários, botões, `hr`, breadcrumbs. Fonte do sistema de design
   carregada (nada de Times New Roman).
4. **Nada de seção vazia.** Título sem conteúdo ("Últimos posts" sem posts) não aparece, ou mostra um estado vazio
   útil ("Nenhum post ainda. Publique o primeiro"), ou usa conteúdo de exemplo marcado `<!-- PROVISÓRIO -->`.
5. **Tudo dentro do grid.** Nenhum elemento colado na borda da tela enquanto o resto está centralizado
   (breadcrumb, avisos, rodapé usam o mesmo container).
6. **Entrega cedo.** Em até 1 rodada/1 hora a HOME tem que estar pronta e bonita (com prints). Documentação e
   infraestrutura vêm depois, nunca antes da primeira tela.

## Etapas

### 1. Inventário (curto: 15 minutos, não um relatório)
- Descubra a stack (PHP puro, WordPress, Laravel, gerador estático, HTML) e como as páginas são montadas
  (templates, includes, banco). Ache de onde vem cada conteúdo.
- Liste em `docs/site/INVENTARIO.md`: páginas e URLs, menu, textos principais, imagens/logo, formulários,
  integrações (WhatsApp, pagamentos, analytics), SEO (title/description por página). Se houver site antigo no ar ou
  pasta antiga, rode `jarvis-site print` nele para ter o "antes".
- Assunto, público e a ação principal do site (comprar, chamar no WhatsApp, assinar, ler). Se não estiver escrito,
  deduza do conteúdo e registre como premissa.

### 2. Direção visual e sistema de design
- Siga a skill `frontend-design`: plano curto (cores 4–6 hex nomeados, tipografia, layout com wireframe ASCII,
  princípios), revise contra o assunto para não sair genérico, só então escreva código.
- Mantenha a identidade existente (logo, cor da marca) a menos que o pedido seja mudar.
- Grave em `docs/site/DESIGN.md` e implemente como `css/tokens.css` (variáveis: cores, fontes, escala tipográfica,
  espaçamentos 4/8/12/16/24/32/48/64/96, raios, sombras, larguras de container) + `css/base.css` (reset, elementos
  padrão estilizados: a, p, h1–h6, ul, ol, table, form, input, button, hr, img, blockquote, code).
- Componentes reutilizáveis (um arquivo/partial cada): cabeçalho com menu (e menu de celular), hero, card,
  lista de posts, breadcrumb, botão, formulário, estado vazio, rodapé. Sem framework pesado; CSS próprio.
- No piloto: decida a direção sozinho e registre [piloto]. Fora do piloto, se o usuário não deu referência, mostre
  2 direções com prints da home (`/jarvis:redesenhar`) e siga a escolhida.

### 3. Home primeiro, completa
Home terminada de verdade: hero com a mensagem principal, seções com conteúdo real (ou provisório marcado),
chamada para a ação, rodapé. Rode `jarvis-site testar`, `jarvis-site print`, olhe os prints, dê a nota visual
(abaixo) e só passe adiante com nota ≥ 8. Commit.

### 4. Página por página
Uma página (ou template) por vez, reaproveitando os componentes: listagem/posts, página interna, tags/categorias,
contato, sobre, 404. Para cada uma: implementar → testar → print → nota → commit. Acrescente a jornada da página em
`.jarvis/jornadas.json` (abre, não está em branco, título visível, link do menu).

### 5. Acabamento
Estados vazios, 404 bonita, favicon, title/description por página, Open Graph, imagens otimizadas (WebP, tamanhos),
foco visível, contraste AA, `prefers-reduced-motion`, sem erros no console, nota do `jarvis-site testar` ≥ 85.

## Nota visual (dê em cada print, desktop e celular; mínimo 8 em cada item)
| Item | 10 é |
|---|---|
| Hierarquia | dá para entender a página em 3 segundos; título, subtítulo e ação principal óbvios |
| Ritmo e espaçamento | espaços da escala, seções respiram, nada apertado nem solto demais |
| Tipografia | fontes escolhidas de propósito, escala clara, linhas < 80 caracteres, leitura confortável |
| Cor e contraste | paleta coerente com a marca, contraste AA, destaque usado com moderação |
| Acabamento | nada com cara de navegador padrão, nada de HTML cru, nada desalinhado ou colado na borda |
| Conteúdo | nenhuma seção vazia, textos reais ou provisórios bons, imagens no lugar |
| Celular | menu funciona, nada vaza da tela, toques ≥ 44px, texto ≥ 16px |
| Identidade | parece feito para ESTE site, não um modelo genérico |

Escreva a nota em `docs/PILOTO.md` (ou na resposta): `Nota visual home: 8,6 (hierarquia 9, …)`. Abaixo de 8 em
qualquer item: corrija e tire o print de novo antes de seguir.

## O que mostrar ao usuário
Prints da home e das páginas prontas, o link da prévia ao vivo e, no fim, `docs/HOMOLOGACAO.md` com o roteiro.
Nada de pedir aprovação de documentação: o usuário quer ver tela.
