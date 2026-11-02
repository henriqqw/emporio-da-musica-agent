# Pedido de devolução fora do prazo

**O que mostra:** Aplicação da política de trocas com prazos calculados pelo código: arrependimento e troca por defeito já vencidos, garantia legal ainda vigente.

**Cenários de aceite (spec §10):** A10, A9  
**Cliente simulado:** (67) 99789-0123 (Letícia)
  
**Modelo:** `gemini-flash-lite-latest` · **Data de referência:** quarta-feira, 25/03/2026 14:30

> Transcrição gerada por `scripts/run_scenarios.py` a partir de uma execução real.
> As respostas usam a formatação do WhatsApp (*negrito*, _itálico_).

---

**Cliente:** Me arrependi da minha compra, posso devolver meu pedido?

**Assistente:**

> Olá, Letícia! Para eu conferir se a devolução está dentro do prazo e quais regras se aplicam, você poderia me informar o e-mail cadastrado na compra?

**Cliente:** leticia@gmail.com

> 🔧 ferramentas: `get_order`

**Assistente:**

> Letícia, não encontrei um cadastro com este número e esse e-mail. Você poderia conferir se o e-mail está correto ou falar diretamente com a nossa equipe pelo WhatsApp no (67) 3321-4500?

**Cliente:** Ah, errei. É leticia.rocha@jmail.com

> 🔧 ferramentas: `get_order`

**Assistente:**

> Letícia, verifiquei o seu pedido (número 7), que foi entregue em 17/02/2026.
> 
> Como o prazo para devolução por arrependimento em compras online é de até 7 dias corridos após o recebimento (neste caso, encerrado em 24/02/2026), não é mais possível fazer a devolução por arrependimento.
> 
> Mas fique tranquila, a garantia legal contra defeitos de fabricação vale até 18/05/2026. Se houver algum problema com o instrumento, me avise por aqui!

**Cliente:** E se o ukulele apresentar defeito?

> 🔧 ferramentas: `get_order`

**Assistente:**

> Para trocas por defeito de fabricação, o prazo direto com a loja era de até 30 dias após a compra (até 05/03/2026). Como já passou dessa data, você ainda está coberta pela garantia legal contra defeitos de fabricação até 18/05/2026, e o acionamento é feito diretamente com o fabricante.
> 
> Se precisar, nós da Empório da Música podemos intermediar esse processo para você mediante solicitação. Quer que eu registre uma solicitação para nossa equipe te ajudar com isso?
