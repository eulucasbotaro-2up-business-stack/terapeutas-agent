---
name: visual-explainer
description: Transforma dados e conceitos em paginas HTML interativas e auto-contidas. Gera diagramas, fluxogramas, dashboards e relatorios visuais. Nao depende de servicos externos — tudo inline. Util para gerar relatorios de diagnostico, dashboards de pacientes e materiais visuais para o portal.
allowed-tools: Read Write Edit Bash
---

# Visual Explainer

## Descricao

Gera paginas HTML auto-contidas (single-file) que explicam visualmente dados, processos e conceitos. Cada pagina e standalone — nao precisa de servidor, CDN ou dependencias externas. Ideal para gerar relatorios visuais de diagnostico, dashboards de pacientes e materiais educativos.

Baseado no projeto visual-explainer (nicobailon/visual-explainer) adaptado para o contexto de terapia alquimica.

## Quando Usar

- Gerar relatorio visual de diagnostico para o terapeuta
- Criar dashboard de progresso de um paciente
- Visualizar cruzamento de dados (elementos vs mapa astral)
- Criar material educativo interativo
- Gerar apresentacao visual de um caso clinico
- Criar diagrama de fluxo de tratamento

## Workflow: Think > Structure > Style > Deliver

### 1. Think (Pensar)
- Qual e o objetivo do visual?
- Quem vai ver? (terapeuta, paciente, ambos?)
- Quais dados sao essenciais?
- Qual o melhor tipo de visualizacao?

### 2. Structure (Estruturar)
- Organizar dados em hierarquia visual
- Definir secoes e fluxo de leitura
- Escolher tipo de grafico/diagrama adequado
- Manter simplicidade — menos e mais

### 3. Style (Estilizar)
- Usar paleta da marca (roxo brand + teal + dourado)
- Tipografia: Inter para corpo, Poppins para titulos
- Evitar excesso visual — profissional e limpo
- Responsivo para mobile e desktop

### 4. Deliver (Entregar)
- Salvar como arquivo HTML unico
- Testar em navegador antes de entregar
- Garantir que funciona offline (sem CDN)
- Nomear arquivo de forma descritiva

## Tipos de Visuais

### Dashboard de Paciente
- Gauges dos 4 elementos
- Cards de substancias
- Timeline de consultas
- Indicador de progresso
- Alertas visuais

### Relatorio de Diagnostico
- Resumo executivo no topo
- Detalhamento por camada
- Graficos de barras para elementos
- Triangulo de substancias
- Setenio visual

### Fluxograma de Tratamento
- Steps numerados
- Decisoes (if/else visual)
- Protocolos por fase
- Timeline com marcos

### Mapa Conceitual
- Conceitos da escola conectados
- Relacoes entre elementos, substancias, DNA
- Hierarquia visual clara

## Regras de Design

### FAZER
- Cores consistentes com a marca
- Contraste adequado (WCAG AA minimo)
- Hierarquia visual clara (titulos > subtitulos > corpo)
- Espaco em branco generoso
- Dados reais, nunca placeholder

### NAO FAZER
- Gradientes excessivos
- Sombras pesadas
- Animacoes desnecessarias
- Fontes decorativas
- Cores neon ou muito saturadas
- Mais de 4-5 cores por visual

## Template HTML Base

```html
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>[Titulo do Relatorio]</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', system-ui, sans-serif; background: #FAFAF9; color: #1a1a1a; }
        .container { max-width: 900px; margin: 0 auto; padding: 2rem; }
        .card { background: white; border-radius: 16px; padding: 1.5rem; margin-bottom: 1rem; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
        .gauge { height: 8px; border-radius: 4px; background: #e5e7eb; overflow: hidden; }
        .gauge-fill { height: 100%; border-radius: 4px; transition: width 0.5s ease; }
        .badge { display: inline-block; padding: 2px 8px; border-radius: 9999px; font-size: 0.75rem; font-weight: 600; }
        h1 { font-size: 1.5rem; font-weight: 700; color: #6D28D9; margin-bottom: 0.5rem; }
        h2 { font-size: 1.1rem; font-weight: 600; color: #374151; margin-bottom: 0.75rem; }
    </style>
</head>
<body>
    <div class="container">
        <!-- Conteudo aqui -->
    </div>
</body>
</html>
```

## Localizacao dos Arquivos

Salvar visuais gerados em: `portal-vercel/reports/` ou diretorio temporario.

## Integracao

- **diagnostico-alquimico**: Dados de diagnostico para visualizar
- **infograficos-terapia**: Paleta de cores e componentes visuais
- **relatorio-clinico**: Relatorios formatados em HTML
