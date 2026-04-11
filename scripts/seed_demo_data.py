"""
Script de seed: cria 10 pacientes demo com histórico completo de conversas,
perfis de memória, resumos de sessão e chat_estado.

Uso: python scripts/seed_demo_data.py
"""

import json
import random
import uuid
from datetime import datetime, timedelta, timezone
import requests

SUPABASE_URL = "https://vtcjuaiuyjizkuyqfhtj.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZ0Y2p1YWl1eWppemt1eXFmaHRqIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NDE4Mzk4OCwiZXhwIjoyMDg5NzU5OTg4fQ.Ie1RAfW4TBFX1GKB2_5vTUKCpVV6SWWW1qa5bJoYetQ"
TERAPEUTA_ID = "5085ff75-fe00-49fe-95f4-a5922a0cf179"

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

def api_post(table, data, upsert=False):
    """Insere dados no Supabase via REST API."""
    headers = dict(HEADERS)
    if upsert:
        headers["Prefer"] = "resolution=merge-duplicates,return=representation"
    r = requests.post(f"{SUPABASE_URL}/rest/v1/{table}", headers=headers, json=data)
    if r.status_code not in (200, 201):
        print(f"ERRO em {table}: {r.status_code} - {r.text}")
        return None
    return r.json()

def api_get(table, params=""):
    """Busca dados do Supabase via REST API."""
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/{table}?{params}",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"},
    )
    if r.status_code == 200:
        return r.json()
    return []

def api_delete(table, params=""):
    """Deleta dados do Supabase via REST API."""
    r = requests.delete(
        f"{SUPABASE_URL}/rest/v1/{table}?{params}",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"},
    )
    return r.status_code in (200, 204)

def random_date(days_back_start, days_back_end=0):
    """Retorna datetime UTC aleatória entre days_back_start e days_back_end dias atrás."""
    now = datetime.now(timezone.utc)
    delta = random.randint(days_back_end, days_back_start)
    hours = random.randint(8, 21)
    minutes = random.randint(0, 59)
    d = now - timedelta(days=delta)
    return d.replace(hour=hours, minute=minutes, second=0, microsecond=0)


# =====================================================
# DADOS DOS PACIENTES
# =====================================================
PACIENTES = [
    {
        "nome": "Ana Carolina Ribeiro",
        "telefone": "5511900000001",
        "email": "ana.ribeiro@email.com",
        "genero": "feminino",
        "data_nascimento": "1989-03-15",
        "cidade_nascimento": "São Paulo",
        "sessoes": 12, "mensagens": 95,
        "temas": [
            {"tema": "ansiedade", "frequencia": 8},
            {"tema": "elemento_agua", "frequencia": 6},
            {"tema": "florais", "frequencia": 5},
            {"tema": "autoconhecimento", "frequencia": 4},
        ],
        "modo_principal": "CONSULTA",
        "perfil": "veterana",
    },
    {
        "nome": "Pedro Henrique Santos",
        "telefone": "5511900000002",
        "email": "pedro.santos@email.com",
        "genero": "masculino",
        "data_nascimento": "1995-07-22",
        "cidade_nascimento": "Belo Horizonte",
        "sessoes": 5, "mensagens": 38,
        "temas": [
            {"tema": "proposito_vida", "frequencia": 4},
            {"tema": "elemento_fogo", "frequencia": 3},
            {"tema": "mapa_natal", "frequencia": 3},
        ],
        "modo_principal": "PESQUISA",
        "perfil": "intermediario",
    },
    {
        "nome": "Juliana Ferreira Costa",
        "telefone": "5511900000003",
        "email": "juliana.costa@email.com",
        "genero": "feminino",
        "data_nascimento": "1982-11-08",
        "cidade_nascimento": "Curitiba",
        "sessoes": 15, "mensagens": 120,
        "temas": [
            {"tema": "trauma", "frequencia": 9},
            {"tema": "relacao_familiar", "frequencia": 7},
            {"tema": "elemento_terra", "frequencia": 5},
            {"tema": "florais", "frequencia": 4},
            {"tema": "depressao", "frequencia": 3},
        ],
        "modo_principal": "CONSULTA",
        "perfil": "veterana",
    },
    {
        "nome": "Marcos Oliveira Lima",
        "telefone": "5511900000004",
        "email": None,
        "genero": "masculino",
        "data_nascimento": "1991-01-30",
        "cidade_nascimento": "Rio de Janeiro",
        "sessoes": 3, "mensagens": 22,
        "temas": [
            {"tema": "relacionamento", "frequencia": 3},
            {"tema": "elemento_ar", "frequencia": 2},
        ],
        "modo_principal": "CONSULTA",
        "perfil": "novo",
    },
    {
        "nome": "Beatriz Almeida Souza",
        "telefone": "5511900000005",
        "email": "bia.souza@email.com",
        "genero": "feminino",
        "data_nascimento": "1997-06-12",
        "cidade_nascimento": "Salvador",
        "sessoes": 8, "mensagens": 65,
        "temas": [
            {"tema": "autoestima", "frequencia": 6},
            {"tema": "astrologia", "frequencia": 5},
            {"tema": "mapa_natal", "frequencia": 4},
            {"tema": "elemento_fogo", "frequencia": 3},
        ],
        "modo_principal": "PESQUISA",
        "perfil": "intermediario",
    },
    {
        "nome": "Rafael Duarte Mendes",
        "telefone": "5511900000006",
        "email": "rafael.mendes@email.com",
        "genero": "masculino",
        "data_nascimento": "1986-09-03",
        "cidade_nascimento": "Porto Alegre",
        "sessoes": 10, "mensagens": 82,
        "temas": [
            {"tema": "meditacao", "frequencia": 7},
            {"tema": "autoconhecimento", "frequencia": 6},
            {"tema": "elemento_agua", "frequencia": 5},
            {"tema": "proposito_vida", "frequencia": 3},
        ],
        "modo_principal": "CONSULTA",
        "perfil": "veterana",
    },
    {
        "nome": "Camila Rodrigues Neves",
        "telefone": "5511900000007",
        "email": None,
        "genero": "feminino",
        "data_nascimento": "1993-12-25",
        "cidade_nascimento": "Recife",
        "sessoes": 4, "mensagens": 30,
        "temas": [
            {"tema": "ansiedade", "frequencia": 3},
            {"tema": "florais", "frequencia": 3},
            {"tema": "elemento_terra", "frequencia": 2},
        ],
        "modo_principal": "CONSULTA",
        "perfil": "intermediario",
    },
    {
        "nome": "Lucas Gabriel Pinto",
        "telefone": "5511900000008",
        "email": "lucas.pinto@email.com",
        "genero": "masculino",
        "data_nascimento": "2000-04-18",
        "cidade_nascimento": "Brasília",
        "sessoes": 6, "mensagens": 48,
        "temas": [
            {"tema": "depressao", "frequencia": 5},
            {"tema": "autoestima", "frequencia": 4},
            {"tema": "elemento_agua", "frequencia": 3},
        ],
        "modo_principal": "CONSULTA",
        "perfil": "intermediario",
    },
    {
        "nome": "Fernanda Vieira Torres",
        "telefone": "5511900000009",
        "email": "fernanda.torres@email.com",
        "genero": "feminino",
        "data_nascimento": "1988-08-07",
        "cidade_nascimento": "Florianópolis",
        "sessoes": 14, "mensagens": 110,
        "temas": [
            {"tema": "astrologia", "frequencia": 8},
            {"tema": "mapa_natal", "frequencia": 7},
            {"tema": "elemento_ar", "frequencia": 5},
            {"tema": "autoconhecimento", "frequencia": 4},
            {"tema": "relacionamento", "frequencia": 3},
        ],
        "modo_principal": "PESQUISA",
        "perfil": "veterana",
    },
    {
        "nome": "Thiago Barbosa Cardoso",
        "telefone": "5511900000010",
        "email": None,
        "genero": "masculino",
        "data_nascimento": "1994-02-14",
        "cidade_nascimento": "Goiânia",
        "sessoes": 3, "mensagens": 20,
        "temas": [
            {"tema": "relacao_familiar", "frequencia": 2},
            {"tema": "elemento_fogo", "frequencia": 2},
        ],
        "modo_principal": "CONSULTA",
        "perfil": "novo",
    },
]


# =====================================================
# CONVERSAS MODELO — templates realistas
# =====================================================

