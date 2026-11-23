# Referência: rede credenciada

Checklist de partida para planejar um sistema de rede credenciada (clínicas, laboratórios, farmácias, academias,
lojas parceiras etc. que atendem os membros de um plano, cartão de benefícios ou associação). Use para fazer as
perguntas certas, não como escopo obrigatório: confirme com o usuário o que se aplica.

## Perfis típicos
- **Administradora** (dono do sistema): cadastra e aprova credenciados, define regras, acompanha relatórios, faz repasses.
- **Credenciado** (parceiro): se cadastra, envia documentos, mantém serviços/preços/horários, valida o membro no
  atendimento, registra o atendimento, acompanha o que tem a receber.
- **Membro / beneficiário** (cliente final): procura credenciados (cidade, especialidade, mapa), vê desconto/cobertura,
  mostra carteirinha digital, agenda (às vezes), avalia.
- **Empresa contratante** (se for B2B): inclui e exclui funcionários, vê uso e fatura.
- **Atendente / suporte**: tira dúvidas, resolve pendências (muitas vezes pelo WhatsApp).

## Processos que quase sempre existem
1. **Credenciamento:** cadastro do parceiro → documentos (CNPJ, alvará, registro no conselho: CRM/CRO/CRF…) →
   análise → aprovação/reprovação → contrato/aceite → ativo. Recredenciamento periódico e descredenciamento.
2. **Catálogo:** serviços/procedimentos, especialidades, preço de tabela x preço da rede (ou % de desconto),
   horários, endereço com geolocalização, fotos.
3. **Busca do membro:** por cidade/bairro, especialidade/serviço, distância, nome; página do credenciado.
4. **Elegibilidade no atendimento:** o credenciado confirma que o membro está ativo (CPF + data de nascimento,
   número da carteirinha, QR code ou token temporário de 6 dígitos com validade curta). Membro inadimplente/cancelado
   = não elegível.
5. **Autorização / guia** (quando o serviço exige): pedido → regra automática ou análise → autorizado/negado → validade.
6. **Registro do atendimento / consumo:** o que foi feito, valor, comprovante; base para repasse e relatório.
7. **Financeiro:** mensalidade do membro (cobrança recorrente: Pix, boleto, cartão), inadimplência e bloqueio;
   repasse ao credenciado ou comissão da administradora; conciliação; notas.
8. **Comunicação:** boas-vindas, carteirinha, lembretes, aviso de vencimento, pesquisa de satisfação (WhatsApp/e-mail).
9. **Avaliações e qualidade:** nota do membro, reclamações, auditoria de credenciados.
10. **Relatórios:** uso por credenciado/cidade/serviço, economia gerada ao membro, receita, inadimplência, ranking.

## Entidades (ponto de partida do DOMINIO.md)
Administradora · Credenciado (PJ/PF) · Unidade/Endereço · Documento · Especialidade · Serviço/Procedimento ·
TabelaDePreço · Plano · Membro · Dependente · EmpresaContratante · Carteirinha · TokenDeElegibilidade · Guia/Autorização ·
Atendimento · Cobrança · Pagamento · Repasse · Avaliação · Usuário/Perfil/Permissão · RegistroDeAuditoria.

Estados que costumam precisar de diagrama: Credenciado (rascunho → em análise → ativo → suspenso → descredenciado),
Membro (ativo → inadimplente → bloqueado → cancelado), Guia (solicitada → autorizada/negada → usada/expirada),
Cobrança (aberta → paga → vencida → cancelada).

## Regras de negócio para perguntar (viram R1, R2…)
- Membro inadimplente há quantos dias perde o acesso? Dependentes herdam o status do titular?
- Carência para algum serviço? Limite de uso por mês?
- Desconto fixo em % ou tabela de preço por credenciado? Quem define?
- O credenciado recebe do membro (só desconto) ou da administradora (repasse)? Em que prazo? Há comissão?
- Token de elegibilidade: validade (ex.: 10 min), uso único?
- Quem aprova credenciamento e guias? Há SLA?

## Integrações frequentes (e o papel do n8n)
- **No sistema (fonte da verdade):** cadastros, regras, elegibilidade, atendimentos, financeiro, permissões.
- **No n8n (orquestração):** avisos no WhatsApp/e-mail (boas-vindas, vencimento, token), rotinas (cobrança do dia,
  inadimplência, relatório semanal), integração com gateway de pagamento (webhook de pago → API do sistema),
  formulários externos, planilhas, alertas para a equipe. O n8n chama a API do sistema; o sistema chama webhooks do n8n.
- Pagamentos (Pix/boleto/cartão recorrente), WhatsApp (WAHA já existe no Jarvis), mapas/geocodificação (endereço →
  coordenadas), assinatura de contrato, e-mail transacional, emissão de nota.

## Riscos e hipóteses típicas para o laboratório
- H: o geocódigo dos endereços funciona bem nas cidades atendidas (taxa de acerto, custo/limite grátis).
- H: o fluxo n8n "webhook de pagamento → liberar membro → avisar no WhatsApp" funciona ponta a ponta com retry.
- H: o token de elegibilidade é simples o bastante para a recepção do credenciado (teste no protótipo pelo celular).
- H: o gateway de pagamento escolhido faz cobrança recorrente + webhook no plano disponível.
- H: a busca por distância responde rápido com o volume esperado de credenciados.

## LGPD (obrigatório no plano)
Dados de saúde são **dados sensíveis**: se o sistema registra procedimentos/consultas, trate como tal. Base legal,
consentimento, mínimo necessário (o credenciado vê só o que precisa para atender), registro de acesso (auditoria),
criptografia em trânsito, backups, prazo de retenção, canal para o titular pedir seus dados. Nunca use dados reais
no protótipo nem nos ajudantes.
