---
description: Analisa um site pela URL e cria 3 variações modernas na mesma linha, com prévia, para você escolher e refinar
argument-hint: '<url> [o que você quer diferente: cores, estilo, seções, público...]'
---

Pedido: $ARGUMENTS

Carregue a skill `orquestrador`, a skill `refatorar-site` e a skill `frontend-design` (as duas vêm com o Jarvis).

Regras:
- Use o navegador (ferramentas `mcp__…playwright…`). NUNCA use `browser_run_code_unsafe`.
- Trabalhe só com o site informado. Não copie textos de terceiros nem marcas que não sejam do cliente: mantenha o
  conteúdo do próprio site e use placeholders onde faltar. Imagens: reutilize as do site do cliente ou use blocos neutros.

1. **Análise** (`designer`, modelo do perfil):
   - Abra a URL, tire prints em 1440x900 (desktop) e 390x844 (celular) e salve em `redesign/referencia/`.
   - Leia a página: estrutura das seções, menu, textos principais, CTAs, formulários, rodapé.
   - Extraia a identidade: cores (hex), fontes, tom de voz, logo, estilo de imagens.
   - Registre tudo em `redesign/ANALISE.md` (máx. 40 linhas) com os problemas encontrados
     (hierarquia, contraste, responsividade, velocidade, acessibilidade, conversão).
2. **3 variações** (`designer`), cada uma em `redesign/variante-a|b|c/index.html` (HTML + CSS próprios, sem build,
   responsivo, acessível, imagens leves). Todas mantêm a essência do site e aplicam o pedido do usuário:
   - A: evolução segura (mesma estrutura, visual moderno e limpo);
   - B: moderna e ousada (tipografia forte, layout mais editorial);
   - C: focada em conversão (CTA claro, prova social, formulário em destaque).
3. **Verificação visual**: `jarvis-site print redesign/variante-X` (prints desktop e celular) e olhe os PNGs com Read, corrija o que estiver
   quebrado (sobreposição, texto cortado, contraste) e salve os prints em `redesign/variante-X/prints/`.
4. Crie `redesign/index.html` com links para as 3 variantes lado a lado (para a prévia do painel).
5. Registre um resumo em `/workspace/.jarvis-conhecimento/projetos/<projeto>.md` (seção Redesign) se a base existir.

Resposta final (máx. 15 linhas): o que mudou em cada variante (2 linhas cada), principais problemas do site atual e
a instrução: "Abra a prévia (👁 no painel) e diga qual variante seguir e o que ajustar".
