# 🛍️ Simulação de Compra com Agentes de IA Generativa em Ambiente 3D Capstone Insper 2025.1 - NTT DATA

Este projeto faz parte do **Capstone (PFE) do curso de Engenharia da Computação do Insper**, desenvolvido em parceria com a **NTT DATA**. O objetivo é explorar o uso de **agentes de Inteligência Artificial Generativa** em um ambiente de **computação espacial**, permitindo que tomem decisões autônomas e interajam com um espaço virtual tridimensional.  

A simulação ocorre dentro de um **shopping center virtual**, onde agentes de IA conduzem **toda a jornada de compra do usuário**, desde a busca pelo produto até a tomada de decisão final, utilizando **modelos de linguagem natural (LLMs)** para gerar interações realistas e dinâmicas.  

---

## 📌 Visão Geral  

A experiência ocorre em um **shopping center virtual**, onde os agentes de IA assumem papéis distintos e interagem autonomamente. O **usuário apenas informa o que deseja comprar**, e os agentes assumem o controle da interação, conduzindo todo o processo de atendimento e negociação.  

### **Fluxo da Experiência**  

1. **Balcão de Informações** – O **agente Buyer (comprador)** inicia a conversa com um **agente atendente**, perguntando onde encontrar o produto desejado.  
2. **Direcionamento** – O atendente consulta as lojas disponíveis e indica para qual delas o Buyer deve se dirigir.  
3. **Interação com o Vendedor** – O Buyer entra na loja e interage com um **agente vendedor**, que possui acesso a um **banco de dados de estoque** e fornece informações sobre o produto.  
4. **Processo de Compra** – O Buyer avalia as opções, faz perguntas sobre preços, tamanhos e variações do produto e negocia detalhes.  
5. **Tomada de Decisão** – O Buyer decide se realizará a compra ou não, encerrando a conversa naturalmente.  

Toda a comunicação ocorre de forma **autônoma entre os agentes**, sem necessidade de interação contínua do usuário após a definição do pedido inicial.

---

## 🎮 Integração com Unity  

A experiência acontece dentro de um **ambiente 3D desenvolvido em Unity**, reforçando o conceito de **computação espacial**. Isso significa que os agentes precisam **se localizar no ambiente**, **interpretar direções** e **interagir com elementos tridimensionais**, tornando a experiência mais imersiva.  

A movimentação do **agente Buyer** pelo shopping ocorre conforme as instruções do atendente, garantindo um fluxo lógico na simulação.

---

## 🧠 Arquitetura de Agentes  

O sistema conta com **múltiplos agentes de IA**, cada um com um papel bem definido:  

- **Buyer (Comprador):** Representa o usuário na simulação. Ele inicia a interação, segue as instruções do atendente e conversa com os vendedores para buscar o produto desejado.  
- **Atendente do Shopping:** Um agente que recebe o Buyer no balcão de informações e o direciona para a loja mais adequada.  
- **Vendedor:** Um agente específico de cada loja, com acesso ao **banco de dados de estoque**, responsável por fornecer recomendações e responder às dúvidas do Buyer.  
- **Controlador de Fluxo:** Um agente adicional que monitora a conversa e decide quando a interação deve ser finalizada, garantindo que os diálogos tenham um desfecho natural.  

A comunicação entre os agentes ocorre via **modelos de linguagem natural**, permitindo um diálogo contínuo e adaptável. A **memória conversacional** garante a coerência da interação ao longo do tempo.

---

## 🔧 Ferramentas Utilizadas  

Para a construção e gerenciamento dos agentes, utilizamos as seguintes tecnologias:  

- **LangChain** – Framework para criação e orquestração de agentes baseados em modelos de linguagem natural. Ele permite a personalização do comportamento dos agentes e a estruturação da conversa entre eles.  
- **OpenAI GPT** – Modelo de linguagem usado para gerar diálogos realistas e coerentes entre os agentes.  
- **Text-to-Speech (TTS) da OpenAI** – Implementação de síntese de voz para que os agentes possam falar suas respostas em tempo real, aumentando a imersão da experiência.  
- **Unity 3D** – Motor gráfico utilizado para criar o ambiente tridimensional e permitir a movimentação dos agentes dentro do shopping virtual.  
- **Banco de Dados de Estoque** – Um repositório que armazena informações sobre os produtos disponíveis em cada loja, permitindo que os vendedores ofereçam opções reais ao Buyer.
- **Banco de Dados na AWS** – O sistema utiliza uma base de dados hospedada na AWS para armazenar as informações de estoque de cada loja, permitindo que os agentes vendedores consultem os produtos disponíveis em tempo real.

---

## 🏬 Base de Dados e Personalização  

O **agente vendedor** possui acesso a uma **base de dados de estoque**, que permite:  

- Identificar a disponibilidade do produto solicitado.  
- Sugerir alternativas caso o item desejado esteja indisponível.  
- Personalizar a experiência de compra conforme as preferências do Buyer.  

Além disso, o sistema pode ser expandido para incluir **perfis de usuário pré-definidos**, permitindo experiências ainda mais personalizadas com base no histórico de compras e preferências.

---

## 🎯 Objetivo  

Este projeto busca demonstrar como **agentes de IA generativa** podem **tomar decisões autônomas e interagir em ambientes tridimensionais**, simulando um cenário de atendimento real.  

A aplicação desse conceito pode ser expandida para diversos setores, como:  

✅ **Varejo inteligente** – Assistentes virtuais em lojas físicas e online.  
✅ **Turismo e hospitalidade** – Atendimento automatizado em hotéis e aeroportos.  
✅ **Simulações empresariais** – Treinamento de atendimento ao cliente baseado em IA.  
