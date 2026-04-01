---
name: infograficos-terapia
description: Cria infograficos e visuais para terapeutas alquimicos. Inclui gauges de elementos, graficos de progresso, mapas de substancias, diagramas de DNA alquimico e cards de diagnostico. Otimizado para o portal web e materiais educativos.
allowed-tools: Read Write Edit Bash
---

# Infograficos para Terapia Alquimica

## Descricao

Cria visualizacoes profissionais para o portal do terapeuta e materiais educativos. Foco em representar dados alquimicos de forma clara e intuitiva.

## Quando Usar

- Criar visuais dos 4 elementos para um paciente
- Gerar grafico de progresso ao longo das consultas
- Criar mapa visual das substancias (Enxofre, Sal, Mercurio)
- Gerar diagrama de DNA alquimico (Serpentes Pai/Mae)
- Criar material educativo sobre conceitos da escola
- Gerar cards visuais para posts em redes sociais

## Tipos de Visuais

### 1. Dashboard de Elementos

Gauges circulares ou barras coloridas mostrando:
- Terra (marrom/verde): 0-100%
- Ar (azul claro): 0-100%
- Fogo (vermelho/laranja): 0-100%
- Agua (azul escuro): 0-100%

Cores de status:
- Verde: equilibrio (25-50%)
- Amarelo: atencao (15-25% ou 50-70%)
- Vermelho: critico (<15% ou >70%)

### 2. Grafico de Progresso

Timeline mostrando evolucao dos elementos ao longo de consultas:
- Eixo X: datas das consultas
- Eixo Y: percentual de cada elemento
- Linhas coloridas por elemento
- Zona verde de equilibrio destacada
- Alertas de surto marcados

### 3. Mapa de Substancias

Triangulo alquimico mostrando:
- Enxofre (base esquerda): Terra + Fogo
- Sal (centro): substancia ponte
- Mercurio (base direita): Ar + Agua
- Paciente posicionado no triangulo conforme dominancia

### 4. Diagrama DNA Alquimico

Duas colunas:
- Serpente do Pai (esquerda): setenios, influencias, status
- Serpente da Mae (direita): setenios, influencias, status
- Centro: paciente com setenio atual destacado
- Cores indicando comprometimento

### 5. Card de Diagnostico

Card resumo para rapida visualizacao:
- Nome do paciente (codigo)
- Data da consulta
- Elemento dominante e carente
- Substancia predominante
- Nivel do floral
- Status (Nigredo/Albedo/Rubedo)
- Progresso (seta para cima/baixo/lateral)

### 6. Material Educativo

Infograficos para redes sociais:
- Explicacao dos 4 elementos (formato carrossel Instagram)
- Como funciona o DNA alquimico
- O que sao as 3 substancias
- Niveis de florais explicados
- Formato 1080x1080 ou 1080x1350

## Paleta de Cores

### Elementos
- Terra: #8B6914 (marrom dourado), #4A7C59 (verde terra)
- Ar: #38BDF8 (azul celeste), #BAE6FD (azul claro)
- Fogo: #EF4444 (vermelho), #F97316 (laranja)
- Agua: #3B82F6 (azul), #1E40AF (azul profundo)

### Substancias
- Enxofre: #F59E0B (amarelo dourado)
- Sal: #9CA3AF (cinza prata)
- Mercurio: #8B5CF6 (violeta)

### Status
- Equilibrio: #10B981 (verde)
- Atencao: #F59E0B (amarelo)
- Critico: #EF4444 (vermelho)
- Progresso: #3B82F6 (azul)

### Marca
- Primaria: #6D28D9 (roxo brand)
- Secundaria: #0D9488 (teal)
- Destaque: #D4AF37 (dourado)

## Tecnologias

- **Portal**: HTML/CSS/JS inline (Alpine.js + Tailwind)
- **Graficos**: Chart.js ou barras CSS puras
- **Imagens**: Matplotlib/PIL para PNG
- **PDF**: HTML to PDF via browser print

## Acessibilidade

- Sempre usar cores com contraste suficiente
- Incluir texto alternativo nos gauges (nao depender so da cor)
- Labels claros em todos os graficos
- Fonte minima 12px no portal, 14px em materiais impressos

## Integracao

- **diagnostico-alquimico**: Fonte dos dados para visualizar
- **relatorio-clinico**: Visuais incluidos nos relatorios
- **plano-tratamento**: Graficos de progresso do plano
