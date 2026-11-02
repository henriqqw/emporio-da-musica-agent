# Pedido atrasado e registro de reclamação

**O que mostra:** Identificação por telefone + e-mail antes de mostrar o pedido, atraso detectado pelo código, e reclamação registrada só após confirmação, com protocolo e prazo.

**Cenários de aceite (spec §10):** A8, A16  
**Cliente simulado:** (67) 99654-7821 (Ana Carolina)
  
**Modelo:** `gemini-flash-lite-latest` · **Data de referência:** quarta-feira, 25/03/2026 14:30

> Transcrição gerada por `scripts/run_scenarios.py` a partir de uma execução real.
> As respostas usam a formatação do WhatsApp (*negrito*, _itálico_).

---

**Cliente:** Oi, cadê meu pedido?

**Assistente:**

> Oi, Ana Carolina! Tudo bem?
> 
> Para que eu possa verificar o status e o rastreio do seu pedido, você poderia me informar o seu e-mail cadastrado?

**Cliente:** anacarol.ferreira@coldmail.com

> 🔧 ferramentas: `get_order`

**Assistente:**

> Ana Carolina, o pedido número 8, realizado em 15/02/2026, foi enviado, mas infelizmente consta como atrasado, já que a previsão de entrega era para 28/02/2026. O código de rastreio dele é BRJL5544332BR.
> 
> Peço desculpas por esse transtorno. Quer que eu registre uma reclamação para a nossa equipe verificar o que aconteceu com a entrega?

**Cliente:** Que absurdo, era pra ter chegado em fevereiro!

**Assistente:**

> Compreendo perfeitamente a sua frustração com esse atraso, Ana Carolina. Vou registrar uma reclamação para a nossa equipe verificar o que aconteceu com a entrega do seu pedido número 8.
> 
> Ficou assim o resumo da reclamação: "Atraso na entrega do pedido número 8, com previsão original para 28/02/2026."
> 
> Posso registrar para que nossa equipe dê prioridade nisso?

**Cliente:** Sim, pode registrar.

> 🔧 ferramentas: `register_complaint`

**Assistente:**

> Reclamação registrada com sucesso, Ana Carolina! O seu protocolo é o *REC-20260325-0001* e a nossa equipe vai retornar com uma resposta até o dia 26/03/2026 às 14:30.
> 
> Se precisar de mais alguma coisa enquanto isso, é só me chamar!
