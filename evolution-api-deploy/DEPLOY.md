# Deploy da Evolution API v2 no Render.com

## Pre-requisitos
- Conta no GitHub
- Conta no Render.com (free tier funciona)

---

## Passo a passo

### 1. Criar repositorio no GitHub

Crie um **novo repositorio** no GitHub (ex: `evolution-api-deploy`).

Suba APENAS os arquivos desta pasta:
```
evolution-api-deploy/
  Dockerfile
  render.yaml
```

Comandos:
```bash
cd evolution-api-deploy
git init
git add Dockerfile render.yaml
git commit -m "Evolution API v2 deploy config"
git remote add origin https://github.com/SEU_USUARIO/evolution-api-deploy.git
git push -u origin main
```

### 2. Criar servico no Render.com

**Opcao A — Blueprint (recomendado):**
1. Acesse https://dashboard.render.com
2. Clique **New > Blueprint**
3. Conecte o repositorio `evolution-api-deploy`
4. O Render vai ler o `render.yaml` e criar o servico automaticamente
5. Preencha as variaveis de ambiente quando solicitado

**Opcao B — Web Service manual:**
1. Acesse https://dashboard.render.com
2. Clique **New > Web Service**
3. Conecte o repositorio `evolution-api-deploy`
4. Runtime: **Docker**
5. Plan: **Free** (ou Starter $7/mes para nao suspender)
6. Region: **Oregon**
7. Clique **Create Web Service**

### 3. Configurar variaveis de ambiente

No painel do servico no Render, va em **Environment** e adicione:

| Variavel | Valor |
|---|---|
| `AUTHENTICATION_API_KEY` | `terapeutas-agent-evo-key-2026` |
| `SERVER_URL` | `https://SEU-SERVICO.onrender.com` |
| `SERVER_PORT` | `8080` |
| `PORT` | `8080` |

> A `AUTHENTICATION_API_KEY` deve ser a MESMA que esta no `.env` do projeto principal como `EVOLUTION_API_KEY`.

### 4. Aguardar deploy

O Render vai:
1. Puxar a imagem `atendai/evolution-api:v2.2.3`
2. Buildar o Dockerfile
3. Iniciar o servico

Isso leva 3-5 minutos na primeira vez.

### 5. Testar

Acesse `https://SEU-SERVICO.onrender.com` no navegador.
Deve aparecer a interface da Evolution API.

Teste a API:
```bash
curl https://SEU-SERVICO.onrender.com/instance/fetchInstances \
  -H "apikey: terapeutas-agent-evo-key-2026"
```

### 6. Atualizar o projeto principal

No `.env` do projeto `terapeutas-agent`, atualize:
```
EVOLUTION_API_URL=https://SEU-SERVICO.onrender.com
```

---

## Limitacoes do Render Free Tier

- **Suspende apos 15 minutos de inatividade** — a primeira requisicao apos suspensao leva ~30s
- **750 horas/mes gratis** (suficiente para 1 servico 24/7)
- Para WhatsApp em producao, recomendo o plano **Starter ($7/mes)** para evitar desconexoes

## Alternativa: manter no Hugging Face Spaces

Se o deploy no Hugging Face Spaces (https://lucasbotaro-evolution-api.hf.space) estiver funcionando,
pode continuar usando. O Render e uma alternativa mais estavel para producao.

---

## Troubleshooting

**Erro: porta incorreta**
O Render exige que o servico escute na porta que ele define via `$PORT`.
A Evolution API v2 usa porta 8080 por padrao. Ja configuramos `PORT=8080` no render.yaml.

**Erro: imagem nao encontrada**
Verifique se o Dockerfile tem exatamente: `FROM atendai/evolution-api:v2.2.3`

**Servico reinicia em loop**
Verifique os logs no Render. Geralmente e problema de variavel de ambiente faltando.

**WhatsApp desconecta**
No free tier, quando o servico suspende, a sessao WhatsApp pode cair.
Solucao: usar plano Starter ou manter um cron job fazendo ping a cada 10 minutos.
