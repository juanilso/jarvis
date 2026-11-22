# Créditos

## gstack (https://github.com/garrytan/gstack), licença MIT
Ideias adaptadas e reescritas em português, em versão enxuta, sem copiar código nem executar nada do gstack:
- `agents/revisor.md`: checklist de produção (do /review)
- `agents/designer.md`: revisão de design e detecção de "cara de IA" (do /design-review)
- `commands/qa.md`: fluxo de QA no navegador (do /qa)
- `commands/novo.md`: desafio das premissas e abordagens (do /office-hours)

Copyright (c) 2026 Garry Tan

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of
the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## skill-scanner (https://github.com/getsentry/skills), licença Apache 2.0
Ver `skills/skill-scanner/LICENSE` e `skills/skill-scanner/NOTICE.md`.

## unslop (https://github.com/heydamir/unslop), por Damir Sokolovsky, licença CC BY 4.0
Instalado como plugin pelo `jarvis-extras` (não copiado para o Jarvis). Usado pelo agente designer.

## Floorplan (https://github.com/haydenschmitty/floorplan), por Hayden Smith, licença MIT
Instalado como plugin pelo `jarvis-extras` (não copiado para o Jarvis). Usado por `/jarvis:mapa` e `/jarvis:adotar`.

## Hermes Agent (https://github.com/NousResearch/hermes-agent), por Nous Research, licença MIT
Usado como serviço separado a partir da imagem oficial `nousresearch/hermes-agent`. Nenhum código do Hermes
foi copiado para o Jarvis; o Jarvis só conversa com a API dele (formato OpenAI) pelo `jarvis-hermes`.

## n8n (https://github.com/n8n-io/n8n), licença Sustainable Use License (fair-code)
Usado como serviço separado a partir da imagem oficial, para uso interno do próprio usuário. Nenhum código do n8n foi
copiado; o Jarvis traz só fluxos de exemplo (JSON) que chamam o gatilho do Jarvis.

## last30days (https://github.com/mvanhorn/last30days-skill), por Matt Van Horn, licença MIT
O motor (pasta `skills/last30days/scripts`, commit bb2f1ed) é baixado na construção da imagem para `/opt/last30days`, junto com o
arquivo LICENSE original. O Jarvis só o executa pelo `jarvis-tendencias`, num ambiente isolado; nenhum arquivo foi modificado.

## frontend-design (https://github.com/anthropics/skills), por Anthropic, licença Apache 2.0
Copiada sem alterações em `skills/frontend-design` (commit e4bb5d9), com o texto da licença em `LICENSE.txt` e a origem em
`ORIGEM.md`. Revisada: só instruções, sem scripts nem downloads.

## WAHA Core (https://github.com/devlikeapro/waha), por devlikeapro, licença Apache 2.0
Usado como serviço separado a partir da imagem oficial `devlikeapro/waha`; nenhum código copiado. O Jarvis só chama a API REST.
