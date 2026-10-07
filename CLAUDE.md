# EscalaPro BCMS — Previsão e Controle de Escalas de Serviço

Sistema local de gestão, cálculo de folgas, controle de permutas e algoritmo de previsão matemática para as escalas de serviço do **Batalhão Central de Manutenção e Suprimento (BCMS — UASG 160329)** / Ba Ap Log Ex.

Foco inicial: **3º Sargento de Dia** (expandível para Comandante da Guarda, Adjunto ao Oficial de Dia e Oficial de Dia).

---

## 📌 Princípios Inegociáveis e Doutrina Militar

1. **Separação Estrita de Filas (Preta × Vermelha):**
   - **Escala Preta:** Dias úteis de expediente normal (segunda a sexta-feira, exceto feriados).
   - **Escala Vermelha:** Sábados, domingos e feriados reconhecidos (nacionais e militares).
   - As duas filas rodam de forma concorrente e totalmente independente. Ter tirado serviço na vermelha não anula nem avança a fila preta, e vice-versa.

2. **Regra de Ouro das Trocas a Caneta (Permutas Operacionais):**
   - *"O pessoal riscado a caneta, geralmente é troca de serviço e não conta na folga do militar em caneta, apenas o que está impresso."*
   - O militar impresso oficial é quem "paga" o serviço no histórico de folgas: sua folga é zerada e recomeça a contar no dia impresso.
   - O militar substituto a caneta assume a execução física no dia e adquire um crédito de permuta (+1 serviço), mas **sua folga na fila da escala não é afetada nem resetada**.

3. **Trava de Interstício Mínimo (Descanso de 48h):**
   - Nenhum militar pode ser escalado se tiver cumprido serviço nas 48 horas anteriores (seja preta ou vermelha), garantindo a higidez física e o descanso regulamentar (RISG).

4. **Calendário e Feriados:**
   - Feriados em dias úteis (como 12 de Outubro - Padroeira do Brasil) são automaticamente tratados e sombreados como **Escala Vermelha**.

5. **Anti-alucinação e Integridade dos Dados:**
   - Nunca inventar militar ou escala; o histórico baseia-se 100% nas fotografias físicas das semanas 37 a 42 de 2026.

---

## 🛠️ Comandos de Execução e Testes

```bat
iniciar.bat                 :: Inicia o servidor local na porta 8770 e abre o navegador
py -3 -m pytest tests -v    :: Executa a suíte completa de testes automatizados
```

Python sempre com `py -3`, caminhos com `pathlib.Path`, UTF-8 explícito.