CONVERSAS_TEMPLATES = {
    "ansiedade": [
        {
            "msg": "Oi, tô me sentindo muito ansiosa esses dias. Parece que meu peito tá sempre apertado e não consigo relaxar de jeito nenhum.",
            "resp": "Querida, que bom que você traz isso para nossa conversa. Essa sensação de aperto no peito é o seu elemento Água pedindo atenção — ele está represado, precisando fluir. Na alquimia interior, a ansiedade é como um rio que encontrou uma barragem. Vamos trabalhar juntas para abrir esses canais. Que tal começarmos com uma respiração de 4-7-8 agora mesmo? Inspire por 4 segundos, segure por 7, e solte lentamente por 8. 🌊",
            "intencao": "CONSULTA",
        },
        {
            "msg": "Tentei a respiração que vc me ensinou mas minha mente não para. É um pensamento atrás do outro, sem parar.",
            "resp": "Entendo perfeitamente. A mente acelerada e uma expressao do elemento Ar em desequilibrio — sao os ventos internos soprando sem direcao. Nao lute contra os pensamentos; observe-os como nuvens passando no ceu. Para te apoiar nesse processo, o floral Babosa do Kit Primus trabalha exatamente esse padrao de mente acelerada. Voce esta usando os florais que combinamos na ultima sessao?",
            "intencao": "CONSULTA",
        },
        {
            "msg": "Sim, tô tomando os florais. Sinto que ajudam um pouco mas à noite ainda é difícil dormir.",
            "resp": "O sono e o portal da transmutacao, querida. E durante a noite que a Grande Obra acontece no seu inconsciente. Sugiro adicionar ao seu ritual noturno: apague as luzes 30 minutos antes, faca a respiracao que praticamos, e coloque a intencao 'Eu me entrego ao fluxo da noite com confianca'. O floral Lantana do Kit Primus trabalha exatamente a questao da insonia. Vamos observar como voce se sente nos proximos 5 dias.",
            "intencao": "CONSULTA",
        },
    ],
    "elemento_agua": [
        {
            "msg": "Quero entender melhor o que significa ter o elemento água como dominante no meu mapa.",
            "resp": "Que linda busca, essa de conhecer suas águas interiores! O elemento Água no seu mapa representa sua capacidade de sentir profundamente, de fluir com a vida e de se conectar com a intuição. Como dominante, você é naturalmente empática, receptiva e possui grande sensibilidade emocional. O desafio é não se afogar nas próprias emoções — aprender a ser o rio sem se tornar a enchente. Na Alquimia Interior, trabalhamos para que sua Água encontre suas margens saudáveis. 💧",
            "intencao": "PESQUISA",
        },
        {
            "msg": "Faz sentido. Eu realmente sinto tudo muito intensamente. Às vezes parece que absorvo a energia dos outros.",
            "resp": "Isso é muito característico do elemento Água forte. Você funciona como uma esponja emocional — e isso não é defeito, é dom. Mas como todo dom, precisa ser lapidado. Na prática alquímica, chamamos isso de \"empatia sem fronteiras\". O trabalho aqui é criar o que eu chamo de \"margem alquímica\" — um limite saudável entre suas águas e as dos outros. Um exercício poderoso: toda manhã, visualize uma membrana dourada ao redor do seu corpo. Ela permite que o amor passe, mas filtra as emoções que não são suas.",
            "intencao": "CONSULTA",
        },
    ],
    "elemento_fogo": [
        {
            "msg": "Me disseram que tenho muito fogo no mapa. O que isso significa na prática?",
            "resp": "O Fogo é o elemento da vontade, da ação e da transformação! Ter muito Fogo significa que você possui uma energia vital intensa, capacidade de liderança e um desejo ardente de realizar coisas no mundo. Na Alquimia Interior, o Fogo é a fornalha que transmuta o chumbo em ouro — ou seja, transforma suas sombras em potenciais. O cuidado é não queimar rápido demais: impaciência, irritabilidade e esgotamento são sinais de Fogo desregulado. 🔥",
            "intencao": "PESQUISA",
        },
        {
            "msg": "Caramba, descreveu certinho. Eu me irrito fácil e depois me arrependo. Como trabalhar isso?",
            "resp": "Reconhecer esse padrão já é uma grande conquista — é o início da Opus Alquímica! A irritabilidade é o Fogo sem direção, como uma fogueira sem chaminé. O trabalho é criar canais saudáveis para essa energia: exercício físico intenso, projetos criativos, dança. E no momento da raiva, antes de reagir, pratique o \"respiro do dragão\": inspire pelas narinas com força, segure 3 segundos imaginando a chama ficando azul (controlada), e solte pela boca devagar. Azul é a cor do Fogo transmutado em sabedoria.",
            "intencao": "CONSULTA",
        },
    ],
    "elemento_terra": [
        {
            "msg": "Preciso me sentir mais aterrada. Tenho me sentido muito aérea, sem foco.",
            "resp": "Seu corpo está te pedindo Terra, querida. O elemento Terra é o fundamento, a raiz, o chão sob seus pés. Quando nos sentimos \"aéreas\", é porque perdemos a conexão com essa base. Na Alquimia Interior, o aterramento é o primeiro passo de qualquer Grande Obra. Exercício prático: caminhe descalça na grama por 10 minutos, sinta cada pedra, cada folha. Enquanto caminha, repita: \"Eu sou daqui. Meus pés conhecem este chão.\" O floral Trapoeraba do Kit Primus tambem ajuda muito nesse aterramento. 🌿",
            "intencao": "CONSULTA",
        },
    ],
    "elemento_ar": [
        {
            "msg": "Oi! Queria saber mais sobre o elemento Ar e como ele atua na minha vida.",
            "resp": "Olá! O elemento Ar é o sopro da mente, da comunicação e das ideias. Quando o Ar está equilibrado, você pensa com clareza, se comunica com leveza e consegue ver situações de múltiplos ângulos. É o elemento dos filósofos e dos pensadores. O desafio do Ar em excesso é a tendência à dispersão — muitas ideias, pouca materialização. E quando está em falta, surge dificuldade de expressão e rigidez mental. Na Alquimia, o Ar é o Mercúrio — o mensageiro que conecta o céu (ideais) à terra (prática). 💨",
            "intencao": "PESQUISA",
        },
    ],
    "florais": [
        {
            "msg": "Os florais que vc receitou estão fazendo efeito? Tô tomando há 1 semana.",
            "resp": "Uma semana é um bom começo! Os florais trabalham em camadas sutis — como a água que aos poucos molda a rocha. Geralmente os primeiros efeitos são percebidos entre 7 e 15 dias: sonhos mais vívidos, emoções que \"sobem\" para serem processadas, e uma sensação sutil de mais presença. Você notou algo diferente nos seus sonhos ou no seu humor nos últimos dias?",
            "intencao": "CONSULTA",
        },
        {
            "msg": "Sim! Tenho sonhado muito mais e com coisas do passado. É normal?",
            "resp": "Muito normal e é um ótimo sinal! Os florais estão fazendo exatamente o que devem: trazendo conteúdos inconscientes à superfície para serem transmutados. Na linguagem alquímica, chamamos isso de \"Nigredo\" — a fase de escuridão onde o material bruto começa a se decompor para ser purificado. Seus sonhos são o athanor (forno alquímico) trabalhando durante a noite. Anote os sonhos assim que acordar — eles carregam símbolos importantes para nosso trabalho. 📝",
            "intencao": "CONSULTA",
        },
    ],
    "mapa_natal": [
        {
            "msg": "Vc consegue ver alguma coisa no meu mapa natal sobre esse momento difícil que estou passando?",
            "resp": "Cada momento difícil tem um propósito no seu mapa, e o Universo não coloca diante de nós nada que não possamos transmutar. Os trânsitos atuais podem estar ativando áreas de transformação profunda no seu mapa. O que posso dizer é que momentos de crise são, na Alquimia, a fase de Calcinação — onde o fogo queima o que não é essencial para revelar o ouro verdadeiro. Você pode me contar mais sobre o que está sentindo? Assim consigo conectar com as energias do seu mapa. ✨",
            "intencao": "CONSULTA",
        },
        {
            "msg": "Quero entender a influência de Saturno no meu mapa. Sinto que tudo está mais pesado ultimamente.",
            "resp": "Saturno é o Grande Alquimista do zodíaco — ele é o Mestre que nos ensina através da disciplina e da estrutura. Quando Saturno fala alto no nosso mapa, sentimos peso, responsabilidade, limitação. Mas é justamente nessa pressão que o diamante é formado. Na Alquimia Interior, Saturno representa o Chumbo — o material mais denso, que contém dentro de si o ouro em potencial. O trabalho saturnal é de paciência: aceitar o tempo, honrar os limites, construir tijolo por tijolo. Esse período vai passar, e você sairá dele mais forte e mais sábia. 🪐",
            "intencao": "PESQUISA",
        },
    ],
    "autoconhecimento": [
        {
            "msg": "Tô num momento de querer me conhecer melhor. Por onde começo?",
            "resp": "Que momento lindo de estar vivendo! O autoconhecimento é a Pedra Filosofal da Alquimia Interior — é a grande busca de toda alma encarnada. O primeiro passo é o que os alquimistas chamavam de \"Conhece-te a ti mesmo\" (inscrito no Templo de Delfos). Comece observando seus padrões: o que te irrita repetidamente? O que te emociona? O que você evita? Essas são as portas de entrada para o seu mundo interior. Sugiro que comece um diário alquímico — toda noite, escreva 3 coisas que sentiu durante o dia e por quê. Vamos trabalhar juntos nessa jornada. 🗝️",
            "intencao": "CONSULTA",
        },
        {
            "msg": "Comecei o diário! Tô percebendo que tenho muito medo de rejeição. Isso aparece em tudo.",
            "resp": "Que descoberta poderosa! Perceber o medo de rejeição é abrir a tampa do athanor e olhar para dentro. Esse medo geralmente tem raízes no nosso primeiro setênio (0-7 anos) — é quando formamos nossas crenças sobre pertencimento. Na Alquimia Interior, o medo de rejeição é uma \"serpente\" que se enrola ao redor do coração, impedindo que ele se abra plenamente. O trabalho de transmutação começa com a compaixão: toda vez que sentir esse medo, coloque a mão no peito e diga \"Eu me aceito, mesmo com medo\". Aos poucos, a serpente se transforma em sabedoria. 🐍",
            "intencao": "CONSULTA",
        },
    ],
    "trauma": [
        {
            "msg": "Preciso falar sobre uma coisa difícil. Lembrei de coisas da infância que me machucaram muito.",
            "resp": "Obrigado por confiar em mim para esse momento tão delicado. Lembrar é o primeiro passo da cura — na Alquimia, dizemos que o que está no escuro não pode ser transmutado. As memórias dolorosas são como metais brutos que carregamos: pesados, mas contendo ouro em seu interior. Estou aqui para caminhar ao seu lado nesse processo. Lembre-se: você não é mais aquela criança indefesa — hoje você tem recursos que antes não tinha. Quer compartilhar o que veio à tona, no seu tempo?",
            "intencao": "CONSULTA",
        },
        {
            "msg": "Minha mãe era muito ausente e eu cresci sentindo que não era suficiente. Isso ainda me afeta hoje.",
            "resp": "Essa ferida de \"não ser suficiente\" é uma das mais profundas que a alma pode carregar. Na Alquimia Interior, chamamos isso de \"a ferida do Abandono\" — ela está ligada ao primeiro setênio e ao elemento Água (vínculo, nutrição, pertencimento). Você internalizou a ausência da mãe como uma falha sua, quando na verdade era a limitação dela. O processo de cura envolve separar: o que é seu e o que é dela. Você é suficiente, sempre foi. A criança dentro de você precisa ouvir isso da adulta que você se tornou. Vamos trabalhar essa re-parentalização com muito cuidado e amor. 💜",
            "intencao": "CONSULTA",
        },
    ],
    "depressao": [
        {
            "msg": "Tô sem energia pra nada. Levanto da cama e já quero voltar. Tudo parece cinza.",
            "resp": "Escuto você com todo o cuidado que esse momento pede. Quando tudo parece cinza, na Alquimia é a fase da Nigredo — a noite escura da alma, onde o antigo precisa morrer para o novo nascer. Não é fácil, e eu não vou minimizar sua dor. O que posso dizer é que essa escuridão não é permanente — ela é um estágio de transformação. Por agora, seja gentil consigo: levantou da cama hoje? Isso já é uma vitória. Uma coisa de cada vez. E me diga: você está acompanhando com algum profissional de saúde mental presencialmente? É importante termos essa rede de apoio. 🤍",
            "intencao": "CONSULTA",
        },
        {
            "msg": "Sim, faço terapia presencial também. Mas às vezes entre as sessões bate forte.",
            "resp": "Fico aliviado em saber que você tem esse acompanhamento. O espaço entre as sessões pode ser desafiador — é quando ficamos a sós com nossos processos. Na tradição alquímica, esse é o tempo do \"forno lento\": a transformação precisa de tempo em fogo baixo. Para esses momentos mais difíceis, sugiro: 1) Saia de casa nem que seja por 5 minutos — o Sol é o melhor floral que existe; 2) Beba água — parece simples, mas desidratação intensifica estados depressivos; 3) Me mande uma mensagem aqui — estou disponível. Você não está sozinho nessa caminhada. 🌤️",
            "intencao": "CONSULTA",
        },
    ],
    "relacao_familiar": [
        {
            "msg": "Tô tendo conflitos sérios com meu pai. Ele não aceita minhas escolhas e eu me sinto sufocado.",
            "resp": "A relação com o pai é um dos pilares mais poderosos na Alquimia Interior — ele representa o princípio do Sol, da autoridade e da estrutura. Quando essa relação está em conflito, é como se nosso Sol interno estivesse eclipsado. O sentimento de sufocamento indica que você está no processo de individuação — se separando das expectativas dele para encontrar as suas. Isso é saudável e necessário, mesmo que doa. A questão não é convencê-lo, mas se autorizar internamente. O que exatamente ele não aceita?",
            "intencao": "CONSULTA",
        },
    ],
    "autoestima": [
        {
            "msg": "Não me sinto bonita, não me sinto inteligente. Parece que todo mundo é melhor que eu.",
            "resp": "Querida, o que você está sentindo tem nome na Alquimia: é o \"Espelho Distorcido\" — quando nosso Mercúrio interno (percepção) está turvo, ele nos mostra uma imagem falsa de nós mesmas. A comparação é o veneno mais sutil que existe, porque usa a beleza do outro para nos envenenar. Cada alma é um composto único — você tem elementos que ninguém mais tem nessa exata combinação. O trabalho aqui é polir seu espelho interno. Exercício: toda manhã, olhe nos seus próprios olhos no espelho por 30 segundos e diga \"Eu me vejo. Eu sou o bastante.\" Pode parecer estranho no início, mas é poderoso. 🪞",
            "intencao": "CONSULTA",
        },
    ],
    "relacionamento": [
        {
            "msg": "Terminei um relacionamento de 3 anos e tô destruído. Não sei como seguir em frente.",
            "resp": "Sinto muito pelo que está passando. O fim de um relacionamento longo é uma pequena morte — e na Alquimia, toda morte precede um renascimento, mas isso não diminui a dor do agora. Permita-se sentir: chorar, ficar triste, sentir raiva — todas essas emoções são o fogo da calcinação queimando o que foi. O erro seria tentar pular essa fase. Seus 3 anos não foram em vão — cada momento foi um ingrediente na sua Grande Obra. O que você construiu internamente nessa relação permanece. Estou aqui para te acompanhar nesse luto. Quer me contar o que aconteceu?",
            "intencao": "CONSULTA",
        },
    ],
    "proposito_vida": [
        {
            "msg": "Tô com 29 anos e sinto que não sei qual é meu propósito. Vejo todo mundo realizando coisas e eu tô parado.",
            "resp": "Os 29 anos são um marco poderoso — na Astrologia, é quando Saturno completa sua primeira volta no seu mapa (o famoso Retorno de Saturno). É NATURAL sentir esse vazio de propósito nessa idade. O Universo está te convidando a questionar tudo que foi construído até aqui e decidir: o que é verdadeiramente meu e o que foi colocado por outros? O propósito não é encontrado — é construído, tijolo por tijolo. E \"estar parado\" pode ser apenas a pausa antes do grande salto. Na Alquimia, chamamos isso de Separatio: separar o essencial do supérfluo. O que te faz perder a noção do tempo quando está fazendo?",
            "intencao": "CONSULTA",
        },
        {
            "msg": "Acho que é quando estou cozinhando ou quando estou ajudando alguém com problemas. Me sinto útil.",
            "resp": "Olha que lindeza! Cozinhar é uma arte alquímica pura — transformar ingredientes brutos em algo que nutre e dá prazer. E ajudar o outro é o dom do Curador. Veja: seu propósito pode estar exatamente na interseção desses dois dons — nutrir e curar. Não precisa ser literal (virar chef ou terapeuta), mas essas pistas são ouro puro. Na Alquimia, dizemos que o propósito se revela quando paramos de procurar fora e olhamos para o que já fazemos naturalmente com amor. Seu ouro já está aí — só precisa ser reconhecido. ✨",
            "intencao": "CONSULTA",
        },
    ],
    "meditacao": [
        {
            "msg": "Quero começar a meditar mas não consigo ficar parado. Minha mente não para.",
            "resp": "A mente que não para é exatamente a mente que MAIS precisa de meditação — é como dizer \"não consigo ir à academia porque estou fora de forma\". Na Alquimia Interior, a meditação é o Athanor — o forno onde a transformação acontece. Mas não precisa começar com 30 minutos de silêncio total. Comece com 3 minutos: sente-se confortavelmente, feche os olhos, e apenas conte suas respirações de 1 a 10. Quando perder a conta (vai acontecer), volte ao 1 sem julgamento. O objetivo NÃO é esvaziar a mente — é observar sem se prender. 3 minutos. Todo dia. Vamos? 🧘",
            "intencao": "CONSULTA",
        },
        {
            "msg": "Consegui meditar 5 minutos ontem! Ainda pensei muito mas não desisti.",
            "resp": "ISSO é vitória! 5 minutos com pensamentos é infinitamente mais poderoso que 0 minutos de \"meditação perfeita\". Na tradição alquímica, cada vez que você nota um pensamento e volta ao respiro, está exercitando o Mercúrio — a consciência que observa. Esse músculo se fortalece com a prática. Em 30 dias fazendo isso diariamente, você vai notar mudanças na sua reatividade emocional, no seu sono e na sua clareza mental. Continue com 5 minutos — só aumente quando sentir que é natural. Estou orgulhoso do seu progresso! 🌟",
            "intencao": "CONSULTA",
        },
    ],
    "astrologia": [
        {
            "msg": "Mercúrio retrógrado tá me destruindo. Tudo dá errado, comunicação péssima, eletrônicos pifando.",
            "resp": "Ah, o famoso Mercúrio Retrógrado! Na Alquimia Interior, vemos esse período não como uma maldição, mas como um convite para REVISAR, REVER, REFLETIR — tudo que começa com RE. É o Universo pedindo que você olhe para trás antes de seguir em frente. Em vez de lutar contra a maré, surfe-a: revise contratos, reconecte com pessoas antigas, reorganize sua vida. Os problemas de comunicação acontecem quando tentamos forçar o novo durante um período de revisão. Respira fundo: dura mais umas semanas e depois vem uma clareza incrível. 📡",
            "intencao": "PESQUISA",
        },
    ],
    "saudacao": [
        {
            "msg": "Oi, tudo bem?",
            "resp": "Olá! Tudo em harmonia por aqui. Como você está se sentindo hoje? Estou aqui para te ouvir e caminhar junto nessa jornada de autoconhecimento. 🌟",
            "intencao": "SAUDACAO",
        },
        {
            "msg": "Bom dia!",
            "resp": "Bom dia! Que o Sol de hoje ilumine seus processos internos. Em que posso te ajudar na sua caminhada alquímica? ☀️",
            "intencao": "SAUDACAO",
        },
    ],
}


