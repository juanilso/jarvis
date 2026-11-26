---
name: criar-pagina
description: Método do Jarvis para criar UMA página web do zero com cara profissional e pronta para converter - landing page, página de vendas, captura de contatos, institucional, serviço, evento, link da bio, obrigado/404. Briefing curto, estrutura por tipo de página, texto persuasivo, formulário/WhatsApp funcionando em PHP (cPanel), SEO, LGPD, desempenho e testes com prints. Use em pedidos como "cria uma página", "faz uma landing", "página de vendas/captura", "página para o produto X".
---

# Criar uma página web

Objetivo: em **uma rodada** entregar a página pronta, bonita, rápida e funcionando (formulário ou botão de WhatsApp
de verdade), com prints e o link da prévia ao vivo. Para um site inteiro ou refatoração, use a skill
`refatorar-site`; esta é para uma página (ou uma página nova dentro de um site existente).

Carregue também a skill `frontend-design` (direção visual) e use a **nota visual** da skill `refatorar-site`.

## 1. Briefing (no máximo 5 perguntas, ou deduza)
Se o pedido não diz, pergunte de uma vez só e sugira a resposta provável em cada uma:
1. **Objetivo**: qual é a UMA ação que o visitante deve fazer? (chamar no WhatsApp, comprar, deixar contato, agendar…)
2. **Público e oferta**: para quem é e o que se oferece (produto/serviço, preço ou "sob consulta", diferencial).
3. **Provas**: depoimentos reais, números reais, clientes, garantias, certificações. Sem provas reais, a seção não
   entra; NUNCA invente depoimento, nota, número de clientes ou logos de empresas.
4. **Identidade**: logo, cores, fontes, fotos. Sem nada: crie uma direção própria (frontend-design).
5. **Onde vai ficar**: pasta do site existente (cPanel/PHP, WordPress) ou página nova solta; domínio/URL.
No piloto ou se o usuário pedir "faz aí": deduza, registre as premissas no topo de `docs/site/PAGINA-<nome>.md`
e siga. Dado que falta vira marcador visível `[PREÇO]`, `[TELEFONE]` e comentário `<!-- PROVISÓRIO -->`.

## 2. Estrutura por tipo de página (escolha uma e adapte; não use todas as seções sempre)
| Tipo | Sequência de seções |
|---|---|
| Landing / vendas | hero (promessa + ação) → problema/dor → solução e como funciona (3 passos) → benefícios → provas → oferta/preço → garantia → FAQ (objeções) → chamada final |
| Captura (lead) | hero com formulário curto (nome + WhatsApp/e-mail) acima da dobra → o que a pessoa recebe → prova → formulário de novo |
| Serviço / local | hero com cidade e serviço → serviços em cards → diferenciais → área atendida/horário/mapa → depoimentos reais → contato |
| Institucional / sobre | quem somos → missão/valores curtos → equipe ou história → números reais → contato |
| Evento | nome, data, local e ação → programação → palestrantes → ingressos/inscrição → local/como chegar → FAQ |
| Link da bio | foto/logo + frase → 4 a 8 botões grandes → redes → rodapé mínimo (carrega em < 1 s) |
| Obrigado / 404 | confirmação ou "não achei" + próximo passo útil (voltar, WhatsApp, página principal) |

Regras: **uma ação principal** repetida (hero, meio e fim), mesmo texto do botão; ação secundária discreta.
Botão flutuante de WhatsApp só se o objetivo for conversa.

## 3. Texto que converte
- Título = resultado para o cliente, específico ("Internet que não cai para a sua loja em Niterói"), não slogan vago.
- Subtítulo diz como/para quem; botão com verbo + resultado ("Quero meu orçamento", não "Enviar").
- Frases curtas, voz ativa, "você"; benefícios antes de características; números só se forem reais.
- FAQ responde objeções reais (preço, prazo, contrato, suporte, cancelamento).
- Rascunhos de texto, FAQ e title/description podem ir para o `jarvis-ajudante` (ou `--ia ollama`): mande só o
  briefing público, revise o tom e corte excessos. Nunca prometa o que o cliente não informou.

