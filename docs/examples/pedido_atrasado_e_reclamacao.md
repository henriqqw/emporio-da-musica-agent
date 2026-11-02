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
> Para que eu possa conferir como está a entrega e te passar os detalhes do seu pedido, você poderia me informar o seu e-mail cadastrado?

**Cliente:** anacarol.ferreira@coldmail.com

> 🔧 ferramentas: `get_order`

**Assistente:**

> Ana, vi aqui que o seu pedido número 8, feito em 15/02/2026 com o ukulele Kala KA-C Concert Mogno, foi enviado com a transportadora, mas infelizmente ele está com um atraso na entrega (a previsão era até 28/02/2026). O código de rastreio é o BRJL5544332BR.
> 
> Peço desculpas por esse transtorno com o prazo! Quer que eu registre uma reclamação para a nossa equipe verificar o que aconteceu com a entrega?

**Cliente:** Que absurdo, era pra ter chegado em fevereiro!

**Assistente:**

> Imagino a sua frustração, Ana. Tem toda razão em estar chateada com esse atraso, peço sinceras desculpas por isso.
> 
> Posso registrar uma reclamação para a nossa equipe verificar com urgência o que aconteceu com a transportadora e te dar um retorno?

**Cliente:** Sim, pode registrar.

> 🔧 ferramentas: `register_complaint`

**Assistente:**

> Prontinho, Ana. Registrei a reclamação sob o protocolo *REC-20260325-0001*.
> 
> Nossa equipe vai verificar o que houve com a transportadora e entraremos em contato com você até o dia 26/03/2026 às 14:30.
> 
> Se precisar de mais alguma coisa enquanto isso, é só me chamar!