def get_conversas_for_paciente(pac):
    """Gera conversas realistas para um paciente baseado em seus temas."""
    temas_do_paciente = [t["tema"] for t in pac["temas"]]
    conversas = []

    # Sempre começa com saudação
    saudacao = random.choice(CONVERSAS_TEMPLATES["saudacao"])
    conversas.append(saudacao)

    # Adiciona conversas dos temas relevantes
    for tema in temas_do_paciente:
        if tema in CONVERSAS_TEMPLATES:
            templates = CONVERSAS_TEMPLATES[tema]
            for t in templates:
                conversas.append(t)

    # Adiciona saudações extras se veterana
    if pac["perfil"] == "veterana":
        conversas.append(random.choice(CONVERSAS_TEMPLATES["saudacao"]))

    # Limita baseado no perfil
    if pac["perfil"] == "novo":
        conversas = conversas[:5]
    elif pac["perfil"] == "intermediario":
        conversas = conversas[:8]
    else:
        conversas = conversas[:15]

    return conversas


def main():
    print("=" * 60)
    print("SEED DE DADOS DEMO — Terapeutas Agent")
    print("=" * 60)

    # ── Limpar dados antigos de demo ─────────────────────────
    print("\n[0/10] Limpando dados demo anteriores...")
    telefones_demo = [p["telefone"] for p in PACIENTES]

    # Limpar conversas, perfil_usuario, resumos_sessao, chat_estado dos telefones demo
    for tel in telefones_demo:
        api_delete("conversas", f"terapeuta_id=eq.{TERAPEUTA_ID}&paciente_numero=eq.{tel}")
        api_delete("perfil_usuario", f"terapeuta_id=eq.{TERAPEUTA_ID}&numero_telefone=eq.{tel}")
        api_delete("resumos_sessao", f"terapeuta_id=eq.{TERAPEUTA_ID}&numero_telefone=eq.{tel}")
        api_delete("chat_estado", f"terapeuta_id=eq.{TERAPEUTA_ID}&numero_telefone=eq.{tel}")
    # Buscar IDs dos pacientes demo para limpar FKs
    existing_pacs = api_get("pacientes", f"terapeuta_id=eq.{TERAPEUTA_ID}&numero_telefone=in.({','.join(telefones_demo)})&select=id")
    for ep in existing_pacs:
        api_delete("diagnosticos_alquimicos", f"paciente_id=eq.{ep['id']}")
        api_delete("anotacoes_prontuario", f"paciente_id=eq.{ep['id']}")
        api_delete("acompanhamentos", f"paciente_id=eq.{ep['id']}")
    # Limpar mapas_astrais e documentos (não dependem de paciente_id)
    for tel in telefones_demo:
        api_delete("mapas_astrais", f"numero_telefone=eq.{tel}")
    api_delete("documentos", f"terapeuta_id=eq.{TERAPEUTA_ID}")
    # Limpar pacientes demo
    for tel in telefones_demo:
        api_delete("pacientes", f"terapeuta_id=eq.{TERAPEUTA_ID}&numero_telefone=eq.{tel}")
    print("  Dados antigos removidos.")

    # ── STEP 2: Inserir pacientes ────────────────────────────
    print("\n[1/10] Inserindo pacientes...")
    paciente_ids = {}
    for pac in PACIENTES:
        data = {
            "terapeuta_id": TERAPEUTA_ID,
            "numero_telefone": pac["telefone"],
            "nome": pac["nome"],
            "email": pac["email"],
            "genero": pac["genero"],
            "data_nascimento": pac["data_nascimento"],
            "cidade_nascimento": pac["cidade_nascimento"],
            "status": "ativo",
            "tags": ["demo"],
        }
        # Remove None values
        data = {k: v for k, v in data.items() if v is not None}

        result = api_post("pacientes", data)
        if result and len(result) > 0:
            pid = result[0]["id"]
            paciente_ids[pac["telefone"]] = pid
            print(f"  OK {pac['nome']} -> {pid}")
        else:
            print(f"  FALHA ao inserir {pac['nome']}")

    if not paciente_ids:
        print("ERRO: Nenhum paciente inserido. Abortando.")
        return

    # ── STEP 3: Inserir perfis de memória ────────────────────
    print("\n[2/10] Inserindo perfis de memória...")
    for pac in PACIENTES:
        if pac["telefone"] not in paciente_ids:
            continue

        preferencias = {
            "modos_count": {
                "CONSULTA": random.randint(5, 30),
                "PESQUISA": random.randint(2, 15),
                "SAUDACAO": random.randint(3, 10),
            },
            "modo_principal": pac["modo_principal"],
        }

        data = {
            "terapeuta_id": TERAPEUTA_ID,
            "numero_telefone": pac["telefone"],
            "nome": pac["nome"],
            "total_sessoes": pac["sessoes"],
            "total_mensagens": pac["mensagens"],
            "temas_principais": pac["temas"],
            "preferencias": preferencias,
            "ultima_sessao_em": random_date(3, 0).isoformat(),
        }

        result = api_post("perfil_usuario", data)
        if result:
            print(f"  OK Perfil de {pac['nome']}")
        else:
            print(f"  FALHA Falha no perfil de {pac['nome']}")

    # ── STEP 4: Inserir conversas ────────────────────────────
    print("\n[3/10] Inserindo conversas...")
    total_conversas = 0
    for pac in PACIENTES:
        if pac["telefone"] not in paciente_ids:
            continue

        conversas = get_conversas_for_paciente(pac)
        for i, conv in enumerate(conversas):
            dias_atras = len(conversas) - i  # mais antigas primeiro
            data_conversa = random_date(dias_atras * 2 + 1, dias_atras * 2)

            data = {
                "terapeuta_id": TERAPEUTA_ID,
                "paciente_numero": pac["telefone"],
                "mensagem_paciente": conv["msg"],
                "resposta_agente": conv["resp"],
                "intencao": conv["intencao"],
                "criado_em": data_conversa.isoformat(),
            }

            result = api_post("conversas", data)
            if result:
                total_conversas += 1

        print(f"  OK {pac['nome']}: {len(conversas)} conversas")

    print(f"  Total: {total_conversas} conversas inseridas")

    # ── STEP 5: Inserir resumos de sessão ────────────────────
    print("\n[4/10] Inserindo resumos de sessão...")
    resumos_data = {
        "5511900000001": [  # Ana Carolina — ansiedade, água, florais
            {
                "resumo": "Paciente relatou ansiedade intensa com aperto no peito. Trabalhamos tecnica de respiracao e identificamos desequilibrio no elemento Agua. Iniciou uso de florais do Kit Primus. Demonstrou boa receptividade ao processo alquimico.",
                "temas": ["ansiedade", "elemento_agua", "florais", "respiracao"],
                "total_mensagens": 12,
            },
            {
                "resumo": "Sessão focada em insônia e mente acelerada. Elemento Ar em desequilíbrio identificado. Adicionado floral Lantana ao protocolo. Paciente relata melhora parcial com florais anteriores. Sugerido ritual noturno de aterramento.",
                "temas": ["ansiedade", "florais", "insonia", "elemento_ar"],
                "total_mensagens": 8,
            },
            {
                "resumo": "Paciente apresentou evolução significativa. Relata sonhos vívidos — fase de Nigredo ativa. Orientada a manter diário de sonhos. Elemento Água mais equilibrado. Autoconhecimento em expansão.",
                "temas": ["autoconhecimento", "florais", "sonhos", "elemento_agua"],
                "total_mensagens": 10,
            },
            {
                "resumo": "Sessão de manutenção. Ana relata maior estabilidade emocional e melhor qualidade de sono. Florais fazendo efeito após 3 semanas. Discutimos próximos passos na jornada alquímica — trabalho com elemento Terra para aterramento.",
                "temas": ["florais", "evolucao", "elemento_terra", "estabilidade"],
                "total_mensagens": 6,
            },
        ],
        "5511900000003": [  # Juliana — trauma, família, terra
            {
                "resumo": "Paciente trouxe memórias dolorosas da infância — ausência materna. Identificada ferida de Abandono no primeiro setênio. Trabalho de re-parentalização iniciado. Elemento Água fortemente mobilizado. Acolhimento foi prioridade.",
                "temas": ["trauma", "relacao_familiar", "elemento_agua", "infancia"],
                "total_mensagens": 15,
            },
            {
                "resumo": "Continuação do trabalho com trauma. Juliana conseguiu separar 'o que é dela' do que é da mãe. Momento de grande insight. Florais Paineira prescritos. Humor melhorou significativamente ao final.",
                "temas": ["trauma", "florais", "insight", "cura"],
                "total_mensagens": 12,
            },
            {
                "resumo": "Sessão sobre padrões de depressão ligados ao trauma original. Discutimos fase de Nigredo como necessária. Paciente demonstra resiliência crescente. Exercício de aterramento com elemento Terra funcionando bem.",
                "temas": ["depressao", "trauma", "elemento_terra", "resiliencia"],
                "total_mensagens": 10,
            },
            {
                "resumo": "Juliana relata que conflitos familiares diminuíram. Conseguiu estabelecer limites com a mãe de forma amorosa. Grande progresso na individuação. Trabalho alquímico de Separatio em andamento.",
                "temas": ["relacao_familiar", "limites", "individuacao", "progresso"],
                "total_mensagens": 8,
            },
            {
                "resumo": "Sessão integrativa. Revisamos toda a jornada: do trauma inicial à reconexão consigo mesma. Paciente reconhece transformações profundas. Elemento Terra estabilizado. Próximo ciclo: trabalhar proposito e Rubedo.",
                "temas": ["integracao", "evolucao", "elemento_terra", "proposito_vida"],
                "total_mensagens": 11,
            },
        ],
        "5511900000005": [  # Beatriz — autoestima, astrologia, mapa
            {
                "resumo": "Paciente trouxe questões de autoestima — 'Espelho Distorcido'. Trabalhamos exercício do espelho diário. Forte conexão com elemento Fogo precisando ser ativado. Interesse em astrologia como ferramenta de autoconhecimento.",
                "temas": ["autoestima", "elemento_fogo", "astrologia", "autoconhecimento"],
                "total_mensagens": 9,
            },
            {
                "resumo": "Análise do mapa natal focada em Saturno e seus desafios atuais. Beatriz compreendeu que a fase de 'peso' é saturnal e temporária. Floral Amor-Perfeito prescrito para autoestima. Boa receptividade.",
                "temas": ["mapa_natal", "astrologia", "florais", "saturno"],
                "total_mensagens": 11,
            },
            {
                "resumo": "Sessão sobre Mercúrio Retrógrado e como usar o período para revisão interna. Paciente relata melhora na autoestima após exercício do espelho. Elemento Fogo mais equilibrado — menos comparação, mais ação.",
                "temas": ["astrologia", "autoestima", "elemento_fogo", "mercurio"],
                "total_mensagens": 7,
            },
        ],
        "5511900000006": [  # Rafael — meditação, autoconhecimento, água
            {
                "resumo": "Paciente iniciou prática de meditação — 3 minutos diários. Muita resistência mental inicial (elemento Ar agitado). Orientado sobre expectativas realistas. Introduzido conceito do Athanor como forno interno da transformação.",
                "temas": ["meditacao", "elemento_ar", "inicio", "expectativas"],
                "total_mensagens": 8,
            },
            {
                "resumo": "Rafael conseguiu meditar 5 minutos! Progresso no exercício de observação de pensamentos. Trabalhamos conceito de Mercúrio como consciência observadora. Elemento Água trazendo mais sensibilidade emocional.",
                "temas": ["meditacao", "progresso", "elemento_agua", "consciencia"],
                "total_mensagens": 10,
            },
            {
                "resumo": "Sessão profunda sobre propósito de vida. Rafael questiona carreira e sente vazio existencial. Trabalhamos conceito de Separatio — separar o essencial do supérfluo. Meditação já é prática diária estabelecida.",
                "temas": ["proposito_vida", "autoconhecimento", "meditacao", "carreira"],
                "total_mensagens": 13,
            },
            {
                "resumo": "Sessão integrativa. Rafael descobriu que cozinhar e ajudar pessoas são seus dons naturais. Conexão com propósito começando a se clarear. Elemento Água equilibrado. Práticas de meditação ampliadas para 15 minutos.",
                "temas": ["proposito_vida", "autoconhecimento", "meditacao", "evolucao"],
                "total_mensagens": 9,
            },
        ],
        "5511900000008": [  # Lucas Gabriel — depressão, autoestima
            {
                "resumo": "Paciente relatou sintomas depressivos: falta de energia, visão 'cinza'. Fase de Nigredo identificada. Confirmado acompanhamento presencial com psicólogo. Orientações de autocuidado básico: sol, água, movimento mínimo.",
                "temas": ["depressao", "nigredo", "autocuidado", "acompanhamento"],
                "total_mensagens": 8,
            },
            {
                "resumo": "Lucas relata que momentos entre sessões presenciais são difíceis. Trabalhamos estratégias de enfrentamento: saídas curtas, hidratação, contato com natureza. Autoestima ainda baixa mas humor ligeiramente melhor.",
                "temas": ["depressao", "autoestima", "estrategias", "melhora_sutil"],
                "total_mensagens": 10,
            },
        ],
        "5511900000009": [  # Fernanda — astrologia, mapa natal, ar
            {
                "resumo": "Sessão rica sobre astrologia e mapa natal. Fernanda tem grande conhecimento prévio. Trabalhamos influência de Saturno no momento atual — sensação de peso e responsabilidade. Elemento Ar dominante: muitas ideias, pouca materialização.",
                "temas": ["astrologia", "mapa_natal", "saturno", "elemento_ar"],
                "total_mensagens": 14,
            },
            {
                "resumo": "Discussão sobre Mercúrio Retrógrado e suas influências práticas. Paciente aprendendo a usar o período para revisão ao invés de resistir. Relacionamento amoroso mencionado como área de desafio.",
                "temas": ["astrologia", "mercurio_retrogrado", "relacionamento", "revisao"],
                "total_mensagens": 10,
            },
            {
                "resumo": "Sessão sobre autoconhecimento via mapa natal. Fernanda fez conexões profundas entre padrões astrológicos e comportamentais. Elemento Ar mais equilibrado após exercícios de aterramento. Grande evolução na autoconsciência.",
                "temas": ["autoconhecimento", "mapa_natal", "elemento_ar", "evolucao"],
                "total_mensagens": 12,
            },
            {
                "resumo": "Fernanda trouxe questão de relacionamento — padrão de se perder no outro. Trabalhamos limites saudáveis através da lente astrológica (Vênus/Netuno). Exercício de 'margem alquímica' para proteção energética.",
                "temas": ["relacionamento", "astrologia", "limites", "protecao_energetica"],
                "total_mensagens": 11,
            },
            {
                "resumo": "Sessão integrativa. Revisamos jornada de 14 sessões. Fernanda demonstra autoconhecimento significativamente maior. Elemento Ar em equilíbrio. Próximo ciclo: aprofundar trabalho com elemento Terra para materializar insights.",
                "temas": ["integracao", "evolucao", "elemento_ar", "elemento_terra"],
                "total_mensagens": 9,
            },
        ],
    }

    total_resumos = 0
    for telefone, resumos in resumos_data.items():
        for i, res in enumerate(resumos):
            dias_atras_inicio = (len(resumos) - i) * 5 + random.randint(1, 3)
            dias_atras_fim = dias_atras_inicio - random.randint(0, 1)
            sessao_inicio = random_date(dias_atras_inicio, dias_atras_inicio)
            sessao_fim = random_date(dias_atras_fim, dias_atras_fim)

            data = {
                "terapeuta_id": TERAPEUTA_ID,
                "numero_telefone": telefone,
                "sessao_inicio": sessao_inicio.isoformat(),
                "sessao_fim": sessao_fim.isoformat(),
                "resumo": res["resumo"],
                "temas": res["temas"],
                "total_mensagens": res["total_mensagens"],
            }

            result = api_post("resumos_sessao", data)
            if result:
                total_resumos += 1

        # Find the name for the phone number
        nome = next((p["nome"] for p in PACIENTES if p["telefone"] == telefone), telefone)
        print(f"  OK {nome}: {len(resumos)} resumos")

    print(f"  Total: {total_resumos} resumos inseridos")

    # ── STEP 6: Inserir chat_estado ──────────────────────────
    print("\n[5/10] Inserindo chat_estado...")
    for pac in PACIENTES:
        if pac["telefone"] not in paciente_ids:
            continue

        data = {
            "terapeuta_id": TERAPEUTA_ID,
            "numero_telefone": pac["telefone"],
            "estado": "ATIVO",
            "nome_usuario": pac["nome"],
            "codigo_usado": "demo",
            "ultima_mensagem_em": random_date(2, 0).isoformat(),
        }

        result = api_post("chat_estado", data)
        if result:
            print(f"  OK Chat estado de {pac['nome']}")
        else:
            print(f"  FALHA Falha no chat estado de {pac['nome']}")

    # ── STEP 7: Inserir diagnósticos alquímicos ───────────────
    print("\n[6/10] Inserindo diagnósticos alquímicos...")

    DNA_OPTIONS = ["Abandono", "Rejeição", "Humilhação", "Traição", "Injustiça"]
    SERPENTES_OPTIONS = ["Medo", "Raiva", "Culpa", "Vergonha", "Tristeza", "Ansiedade", "Inveja", "Ciúme"]
    FLORAIS_KIT_PRIMUS = [
        "Abutilom", "Amor-Perfeito", "Assa-Peixe", "Boca-de-Leao", "Cactos",
        "Carqueja", "Cravo", "Acucena", "Anis", "Azaleia",
        "Boldo", "Calendula", "Cassia", "Crisantemo", "Agapanto",
        "Anturio", "Babosa", "Borragem", "Dalia", "Lantana",
    ]
    ELEMENTOS = ["Fogo", "Água", "Ar", "Terra"]
    SETENIOS = {
        1: "Setênio da impressão (0-7 anos) — formação do corpo etérico, vínculo com a mãe, confiança básica",
        2: "Setênio da imitação (7-14 anos) — desenvolvimento emocional, relação com autoridade, criatividade",
        3: "Setênio da individualização (14-21 anos) — pensamento próprio, identidade, despertar da sexualidade",
        4: "Setênio da alma sensível (21-28 anos) — encontro com o mundo, ideais, relações afetivas profundas",
        5: "Setênio da alma racional (28-35 anos) — crise de sentido, retorno de Saturno, maturidade emocional",
        6: "Setênio da alma consciencial (35-42 anos) — meia-vida, propósito, confronto com a sombra",
        7: "Setênio do espírito (42-49 anos) — sabedoria, mentor interior, desapego do ego",
        8: "Setênio da colheita (49-56 anos) — integração da jornada, legado, generatividade",
        9: "Setênio da transcendência (56-63 anos) — espiritualidade madura, aceitação, plenitude",
    }

    diagnosticos = [
        # Ana Carolina — ansiedade, água dominante
        {
            "paciente_tel": "5511900000001",
            "elemento_dominante": "Água", "elemento_carente": "Terra",
            "elementos_detalhes": {"Fogo": 4, "Água": 9, "Ar": 6, "Terra": 2},
            "dna_comprometido": ["Abandono", "Rejeição"],
            "serpentes_ativas": ["Ansiedade", "Medo", "Tristeza"],
            "setenio_atual": 5,
            "florais_prescritos": ["Babosa", "Lantana", "Camomila", "Alfazema"],
            "protocolo_texto": "Protocolo de aterramento com elemento Terra: caminhada descalca 10min/dia, respiracao antes de dormir. Florais 4 gotas 4x/dia. Diario emocional noturno focado em gratidao.",
            "sessao_data": "2026-03-10", "status": "finalizado", "fonte": "manual",
        },
        {
            "paciente_tel": "5511900000001",
            "elemento_dominante": "Água", "elemento_carente": "Terra",
            "elementos_detalhes": {"Fogo": 5, "Água": 8, "Ar": 5, "Terra": 3},
            "dna_comprometido": ["Abandono"],
            "serpentes_ativas": ["Ansiedade", "Medo"],
            "setenio_atual": 5,
            "florais_prescritos": ["Hortelã", "Babosa", "Dama-da-Noite", "Boldo"],
            "protocolo_texto": "Ajuste de protocolo: adicionar Hortela para medos difusos noturnos. Manter aterramento. Adicionar visualizacao da membrana dourada pela manha.",
            "sessao_data": "2026-03-22", "status": "finalizado", "fonte": "manual",
        },
        # Pedro Henrique — fogo, propósito
        {
            "paciente_tel": "5511900000002",
            "elemento_dominante": "Fogo", "elemento_carente": "Água",
            "elementos_detalhes": {"Fogo": 8, "Água": 3, "Ar": 6, "Terra": 5},
            "dna_comprometido": ["Injustiça"],
            "serpentes_ativas": ["Raiva", "Ansiedade"],
            "setenio_atual": 4,
            "florais_prescritos": ["Boca-de-Leao", "Carqueja", "Cactos"],
            "protocolo_texto": "Canalizar energia do Fogo: exercicio fisico intenso 3x/semana. Respiracao do dragao nos momentos de irritacao. Diario de proposito — anotar 1 coisa que fez sentido no dia.",
            "sessao_data": "2026-03-18", "status": "finalizado", "fonte": "manual",
        },
        # Juliana — trauma, terra, família
        {
            "paciente_tel": "5511900000003",
            "elemento_dominante": "Terra", "elemento_carente": "Fogo",
            "elementos_detalhes": {"Fogo": 2, "Água": 7, "Ar": 4, "Terra": 8},
            "dna_comprometido": ["Abandono", "Humilhação", "Rejeição"],
            "serpentes_ativas": ["Tristeza", "Culpa", "Vergonha"],
            "setenio_atual": 6,
            "florais_prescritos": ["Paineira", "Serralha", "Boldo", "Araucaria", "Crisantemo"],
            "protocolo_texto": "Trabalho de re-parentalizacao: carta a crianca interior 1x/semana. Florais Paineira para liberacao de traumas passados e Serralha para compreensao. Exercicio de separacao eu/mae. Limites amorosos com familia.",
            "sessao_data": "2026-03-05", "status": "finalizado", "fonte": "manual",
        },
        {
            "paciente_tel": "5511900000003",
            "elemento_dominante": "Terra", "elemento_carente": "Fogo",
            "elementos_detalhes": {"Fogo": 3, "Água": 6, "Ar": 5, "Terra": 8},
            "dna_comprometido": ["Abandono", "Humilhação"],
            "serpentes_ativas": ["Tristeza", "Culpa"],
            "setenio_atual": 6,
            "florais_prescritos": ["Paineira", "Araucaria", "Amor-Perfeito", "Girassol"],
            "protocolo_texto": "Evolucao positiva. Ajuste de florais: retirar Serralha (culpa processada), adicionar Amor-Perfeito (autoestima) e Girassol (integracao). Manter re-parentalizacao. Iniciar trabalho com Fogo — vontade propria.",
            "sessao_data": "2026-03-20", "status": "finalizado", "fonte": "manual",
        },
        # Marcos — ar, relacionamento, novo
        {
            "paciente_tel": "5511900000004",
            "elemento_dominante": "Ar", "elemento_carente": "Terra",
            "elementos_detalhes": {"Fogo": 5, "Água": 4, "Ar": 8, "Terra": 3},
            "dna_comprometido": ["Traição"],
            "serpentes_ativas": ["Ciúme", "Medo"],
            "setenio_atual": 5,
            "florais_prescritos": ["Crisantemo", "Araucaria", "Aguape"],
            "protocolo_texto": "Paciente novo, avaliacao inicial. Elemento Ar dominante com dispersao mental. Trabalho inicial de aterramento. Florais Crisantemo para abrir o coracao e Araucaria para forca interior. Proxima sessao aprofundar ferida de Traicao.",
            "sessao_data": "2026-03-25", "status": "finalizado", "fonte": "manual",
        },
        # Beatriz — fogo, autoestima, astrologia
        {
            "paciente_tel": "5511900000005",
            "elemento_dominante": "Fogo", "elemento_carente": "Água",
            "elementos_detalhes": {"Fogo": 7, "Água": 3, "Ar": 6, "Terra": 5},
            "dna_comprometido": ["Rejeição", "Humilhação"],
            "serpentes_ativas": ["Vergonha", "Tristeza", "Inveja"],
            "setenio_atual": 4,
            "florais_prescritos": ["Amor-Perfeito", "Boldo", "Serralha", "Jurubeba"],
            "protocolo_texto": "Espelho Distorcido identificado — Mercurio turvo. Exercicio do espelho diario (30 seg olhando nos olhos + afirmacao). Florais Amor-Perfeito para autoestima e Boldo para limpar sentimentos grosseiros. Analise do mapa natal como ferramenta.",
            "sessao_data": "2026-03-12", "status": "finalizado", "fonte": "manual",
        },
        {
            "paciente_tel": "5511900000005",
            "elemento_dominante": "Fogo", "elemento_carente": "Água",
            "elementos_detalhes": {"Fogo": 7, "Água": 4, "Ar": 5, "Terra": 5},
            "dna_comprometido": ["Rejeição"],
            "serpentes_ativas": ["Vergonha", "Inveja"],
            "setenio_atual": 4,
            "florais_prescritos": ["Amor-Perfeito", "Araucaria", "Girassol"],
            "protocolo_texto": "Melhora na autoestima apos 3 semanas de exercicio do espelho. Ajuste: retirar Boldo e Serralha (processados). Foco em Araucaria para fortalecer identidade propria e nao se comparar.",
            "sessao_data": "2026-03-26", "status": "finalizado", "fonte": "manual",
        },
        # Rafael — água, meditação, autoconhecimento
        {
            "paciente_tel": "5511900000006",
            "elemento_dominante": "Água", "elemento_carente": "Fogo",
            "elementos_detalhes": {"Fogo": 3, "Água": 8, "Ar": 5, "Terra": 6},
            "dna_comprometido": ["Injustiça", "Abandono"],
            "serpentes_ativas": ["Tristeza", "Medo"],
            "setenio_atual": 5,
            "florais_prescritos": ["Aguape", "Rosa", "Dama-da-Noite", "Araucaria"],
            "protocolo_texto": "Meditacao como Athanor: pratica diaria de 5 min com contagem de respiracoes. Florais Aguape para inspiracao e Rosa para decisao universal. Questao existencial do Retorno de Saturno em trabalho.",
            "sessao_data": "2026-03-14", "status": "finalizado", "fonte": "manual",
        },
        # Camila — terra, ansiedade, florais
        {
            "paciente_tel": "5511900000007",
            "elemento_dominante": "Terra", "elemento_carente": "Ar",
            "elementos_detalhes": {"Fogo": 4, "Água": 5, "Ar": 2, "Terra": 7},
            "dna_comprometido": ["Humilhação", "Injustiça"],
            "serpentes_ativas": ["Ansiedade", "Vergonha"],
            "setenio_atual": 4,
            "florais_prescritos": ["Hortela", "Camomila", "Beldroega", "Espinheira-Santa"],
            "protocolo_texto": "Ansiedade com componente de vergonha social. Terra dominante traz rigidez — dificuldade de se expressar (Ar carente). Florais Hortela para confortar medos e Beldroega para impulso da vida. Exercicios de comunicacao autentica.",
            "sessao_data": "2026-03-19", "status": "finalizado", "fonte": "manual",
        },
        # Lucas Gabriel — água, depressão
        {
            "paciente_tel": "5511900000008",
            "elemento_dominante": "Água", "elemento_carente": "Fogo",
            "elementos_detalhes": {"Fogo": 2, "Água": 8, "Ar": 4, "Terra": 5},
            "dna_comprometido": ["Abandono", "Rejeição"],
            "serpentes_ativas": ["Tristeza", "Medo", "Culpa"],
            "setenio_atual": 3,
            "florais_prescritos": ["Mandacaru", "Dama-da-Noite", "Bracatinga", "Cravo"],
            "protocolo_texto": "Nigredo ativa — fase depressiva. Autocuidado prioritario: sol 15min/dia, agua 2L, caminhada curta. Florais Mandacaru para morte e renascimento e Dama-da-Noite para realizacao interior. Manter acompanhamento presencial com psicologo.",
            "sessao_data": "2026-03-16", "status": "finalizado", "fonte": "manual",
        },
        {
            "paciente_tel": "5511900000008",
            "elemento_dominante": "Água", "elemento_carente": "Fogo",
            "elementos_detalhes": {"Fogo": 3, "Água": 7, "Ar": 4, "Terra": 5},
            "dna_comprometido": ["Abandono"],
            "serpentes_ativas": ["Tristeza", "Medo"],
            "setenio_atual": 3,
            "florais_prescritos": ["Mandacaru", "Abutilom", "Amor-Perfeito", "Araucaria"],
            "protocolo_texto": "Melhora sutil no humor. Troca de Dama-da-Noite por Abutilom (projetos realizados). Adicao de Amor-Perfeito para autoestima. Manter protocolos de autocuidado. Incentivar pequenas conquistas diarias.",
            "sessao_data": "2026-03-28", "status": "rascunho", "fonte": "manual",
        },
        # Fernanda — ar, astrologia, mapa natal
        {
            "paciente_tel": "5511900000009",
            "elemento_dominante": "Ar", "elemento_carente": "Terra",
            "elementos_detalhes": {"Fogo": 5, "Água": 4, "Ar": 9, "Terra": 3},
            "dna_comprometido": ["Traição", "Injustiça"],
            "serpentes_ativas": ["Ansiedade", "Ciúme"],
            "setenio_atual": 5,
            "florais_prescritos": ["Jacaranda", "Araucaria", "Aguape", "Cactos"],
            "protocolo_texto": "Ar em excesso: muita analise, pouca acao. Aterramento via elemento Terra essencial. Exercicios de materializacao: escolher 1 insight por semana e colocar em pratica. Florais Jacaranda para integrar intuicao e razao.",
            "sessao_data": "2026-03-08", "status": "finalizado", "fonte": "manual",
        },
        {
            "paciente_tel": "5511900000009",
            "elemento_dominante": "Ar", "elemento_carente": "Terra",
            "elementos_detalhes": {"Fogo": 5, "Água": 5, "Ar": 8, "Terra": 4},
            "dna_comprometido": ["Traição"],
            "serpentes_ativas": ["Ansiedade"],
            "setenio_atual": 5,
            "florais_prescritos": ["Araucaria", "Aguape", "Espinheira-Santa", "Cactos"],
            "protocolo_texto": "Evolucao significativa. Ar mais equilibrado com praticas de aterramento. Padrao de se perder em relacionamentos sendo trabalhado — margem alquimica. Ajuste de florais: Espinheira-Santa para controle emocional e Cactos para forca interna.",
            "sessao_data": "2026-03-24", "status": "finalizado", "fonte": "manual",
        },
        # Thiago — fogo, família, novo
        {
            "paciente_tel": "5511900000010",
            "elemento_dominante": "Fogo", "elemento_carente": "Água",
            "elementos_detalhes": {"Fogo": 8, "Água": 2, "Ar": 5, "Terra": 6},
            "dna_comprometido": ["Traição", "Injustiça"],
            "serpentes_ativas": ["Raiva", "Medo"],
            "setenio_atual": 4,
            "florais_prescritos": ["Crisantemo", "Boca-de-Leao", "Sete-Sangrias"],
            "protocolo_texto": "Avaliacao inicial. Fogo intenso com conflitos familiares — relacao com pai (Sol eclipsado). Respiracao do dragao para momentos de raiva. Florais Crisantemo para abrir o coracao e Boca-de-Leao para integrar os opostos. Inicio do processo de individuacao.",
            "sessao_data": "2026-03-27", "status": "rascunho", "fonte": "manual",
        },
    ]

    total_diag = 0
    for diag in diagnosticos:
        tel = diag.pop("paciente_tel")
        if tel not in paciente_ids:
            continue
        data = {
            "id": str(uuid.uuid4()),
            "terapeuta_id": TERAPEUTA_ID,
            "paciente_id": paciente_ids[tel],
            "elemento_dominante": diag["elemento_dominante"],
            "elemento_carente": diag["elemento_carente"],
            "elementos_detalhes": diag["elementos_detalhes"],
            "dna_comprometido": diag["dna_comprometido"],
            "serpentes_ativas": diag["serpentes_ativas"],
            "setenio_atual": diag["setenio_atual"],
            "setenio_descricao": SETENIOS[diag["setenio_atual"]],
            "florais_prescritos": diag["florais_prescritos"],
            "protocolo_texto": diag["protocolo_texto"],
            "sessao_data": diag["sessao_data"],
            "status": diag["status"],
            "fonte": diag["fonte"],
            "criado_em": diag["sessao_data"] + "T10:00:00-03:00",
        }
        result = api_post("diagnosticos_alquimicos", data)
        if result:
            total_diag += 1
    print(f"  Total: {total_diag} diagnósticos inseridos")

    # ── STEP 8: Inserir acompanhamentos ─────────────────────────
    print("\n[7/10] Inserindo acompanhamentos...")

    acompanhamentos = [
        # Ana Carolina — retornos e florais
        {"tel": "5511900000001", "tipo": "retorno", "descricao": "Retorno para avaliação dos florais após 3 semanas de uso", "data_prevista": "2026-03-29", "data_realizado": None, "status": "pendente", "prioridade": 1},
        {"tel": "5511900000001", "tipo": "floral", "descricao": "Preparar nova formula floral — ajuste Hortela + Babosa", "data_prevista": "2026-03-29", "data_realizado": None, "status": "pendente", "prioridade": 2},
        {"tel": "5511900000001", "tipo": "tarefa", "descricao": "Verificar diário emocional da paciente — pediu feedback", "data_prevista": "2026-03-31", "data_realizado": None, "status": "pendente", "prioridade": 3},
        # Pedro Henrique
        {"tel": "5511900000002", "tipo": "retorno", "descricao": "Sessão de acompanhamento — verificar prática de exercício físico", "data_prevista": "2026-04-01", "data_realizado": None, "status": "pendente", "prioridade": 2},
        {"tel": "5511900000002", "tipo": "contato", "descricao": "Ligar para verificar como está após última sessão intensa", "data_prevista": "2026-03-29", "data_realizado": None, "status": "pendente", "prioridade": 2},
        # Juliana — acompanhamento de trauma
        {"tel": "5511900000003", "tipo": "retorno", "descricao": "Sessão de re-parentalização — carta à criança interior", "data_prevista": "2026-03-29", "data_realizado": None, "status": "pendente", "prioridade": 1},
        {"tel": "5511900000003", "tipo": "floral", "descricao": "Renovar formula floral — Paineira + Araucaria + Amor-Perfeito", "data_prevista": "2026-03-30", "data_realizado": None, "status": "pendente", "prioridade": 2},
        {"tel": "5511900000003", "tipo": "marco", "descricao": "Juliana completou 15 sessões — preparar avaliação de progresso", "data_prevista": "2026-04-02", "data_realizado": None, "status": "pendente", "prioridade": 2},
        {"tel": "5511900000003", "tipo": "retorno", "descricao": "Sessão sobre limites familiares — evolução do Separatio", "data_prevista": "2026-03-15", "data_realizado": "2026-03-15", "status": "realizado", "prioridade": 1},
        # Marcos — novo paciente
        {"tel": "5511900000004", "tipo": "retorno", "descricao": "Segunda sessão — aprofundar ferida de Traição", "data_prevista": "2026-04-01", "data_realizado": None, "status": "pendente", "prioridade": 1},
        {"tel": "5511900000004", "tipo": "tarefa", "descricao": "Enviar material sobre elementos e temperamentos por WhatsApp", "data_prevista": "2026-03-29", "data_realizado": None, "status": "pendente", "prioridade": 3},
        # Beatriz — autoestima e astrologia
        {"tel": "5511900000005", "tipo": "retorno", "descricao": "Acompanhamento do exercício do espelho — verificar consistência", "data_prevista": "2026-03-29", "data_realizado": None, "status": "pendente", "prioridade": 2},
        {"tel": "5511900000005", "tipo": "floral", "descricao": "Avaliar se manter Amor-Perfeito ou trocar por Rosa", "data_prevista": "2026-04-03", "data_realizado": None, "status": "pendente", "prioridade": 2},
        {"tel": "5511900000005", "tipo": "contato", "descricao": "Enviar interpretação complementar do trânsito de Saturno", "data_prevista": "2026-03-20", "data_realizado": "2026-03-20", "status": "realizado", "prioridade": 3},
        # Rafael — meditação e propósito
        {"tel": "5511900000006", "tipo": "retorno", "descricao": "Sessão sobre propósito — explorar dons de cozinhar e curar", "data_prevista": "2026-04-02", "data_realizado": None, "status": "pendente", "prioridade": 1},
        {"tel": "5511900000006", "tipo": "tarefa", "descricao": "Preparar exercício de Separatio personalizado", "data_prevista": "2026-03-31", "data_realizado": None, "status": "pendente", "prioridade": 2},
        {"tel": "5511900000006", "tipo": "marco", "descricao": "Rafael completou 30 dias de meditação diária!", "data_prevista": "2026-03-25", "data_realizado": "2026-03-25", "status": "realizado", "prioridade": 1},
        # Camila
        {"tel": "5511900000007", "tipo": "retorno", "descricao": "Retorno para avaliar florais e exercícios de comunicação", "data_prevista": "2026-04-03", "data_realizado": None, "status": "pendente", "prioridade": 2},
        {"tel": "5511900000007", "tipo": "contato", "descricao": "Mensagem de acolhimento — paciente estava ansiosa na última sessão", "data_prevista": "2026-03-29", "data_realizado": None, "status": "pendente", "prioridade": 2},
        # Lucas Gabriel — depressão
        {"tel": "5511900000008", "tipo": "retorno", "descricao": "Sessão de acompanhamento — monitorar humor e autocuidado", "data_prevista": "2026-03-29", "data_realizado": None, "status": "pendente", "prioridade": 1},
        {"tel": "5511900000008", "tipo": "floral", "descricao": "Preparar nova formula — Mandacaru + Abutilom + Amor-Perfeito", "data_prevista": "2026-03-30", "data_realizado": None, "status": "pendente", "prioridade": 1},
        {"tel": "5511900000008", "tipo": "contato", "descricao": "Contato para verificar como está entre sessões presenciais", "data_prevista": "2026-03-22", "data_realizado": "2026-03-22", "status": "realizado", "prioridade": 1},
        # Fernanda — astrologia
        {"tel": "5511900000009", "tipo": "retorno", "descricao": "Sessão de integração — revisão das 14 sessões e próximo ciclo", "data_prevista": "2026-04-05", "data_realizado": None, "status": "pendente", "prioridade": 1},
        {"tel": "5511900000009", "tipo": "tarefa", "descricao": "Preparar análise dos trânsitos de abril para a paciente", "data_prevista": "2026-03-31", "data_realizado": None, "status": "pendente", "prioridade": 3},
        {"tel": "5511900000009", "tipo": "floral", "descricao": "Ajuste floral — trocar Jacaranda por Espinheira-Santa conforme evolucao", "data_prevista": "2026-03-18", "data_realizado": "2026-03-18", "status": "realizado", "prioridade": 2},
        # Thiago — novo
        {"tel": "5511900000010", "tipo": "retorno", "descricao": "Segunda sessão — trabalho com relação paterna e individuação", "data_prevista": "2026-04-03", "data_realizado": None, "status": "pendente", "prioridade": 1},
        {"tel": "5511900000010", "tipo": "tarefa", "descricao": "Enviar áudio explicativo sobre respiração do dragão", "data_prevista": "2026-03-29", "data_realizado": None, "status": "pendente", "prioridade": 3},
        {"tel": "5511900000010", "tipo": "contato", "descricao": "Ligar para Thiago — saiu muito mobilizado da primeira sessão", "data_prevista": "2026-03-28", "data_realizado": "2026-03-28", "status": "realizado", "prioridade": 1},
    ]

    total_acomp = 0
    for acomp in acompanhamentos:
        tel = acomp["tel"]
        if tel not in paciente_ids:
            continue
        data = {
            "id": str(uuid.uuid4()),
            "terapeuta_id": TERAPEUTA_ID,
            "paciente_id": paciente_ids[tel],
            "tipo": acomp["tipo"],
            "descricao": acomp["descricao"],
            "data_prevista": acomp["data_prevista"],
            "data_realizado": acomp["data_realizado"],
            "status": acomp["status"],
            "prioridade": acomp["prioridade"],
            "criado_em": "2026-03-20T10:00:00-03:00",
        }
        # Remove None values
        data = {k: v for k, v in data.items() if v is not None}
        result = api_post("acompanhamentos", data)
        if result:
            total_acomp += 1
    print(f"  Total: {total_acomp} acompanhamentos inseridos")

    # ── STEP 9: Inserir anotações de prontuário ─────────────────
    print("\n[8/10] Inserindo anotações de prontuário...")

    anotacoes = [
        # Ana Carolina
        {"tel": "5511900000001", "texto": "Paciente chegou muito ansiosa, relatando aperto no peito constante ha 2 semanas. Identificado desequilibrio no elemento Agua — emocoes represadas. Prescrito protocolo de aterramento e florais Babosa + Lantana do Kit Primus.", "data": "2026-03-10T10:30:00-03:00"},
        {"tel": "5511900000001", "texto": "Ana relata melhora parcial com florais. Insônia persiste. Adicionado Lantana ao protocolo. Sonhos vívidos indicam início da fase de Nigredo — conteúdos inconscientes emergindo para processamento.", "data": "2026-03-17T14:00:00-03:00"},
        {"tel": "5511900000001", "texto": "Evolução positiva significativa. Sono melhorou, ansiedade reduziu de 8/10 para 5/10. Elemento Água mais fluido. Manter protocolo atual por mais 2 semanas.", "data": "2026-03-22T11:00:00-03:00"},
        # Pedro Henrique
        {"tel": "5511900000002", "texto": "Primeira sessão profunda sobre propósito de vida. Pedro está no Retorno de Saturno (29 anos) — questionando tudo. Elemento Fogo forte mas sem direção. Prescrito exercício físico como canal.", "data": "2026-03-18T09:00:00-03:00"},
        {"tel": "5511900000002", "texto": "Pedro descobriu que cozinhar e ajudar os outros são seus dons naturais. Conexão com propósito começando a se clarear. Momento de Separatio — separar o essencial do supérfluo.", "data": "2026-03-25T10:00:00-03:00"},
        # Juliana
        {"tel": "5511900000003", "texto": "Sessão delicada. Juliana trouxe memórias de abandono materno. Choro intenso. Ferida de Abandono claramente ativa no primeiro setênio. Acolhimento foi prioridade. Prescrito Paineira.", "data": "2026-03-05T15:00:00-03:00"},
        {"tel": "5511900000003", "texto": "Juliana conseguiu fazer a separação 'eu vs. mãe' pela primeira vez. Momento de grande insight terapêutico. Culpa diminuindo. Retirado Serralha do protocolo floral.", "data": "2026-03-12T14:30:00-03:00"},
        {"tel": "5511900000003", "texto": "Progresso notável nos limites familiares. Juliana estabeleceu conversa firme e amorosa com a mãe. Processo de individuação avançando. Elemento Terra estabilizando.", "data": "2026-03-20T16:00:00-03:00"},
        # Marcos
        {"tel": "5511900000004", "texto": "Avaliação inicial. Marcos é paciente novo, veio por indicação. Queixa principal: término recente e ciúme. Elemento Ar dominante com dispersão. Ferida de Traição identificada preliminarmente.", "data": "2026-03-25T11:00:00-03:00"},
        # Beatriz
        {"tel": "5511900000005", "texto": "Beatriz apresenta quadro clássico de Espelho Distorcido — autoimagem muito abaixo da realidade. Comparação constante com outros. Prescrito exercicio do espelho + Amor-Perfeito.", "data": "2026-03-12T10:00:00-03:00"},
        {"tel": "5511900000005", "texto": "Análise do mapa natal revelou Saturno transitando sobre Vênus — período de reconstrução da autoestima. Beatriz compreendeu e se sentiu acolhida pela explicação astrológica.", "data": "2026-03-19T09:30:00-03:00"},
        {"tel": "5511900000005", "texto": "Melhora visível na autoestima. Beatriz faz exercício do espelho todos os dias. Relata que a comparação com outros diminuiu. Ajuste de florais: retirar Boldo.", "data": "2026-03-26T11:00:00-03:00"},
        # Rafael
        {"tel": "5511900000006", "texto": "Rafael iniciou meditação — 3 minutos com contagem de respirações. Muita resistência mental inicial. Orientado sobre expectativas realistas. Conceito do Athanor introduzido.", "data": "2026-03-14T08:30:00-03:00"},
        {"tel": "5511900000006", "texto": "Conseguiu meditar 5 minutos! Progresso no exercício de observação. Trabalhamos Mercúrio como consciência observadora. Prática ficando mais natural.", "data": "2026-03-21T09:00:00-03:00"},
        {"tel": "5511900000006", "texto": "Sessão profunda sobre propósito. Vazio existencial em processamento. Separatio em andamento — Rafael começando a distinguir desejos próprios de expectativas externas.", "data": "2026-03-28T10:00:00-03:00"},
        # Camila
        {"tel": "5511900000007", "texto": "Camila apresenta ansiedade com componente de vergonha social forte. Elemento Terra dominante traz rigidez. Ar carente dificulta expressão. Prescrito Beldroega para impulso de vida.", "data": "2026-03-19T14:00:00-03:00"},
        {"tel": "5511900000007", "texto": "Observação: Camila tende a minimizar o que sente ('não é nada demais'). Padrão de Humilhação ativo. Trabalho de validação emocional sendo priorizado nas sessões.", "data": "2026-03-26T15:00:00-03:00"},
        # Lucas Gabriel
        {"tel": "5511900000008", "texto": "Lucas em fase depressiva — Nigredo. Falta de energia, visão cinza. Confirmado acompanhamento com psicólogo presencial. Autocuidado básico: sol, água, movimento mínimo. Florais Mandacaru + Dama-da-Noite.", "data": "2026-03-16T10:00:00-03:00"},
        {"tel": "5511900000008", "texto": "Melhora sutil no humor. Lucas saiu de casa 3 vezes na semana. Pequenas conquistas sendo celebradas. Troca de Dama-da-Noite por Abutilom para motivacao matinal.", "data": "2026-03-23T11:00:00-03:00"},
        {"tel": "5511900000008", "texto": "ATENÇÃO: Lucas relatou episódio de choro intenso entre sessões. Orientado a contatar psicólogo presencial. Reforçada a rede de apoio. Monitorar de perto.", "data": "2026-03-28T16:00:00-03:00"},
        # Fernanda
        {"tel": "5511900000009", "texto": "Fernanda tem excelente conhecimento astrológico prévio. Sessão produtiva sobre Saturno e elemento Ar. Muitas ideias mas pouca materialização — aterramento necessário.", "data": "2026-03-08T10:00:00-03:00"},
        {"tel": "5511900000009", "texto": "Trabalhamos padrão de se perder em relacionamentos (Vênus/Netuno). Margem alquímica como ferramenta de proteção energética. Fernanda respondeu bem ao conceito.", "data": "2026-03-15T11:30:00-03:00"},
        {"tel": "5511900000009", "texto": "Grande evolução. Ar mais equilibrado. Fernanda está conseguindo materializar insights em ações concretas. Próximo ciclo: aprofundar elemento Terra.", "data": "2026-03-24T10:00:00-03:00"},
        # Thiago
        {"tel": "5511900000010", "texto": "Primeira sessão. Thiago veio com conflito paterno intenso. Fogo muito forte — raiva como emoção predominante. Ferida de Traição e Injustiça identificadas. Respiração do dragão ensinada.", "data": "2026-03-27T14:00:00-03:00"},
        {"tel": "5511900000010", "texto": "NOTA: Thiago saiu mobilizado da sessão. Enviada mensagem de acolhimento no dia seguinte. Respondeu positivamente. Manter monitoramento próximo nas primeiras semanas.", "data": "2026-03-28T09:00:00-03:00"},
    ]

    total_anot = 0
    for anot in anotacoes:
        tel = anot["tel"]
        if tel not in paciente_ids:
            continue
        data = {
            "id": str(uuid.uuid4()),
            "terapeuta_id": TERAPEUTA_ID,
            "paciente_id": paciente_ids[tel],
            "conteudo": anot["texto"],
            "data_anotacao": anot["data"][:10],
            "tipo": "observacao",
            "titulo": "Anotação de sessão",
            "criado_em": anot["data"],
        }
        result = api_post("anotacoes_prontuario", data)
        if result:
            total_anot += 1
    print(f"  Total: {total_anot} anotações inseridas")

    # ── STEP 10: Inserir mapas astrais ──────────────────────────
    print("\n[9/10] Inserindo mapas astrais...")

    mapas = [
        {"tel": "5511900000001", "nome": "Ana Carolina", "data_nasc": "1989-03-15", "tipo": "Mapa Natal"},
        {"tel": "5511900000003", "nome": "Juliana", "data_nasc": "1982-11-08", "tipo": "Mapa Natal"},
        {"tel": "5511900000005", "nome": "Beatriz", "data_nasc": "1997-06-12", "tipo": "Mapa Natal"},
        {"tel": "5511900000006", "nome": "Rafael", "data_nasc": "1986-09-03", "tipo": "Mapa Natal"},
        {"tel": "5511900000008", "nome": "Lucas Gabriel", "data_nasc": "2000-04-18", "tipo": "Mapa Natal"},
        {"tel": "5511900000009", "nome": "Fernanda", "data_nasc": "1988-08-07", "tipo": "Mapa Natal"},
        {"tel": "5511900000009", "nome": "Fernanda", "data_nasc": "1988-08-07", "tipo": "Revolução Solar 2026"},
        {"tel": "5511900000002", "nome": "Pedro Henrique", "data_nasc": "1995-07-22", "tipo": "Mapa Natal"},
        {"tel": "5511900000007", "nome": "Camila", "data_nasc": "1993-12-25", "tipo": "Mapa Natal"},
    ]

    total_mapas = 0
    for mapa in mapas:
        nome_url = mapa["nome"].replace(" ", "+")
        tipo_url = mapa["tipo"].replace(" ", "+")
        horas = ["08:30", "10:15", "14:00", "16:45", "06:20", "12:30", "22:10", "09:00", "11:45"]
        cidades = ["São Paulo, SP", "Rio de Janeiro, RJ", "Belo Horizonte, MG", "Curitiba, PR", "Salvador, BA", "Brasília, DF", "Porto Alegre, RS", "Recife, PE", "Fortaleza, CE"]
        signos = ["Áries", "Touro", "Gêmeos", "Câncer", "Leão", "Virgem", "Libra", "Escorpião", "Sagitário"]
        ascendentes = ["Leão", "Virgem", "Escorpião", "Peixes", "Capricórnio", "Áries", "Libra", "Gêmeos", "Touro"]
        luas = ["Câncer", "Aquário", "Peixes", "Sagitário", "Touro", "Leão", "Virgem", "Capricórnio", "Gêmeos"]
        idx = mapas.index(mapa)
        mapa_json = {
            "sol": {"signo": signos[idx % len(signos)], "casa": random.randint(1, 12), "grau": round(random.uniform(0, 29), 1)},
            "lua": {"signo": luas[idx % len(luas)], "casa": random.randint(1, 12), "grau": round(random.uniform(0, 29), 1)},
            "ascendente": {"signo": ascendentes[idx % len(ascendentes)], "grau": round(random.uniform(0, 29), 1)},
            "elemento_dominante": random.choice(["Fogo", "Terra", "Ar", "Água"]),
            "modalidade_dominante": random.choice(["Cardinal", "Fixo", "Mutável"]),
        }
        data = {
            "id": str(uuid.uuid4()),
            "terapeuta_id": TERAPEUTA_ID,
            "numero_telefone": mapa["tel"],
            "nome": mapa["nome"],
            "data_nascimento": mapa["data_nasc"],
            "hora_nascimento": horas[idx % len(horas)],
            "cidade_nascimento": cidades[idx % len(cidades)],
            "mapa_json": json.dumps(mapa_json),
            "imagem_url": f"https://placehold.co/600x600/2d1b69/gold?text={tipo_url}%0A{nome_url}",
            "criado_em": "2026-03-10T10:00:00-03:00",
        }
        result = api_post("mapas_astrais", data)
        if result:
            total_mapas += 1
    print(f"  Total: {total_mapas} mapas astrais inseridos")

    # ── STEP 11: Inserir documentos ─────────────────────────────
    print("\n[10/10] Inserindo documentos...")

    documentos = [
        {"nome_arquivo": "A Aura das Ervas.pdf", "titulo": "A Aura das Ervas — Joel Aleixo", "total_chunks": 768, "data": "2026-03-01T10:00:00-03:00"},
        {"nome_arquivo": "Guia de Alquimia Interior.pdf", "titulo": "Guia de Alquimia Interior", "total_chunks": 78, "data": "2026-03-01T12:00:00-03:00"},
        {"nome_arquivo": "Manual do Terapeuta - Setenios.pdf", "titulo": "Manual do Terapeuta - Setênios", "total_chunks": 52, "data": "2026-03-02T09:00:00-03:00"},
        {"nome_arquivo": "Tabela de Elementos e Temperamentos.pdf", "titulo": "Tabela de Elementos e Temperamentos", "total_chunks": 18, "data": "2026-03-03T14:00:00-03:00"},
        {"nome_arquivo": "Serpentes da Alma - Guia Pratico.pdf", "titulo": "Serpentes da Alma - Guia Prático", "total_chunks": 35, "data": "2026-03-05T10:00:00-03:00"},
        {"nome_arquivo": "DNA Emocional - Feridas Fundamentais.pdf", "titulo": "DNA Emocional - Feridas Fundamentais", "total_chunks": 62, "data": "2026-03-07T11:00:00-03:00"},
        {"nome_arquivo": "Mapa Natal e Elementos.pdf", "titulo": "Mapa Natal e Elementos - Correlações", "total_chunks": 41, "data": "2026-03-08T15:00:00-03:00"},
    ]

    total_docs = 0
    for doc in documentos:
        data = {
            "id": str(uuid.uuid4()),
            "terapeuta_id": TERAPEUTA_ID,
            "nome_arquivo": doc["nome_arquivo"],
            "status": "ativo",
            "total_chunks": doc["total_chunks"],
            "processado": True,
            "criado_em": doc["data"],
        }
        result = api_post("documentos", data)
        if result:
            total_docs += 1
    print(f"  Total: {total_docs} documentos inseridos")

    # ── Verificação final ────────────────────────────────────
    print("\n" + "=" * 60)
    print("VERIFICAÇÃO FINAL")
    print("=" * 60)

    tables_with_terapeuta = [
        "pacientes", "perfil_usuario", "conversas", "resumos_sessao",
        "chat_estado", "diagnosticos_alquimicos", "acompanhamentos",
        "anotacoes_prontuario", "documentos",
    ]
    for table in tables_with_terapeuta:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/{table}?terapeuta_id=eq.{TERAPEUTA_ID}&select=id",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
            },
        )
        count = len(r.json()) if r.status_code == 200 else "ERRO"
        print(f"  {table}: {count} registros")

    # mapas_astrais não tem terapeuta_id, verificar por telefone
    telefones_param = ",".join(telefones_demo)
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/mapas_astrais?numero_telefone=in.({telefones_param})&select=id",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
        },
    )
    count = len(r.json()) if r.status_code == 200 else "ERRO"
    print(f"  mapas_astrais: {count} registros")

    print("\nDONE Seed completo!")
    print(f"  Login: email do terapeuta + senha 'demo2026'")


if __name__ == "__main__":
    main()
