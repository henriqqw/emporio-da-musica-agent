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
> Para eu conferir como está o seu pedido por aqui, por favor, me informa o seu e-mail cadastrado?

**Cliente:** anacarol.ferreira@coldmail.com

> 🔧 ferramentas: `get_order`

**Assistente:**

> Ana, o pedido número 8, com o ukulelê Kala KA-C Concert Mogno, foi enviado no dia 15/02/2026. O código de rastreamento é o BRJL5544332BR.
> 
> O prazo estimado de entrega era para o dia 28/02/2026, então ele está com atraso e peço sinceras desculpas por isso.
> 
> Posso registrar uma reclamação para a nossa equipe verificar o que aconteceu com a entrega?

**Cliente:** Que absurdo, era pra ter chegado em fevereiro!

**Assistente:**

> Entendo perfeitamente a sua frustração, Ana. É realmente inaceitável esse atraso, e peço desculpas mais uma vez pelo transtorno.
> 
> Posso registrar uma reclamação formal para que nossa equipe investigue o que aconteceu com a entrega junto à transportadora?

**Cliente:** Sim, pode registrar.

> 🔧 ferramentas: `register_complaint`

**Assistente:**

> Prontinho, Ana. Registrei a sua reclamação sob o protocolo *REC-20260325-0001*. Nossa equipe vai verificar o que houve com a transportadora e entraremos em contato com você até o dia *26/03/2026 às 14:30*.
> 
> Fico à disposição se precisar de algo mais por enquanto!
