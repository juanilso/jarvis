# Jarvis: orquestrador global de projetos para Claude Code

Instale uma vez e o Jarvis passa a funcionar em **todos** os projetos. Ele monta um time de agentes,
escolhe o modelo ideal para cada papel (ou deixa você escolher), executa sozinho e só para nas decisões que são suas.

## Instalação (uma vez por computador)
1. Suba esta pasta para um repositório no GitHub (ex.: `seu-usuario/jarvis`).
2. No Claude Code:
   ```
   /plugin marketplace add seu-usuario/jarvis
   /plugin install jarvis@jarvis-marketplace
   ```
   Ou pelo terminal: `claude plugin marketplace add seu-usuario/jarvis` e depois `claude plugin install jarvis@jarvis-marketplace`.
3. Permissões globais (opcional, recomendado): `bash instalar-permissoes.sh`
   O script mescla `settings-recomendado.json` em `~/.claude/settings.json` e faz backup antes.
4. Para atualizar no futuro: dê push no repositório e rode `/plugin marketplace update jarvis-marketplace`.

## Uso
| Comando | O que faz |
|---|---|
| `/jarvis <qualquer pedido>` | Entrada única: entende o pedido e aciona o fluxo certo |
| `/jarvis:novo <ideia>` | Discute o escopo, recomenda o perfil de modelos e gera `docs/` |
| `/jarvis:executar [n\|T-ID\|tudo]` | O time trabalha sozinho com commits locais |
| `/jarvis:decidir [D-001 A \| ok]` | Responde às decisões pendentes em lote |
| `/jarvis:evoluir <mudança>` | Análise de impacto + opções → atualiza o backlog |
| `/jarvis:modelos [perfil]` | Mostra, recomenda ou troca o perfil de modelos |
| `/jarvis:status` | Resumo barato, sem subagentes |

Ao abrir o Claude Code em qualquer pasta, o Jarvis lê o `docs/ESTADO.md` e avisa se há decisões pendentes.

## Perfis de modelos
| Papel | economico | equilibrado (padrão) | maximo |
|---|---|---|---|
| arquiteto | Sonnet | Opus | Opus |
| explorador | Haiku | Haiku | Haiku |
| dev / dba / android | Sonnet | Sonnet | Opus |
| testador | Haiku | Haiku | Sonnet |
| revisor | Haiku | Sonnet | Opus |
| deploy / documentador | Haiku | Haiku | Haiku |

- O Jarvis recomenda um perfil pela criticidade do projeto, e você confirma ou escolhe outro.
- Exceção numa tarefa: coloque `[modelo:opus]` no título.
- Depois de 2 falhas na mesma tarefa, ele sobe um nível de modelo automaticamente.

## Decisões que sempre ficam com você
Escopo ou stack, dependência nova, migration destrutiva, deploy ou push, permissão Android nova,
custo e segurança/LGPD. O time registra a decisão em `docs/DECISOES-PENDENTES.md` e continua nas outras tarefas.

## Estrutura
```
.claude-plugin/  plugin.json, marketplace.json
agents/          arquiteto, explorador, desenvolvedor, dba, android, testador, revisor, deploy, documentador
commands/        jarvis, novo, executar, decidir, evoluir, modelos, status
skills/orquestrador/  SKILL.md (regras) + templates/ (docs do projeto)
hooks/           SessionStart: injeta o estado do projeto
```

## Inspirações
wshobson/agents, BMAD-METHOD e oh-my-claude-code (orquestração multiagente no Claude Code).
O foco do Jarvis é ser enxuto, em português, voltado a PHP/cPanel e Android, e decidir com você só o que importa.