## 4. Construção
- Direção visual pela `frontend-design` (plano curto → código). Num site existente, use os tokens/componentes dele.
- Estrutura de arquivos (página solta): `index.php` (ou `.html`), `css/estilo.css`, `js/pagina.js` (só se precisar),
  `img/` (WebP), `enviar.php` (formulário), `obrigado.php`. Sem framework pesado; CSS próprio, mobile first.
- HTML semântico: um `h1`, `header/main/section/footer`, `label` em todo campo, `alt` em toda imagem com conteúdo.
- **Formulário em PHP (cPanel)**: validação no servidor, campo isca (honeypot) e tempo mínimo contra robôs,
  limite por IP, sanitização, envio por e-mail (mail()/SMTP configurável em um `config.php` fora do Git) e/ou
  repasse para um webhook do n8n; redireciona para `obrigado.php`. Nunca grave senha, token ou dados de cartão.
- **LGPD**: caixa de consentimento clara no formulário (não marcada), link para política de privacidade
  (crie `privacidade.php` com marcadores para os dados da empresa) e aviso de cookies só se houver rastreamento.
- **WhatsApp**: `https://wa.me/55DDDNUMERO?text=` com mensagem já preenchida e codificada (diz de qual página veio).
- Rastreamento (Meta Pixel, Google Analytics/Tag Manager): só com o ID fornecido pelo usuário; senão, deixe o ponto
  marcado `<!-- ANALYTICS: cole aqui -->`. Nunca invente IDs.

### Skills extras (se instaladas)
Direção visual: landing/página de vendas → `hallmark`; site de empresa → `taste-skill`. Uma só por página.
Antes de entregar: `/impeccable audit` na página e `/seo page <prévia>` (claude-seo); corrija o que for crítico.

### Imagens e banners
Precisa de banner/hero, ilustração ou imagem de produto e o MCP `picsart-gen-ai` está conectado? Gere com ele
(consulte o custo antes), no tamanho certo (hero 1920x800 no PC e versão 1080x1350 para celular), baixe para
`assets/`, converta para WebP e use `<picture>`/`srcset`. Sem Picsart: imagens livres ou SVG/CSS, nunca link quebrado.

## 5. SEO e compartilhamento
`<title>` (≤ 60 caracteres) e `meta description` (≤ 155) próprios; `lang="pt-BR"`; Open Graph e Twitter Card com
imagem 1200×630; favicon; URL limpa; dados estruturados JSON-LD do tipo certo (LocalBusiness, Product, Event, FAQPage)
só com dados reais; `canonical` quando estiver dentro de um site.

## 6. Desempenho e acessibilidade
Imagens WebP com `width/height` e `loading="lazy"` (menos a do hero), fontes com `display=swap` (no máximo 2
famílias), CSS crítico enxuto, sem bibliotecas para efeitos simples, contraste AA, foco visível, alvos de toque ≥ 44 px,
texto ≥ 16 px no celular, `prefers-reduced-motion` respeitado.

## 7. Testar antes de responder (obrigatório)
1. Jornada em `.jarvis/jornadas.json`: a página abre, `h1` visível, botão principal visível e clicável, formulário
   preenche e chega em `obrigado`, link de WhatsApp com o número certo, 404 bonita.
2. `jarvis-site testar` (nota ≥ 85, zero crítico/alto) e `jarvis-site print` — olhe os PNGs de desktop e celular.
3. Nota visual da `refatorar-site` ≥ 8 em cada item. Abaixo disso: corrija e tire os prints de novo.
4. Confira: nada de lorem ipsum, nenhum depoimento/número inventado, marcadores `[ ]` listados para o usuário.

## 8. Entrega
Resposta curta: prints (desktop e celular), link da prévia ao vivo, nota do teste, a lista do que falta o usuário
preencher (`[PREÇO]`, número do WhatsApp, e-mail do formulário, ID do pixel) e como publicar (pasta para subir no
cPanel). Publicar continua sendo decisão do usuário: nunca faça deploy sozinho.
