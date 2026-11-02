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

> Oi, Ana Carolina! Para eu consultar o andamento do seu pedido, você poderia me informar o seu e-mail cadastrado?

**Cliente:** anacarol.ferreira@coldmail.com

> 🔧 ferramentas: `get_order`

**Assistente:**

> Ana Carolina, o seu pedido número 8, que inclui o Kala KA-C Concert Mogno, foi despachado no dia 15/02/2026, mas infelizmente ele acabou atrasando em relação à previsão de entrega que era para o dia 28/02/2026. O código de rastreio dele é o _BRJL5544332BR_, e você pode acompanhar por ele.
> 
> Peço desculpas por esse atraso! Se quiser, posso registrar uma reclamação agora mesmo para a nossa equipe verificar o que aconteceu com a entrega. Posso abrir?

**Cliente:** Que absurdo, era pra ter chegado em fevereiro!

**Assistente:**

> Entendo perfeitamente a sua frustração, Ana Carolina, tem toda razão em estar chateada com esse atraso.
> 
> Posso registrar uma reclamação sobre o atraso na entrega do pedido 8 para a nossa equipe verificar o que aconteceu?

**Cliente:** Sim, pode registrar.

> 🔧 ferramentas: `register_complaint`

**Assistente:**

> Prontinho, Ana Carolina! Registrei a reclamação aqui. O seu protocolo é o *REC-20260325-0001*, e a nossa equipe vai verificar o que houve com o seu pedido e retornar até o dia *26/03/2026 às 14:30*.
> 
> Peço mais uma vez desculpas pelo transtorno. Precisa de ajuda com mais alguma coisa por enquanto?
