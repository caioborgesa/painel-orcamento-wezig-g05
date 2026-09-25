# =============================================================
# RELATORIOS DO ORCAMENTO — as abas do painel
# =============================================================
#
# O QUE ESTE ARQUIVO FAZ
#   Monta as cinco visoes que antes sairiam do OrcaFascio:
#     Sintetico        a planilha orcamentaria, na ordem da EAP
#     Analitico        cada composicao usada, aberta item a item
#     ABC de insumos   o que a obra consome, do maior gasto para o menor
#     ABC de servicos  os servicos, do maior gasto para o menor
#     Resumo           o total por macro-servico e as pendencias
#
#   As colunas seguem os relatorios de verdade que o Caio guardou em
#   0 REFERENCIA\RELAOTORIOS ORCAFASCIO — eles sao a especificacao.
#
# DE ONDE VEM O NUMERO
#   Tudo sai do "orcamento WEZIG <carimbo>.json" ja pronto. Nenhuma conta
#   e refeita aqui: relatorio que recalcula e relatorio que discorda do
#   arquivo que ele deveria mostrar.
#
# NUMERO NA TELA x NUMERO NO EXCEL
#   Cada montar_*() devolve a tabela com NUMERO DE VERDADE. E ela que vai
#   para o Excel, para poder ser somada e ordenada la.
#   Para a tela, para_a_tela() faz uma copia com os numeros escritos em
#   pt-BR ("R$ 1.234,56"). Sao dois usos diferentes do mesmo dado — por
#   isso a formatacao fica no fim, e nao no meio da conta.
#
# DUAS FORMAS DE TABELA
#   Sintetico e Analitico tem niveis, entao usam a arvore-tabela
#   (arvore_tabela.py), que abre e fecha igual a arvore da auditoria.
#   As curvas ABC sao listas ordenadas, sem niveis: continuam em
#   st.dataframe, com as faixas A, B e C em cores.
# =============================================================

import io

import pandas as pd
import streamlit as st

from arvore_tabela import arvore_tabela
from formatos import (formatar_coeficiente, formatar_numero,
                      formatar_porcentagem, formatar_reais)

# Como cada coluna deve aparecer na tela, pelo nome dela.
FORMATO_DA_COLUNA = {
    "Valor unit.": formatar_reais,
    "Total": formatar_reais,
    "Quant.": formatar_numero,
    "Quantidade": formatar_numero,
    "Coef.": formatar_coeficiente,
    "Peso": formatar_porcentagem,
    "Peso acumulado": formatar_porcentagem,
}

# -------------------------------------------------------------
# FAIXAS DA CURVA ABC
#
# A curva ABC separa o que merece atencao do que nao merece: poucos itens
# respondem pela maior parte do dinheiro. O corte usado aqui e o mais
# comum no orcamento de obra (Aldo Dorea Mattos):
#   faixa A  ate 50% do custo acumulado   <- negociar item a item
#   faixa B  de 50% a 80%                 <- acompanhar
#   faixa C  o resto                      <- comprar sem cerimonia
# O item que ATRAVESSA o corte fica na faixa de baixo (a mais exigente).
# -------------------------------------------------------------
CORTE_DA_FAIXA_A = 0.50
CORTE_DA_FAIXA_B = 0.80

COR_DA_FAIXA = {
    "A": "background-color: rgba(224, 49, 49, 0.14)",
    "B": "background-color: rgba(245, 159, 0, 0.16)",
    "C": "background-color: rgba(47, 158, 68, 0.10)",
}


def faixa_abc(acumulado_antes):
    """Em que faixa cai o item, pelo acumulado ANTES dele entrar."""
    if acumulado_antes < CORTE_DA_FAIXA_A:
        return "A"
    if acumulado_antes < CORTE_DA_FAIXA_B:
        return "B"
    return "C"


def para_a_tela(tabela):
    """Copia da tabela com os numeros em pt-BR, para o st.dataframe.

    Vai como texto de proposito: coluna de numero do Streamlit escreve
    "None" na celula vazia e usa o ponto decimal do ingles.
    """
    na_tela = tabela.copy()
    for coluna, formatar in FORMATO_DA_COLUNA.items():
        if coluna in na_tela.columns:
            na_tela[coluna] = [formatar(valor) if pd.notna(valor) else ""
                               for valor in na_tela[coluna]]
    return na_tela


def baixar_excel(tabela, nome_do_arquivo, chave):
    """Botao para salvar a tabela em Excel, com os numeros como numeros."""
    memoria = io.BytesIO()
    with pd.ExcelWriter(memoria, engine="openpyxl") as escritor:
        tabela.to_excel(escritor, index=False, sheet_name="Relatorio")
    st.download_button("Baixar em Excel", memoria.getvalue(),
                       file_name=nome_do_arquivo,
                       mime="application/vnd.openxmlformats-officedocument."
                            "spreadsheetml.sheet",
                       icon=":material/download:", key=chave,
                       help="No arquivo os valores vao como numero, para "
                            "poderem ser somados e ordenados no Excel.")


def mostrar(tabela, nome_do_arquivo, chave, larguras=None, altura=620,
            cores_por_linha=None):
    """Desenha a tabela na tela (st.dataframe) e oferece o Excel dela.

    cores_por_linha: lista de estilos CSS, um por linha — e o que pinta as
    faixas A, B e C da curva ABC.
    """
    colunas = {"Descricao": st.column_config.TextColumn(width="large")}
    colunas.update(larguras or {})
    na_tela = para_a_tela(tabela)

    if cores_por_linha is not None:
        pintura = pd.DataFrame([[cor] * len(na_tela.columns) for cor in cores_por_linha],
                               index=na_tela.index, columns=na_tela.columns)
        na_tela = na_tela.style.apply(lambda _: pintura, axis=None)

    st.dataframe(na_tela, hide_index=True, height=altura, column_config=colunas)
    baixar_excel(tabela, nome_do_arquivo, chave)


def cabecalho(orcamento):
    """A faixa de procedencia que todo relatorio carrega.

    E o que torna o numero defensavel: de qual banco, de que mes, de que
    praca, com que BDI e a partir de qual quantitativo.
    """
    procedencia = orcamento["procedencia"]
    bancos = " · ".join(
        f"{b['banco']} {b['referencia']} · {b['uf']} · {b['regime'].lower()}"
        for b in procedencia["bancos"].values())
    bdi = procedencia["bdi"]
    st.caption(
        f"**Obra WEZIG** · {bancos} · BDI "
        + (formatar_porcentagem(bdi) if bdi else "nao aplicado")
        + f"  \nQuantitativo {procedencia['quantitativo']['arquivo']} · "
          f"orcamento gerado em {procedencia['gerado_em']}  \n"
          "Os relatorios mostram o orcamento inteiro; os filtros da barra "
          "lateral valem so para a aba Auditoria.")


# =============================================================
# SINTETICO — a planilha orcamentaria, na ordem da EAP
# =============================================================
COLUNAS_DO_SINTETICO = [
    {"nome": "Item", "largura": "7rem"},
    {"nome": "Descricao", "largura": "minmax(0, 1fr)"},
    {"nome": "Codigo", "largura": "5rem"},
    {"nome": "Banco", "largura": "4.5rem"},
    {"nome": "Und", "largura": "3rem"},
    {"nome": "Quant.", "largura": "7rem", "alinhar": "direita"},
    {"nome": "Valor unit.", "largura": "7.5rem", "alinhar": "direita"},
    {"nome": "Total", "largura": "8.5rem", "alinhar": "direita"},
    {"nome": "Peso", "largura": "5rem", "alinhar": "direita"},
    {"nome": "Situacao", "largura": "8.5rem"},
]


def montar_sintetico(orcamento):
    """Uma linha por nivel da EAP e por servico, com o custo somado.

    O nivel de uma linha sai do tamanho da REFERENCIA (3 digitos por
    nivel), a mesma regra que a EAP usa desde a etapa 1.
    """
    somas = {}      # id do nivel -> custo
    nomes = {}      # id do nivel -> texto
    for linha in orcamento["linhas"]:
        ref = linha["referencia"]
        for id_do_nivel, texto in ((ref[:-9], linha["macro"]),
                                   (ref[:-6], linha["grupo"]),
                                   (ref[:-3], linha["item"])):
            nomes[id_do_nivel] = texto
            somas[id_do_nivel] = somas.get(id_do_nivel, 0.0) + (linha["custo_total"] or 0)

    custo_direto = orcamento["resumo"]["custo_direto"]
    ordenadas = sorted(orcamento["linhas"],
                       key=lambda l: (len(l["referencia"]), l["referencia"]))

    linhas_do_relatorio = []
    ja_saiu = set()
    for linha in ordenadas:
        ref = linha["referencia"]
        for id_do_nivel in (ref[:-9], ref[:-6], ref[:-3]):
            if id_do_nivel in ja_saiu:
                continue
            ja_saiu.add(id_do_nivel)
            linhas_do_relatorio.append({
                "Item": id_do_nivel,
                "Descricao": nomes[id_do_nivel],
                "Codigo": "",
                "Banco": "",
                "Und": "",
                "Quant.": None,
                "Valor unit.": None,
                "Total": somas[id_do_nivel] or None,
                "Peso": (somas[id_do_nivel] / custo_direto) if custo_direto else None,
                "Situacao": "",
            })
        linhas_do_relatorio.append({
            "Item": ref,
            "Descricao": linha["descricao"],
            "Codigo": linha["codigo"],
            "Banco": linha["banco"],
            "Und": linha["unidade"],
            "Quant.": linha["quantidade"],
            "Valor unit.": linha["custo_unitario"],
            "Total": linha["custo_total"],
            "Peso": linha["peso"],
            "Situacao": linha["status"],
        })
    return pd.DataFrame(linhas_do_relatorio)


def nos_do_sintetico(na_tela):
    """Transforma as linhas do sintetico em nos de arvore.

    O nivel vem do tamanho da REFERENCIA: 3 digitos por nivel. Assim o
    macro "20" (2 digitos) e nivel 1, e "20004001001" e nivel 4.
    """
    nos = []
    for _, linha in na_tela.iterrows():
        referencia = str(linha["Item"])
        nivel = -(-len(referencia) // 3)          # divisao arredondada para cima
        nos.append({
            "id": referencia,
            "pai": referencia[:-3] if nivel > 1 else None,
            "nivel": nivel,
            "folha": nivel == 4,
            "celulas": [linha[coluna["nome"]] for coluna in COLUNAS_DO_SINTETICO],
            # o que nao tem preco aparece marcado, nunca como vazio qualquer
            "classes": ({"Situacao": "destaque"}
                        if linha["Situacao"] in ("SEM PRECO", "BANCO A DEFINIR") else {}),
        })
    return nos


def aba_sintetico(orcamento):
    st.subheader("Orcamento sintetico", anchor=False)
    cabecalho(orcamento)
    st.caption("Na ordem da EAP. Cada nivel abre e fecha; o valor do nivel "
               "e a soma dos filhos.")
    tabela = montar_sintetico(orcamento)
    arvore_tabela(COLUNAS_DO_SINTETICO, nos_do_sintetico(para_a_tela(tabela)),
                  altura=620, abrir_ate=1, key="arvore_sintetico")
    baixar_excel(tabela, "WEZIG orcamento sintetico.xlsx", "baixar_sintetico")


# =============================================================
# ANALITICO — a EAP inteira, com cada composicao aberta
# =============================================================
#
# Cinco niveis: macro-servico > grupo > item > servico > itens da
# composicao. E a mesma estrutura do Sintetico, descendo um nivel a mais.
#
# A mesma composicao aparece em varias linhas da EAP (uma por pavimento),
# e aqui ela se repete mesmo — e assim que o relatorio analitico e lido:
# item por item do orcamento, e nao por catalogo de composicoes.
#
# ATENCAO AO QUE "TOTAL" SIGNIFICA EM CADA NIVEL
#   nos niveis da EAP  o custo do ramo inteiro
#   na linha de servico o custo total (quantidade x custo unitario)
#   nos itens          o custo do item POR UNIDADE do servico, que e como
#                      a composicao e publicada. Somando os itens de um
#                      servico chega-se ao custo unitario dele, nao ao total.
# =============================================================
# Sao onze colunas num espaco so. Duas regras de equilibrio:
#   - a descricao tem largura MINIMA, senao vira "CANTEIRO DE O...";
#   - as demais sao as mais estreitas possiveis, para as colunas de
#     dinheiro caberem na tela sem rolar para o lado.
# O nome inteiro do servico aparece ao passar o mouse, e a aba Auditoria
# mostra a descricao completa de qualquer jeito.
COLUNAS_DO_ANALITICO = [
    {"nome": "Item", "largura": "6rem"},
    {"nome": "Descricao", "largura": "minmax(15rem, 1fr)"},
    {"nome": "Tipo", "largura": "6rem"},
    {"nome": "Codigo", "largura": "5rem"},
    {"nome": "Banco", "largura": "4rem"},
    {"nome": "Und", "largura": "3rem"},
    {"nome": "Quant.", "largura": "5.5rem", "alinhar": "direita"},
    {"nome": "Coef.", "largura": "4.5rem", "alinhar": "direita"},
    {"nome": "Valor unit.", "largura": "6.5rem", "alinhar": "direita"},
    {"nome": "Total", "largura": "7rem", "alinhar": "direita"},
    {"nome": "Preco de", "largura": "6.5rem"},
]


def montar_analitico(orcamento):
    """Devolve (tabela, estrutura).

    A tabela vai para a tela e para o Excel. A estrutura diz, para cada
    linha da tabela, onde ela fica na arvore (id, pai, nivel, folha) —
    as duas nascem juntas para nao terem como sair de sincronia.
    """
    somas, nomes = {}, {}
    for linha in orcamento["linhas"]:
        ref = linha["referencia"]
        for id_do_nivel, texto in ((ref[:-9], linha["macro"]),
                                   (ref[:-6], linha["grupo"]),
                                   (ref[:-3], linha["item"])):
            nomes[id_do_nivel] = texto
            somas[id_do_nivel] = somas.get(id_do_nivel, 0.0) + (linha["custo_total"] or 0)

    ordenadas = sorted(orcamento["linhas"],
                       key=lambda l: (len(l["referencia"]), l["referencia"]))

    linhas_do_relatorio, estrutura = [], []
    ja_saiu = set()
    for linha in ordenadas:
        ref = linha["referencia"]

        # ---- os niveis da EAP, quando aparecem pela primeira vez ----
        for id_do_nivel in (ref[:-9], ref[:-6], ref[:-3]):
            if id_do_nivel in ja_saiu:
                continue
            ja_saiu.add(id_do_nivel)
            nivel = -(-len(id_do_nivel) // 3)      # 3 digitos por nivel
            linhas_do_relatorio.append({
                "Item": id_do_nivel, "Descricao": nomes[id_do_nivel], "Tipo": "",
                "Codigo": "", "Banco": "", "Und": "", "Quant.": None,
                "Coef.": None, "Valor unit.": None,
                "Total": somas[id_do_nivel] or None, "Preco de": "",
            })
            estrutura.append({"id": id_do_nivel,
                              "pai": id_do_nivel[:-3] if nivel > 1 else None,
                              "nivel": nivel, "folha": False})

        # ---- a linha de servico ----
        analitica = orcamento["analiticas"].get(f"{linha['banco']}/{linha['codigo']}")
        tem_itens = bool(analitica and analitica["custo_unitario"] is not None)
        linhas_do_relatorio.append({
            "Item": ref, "Descricao": linha["descricao"], "Tipo": "Servico",
            "Codigo": linha["codigo"], "Banco": linha["banco"],
            "Und": linha["unidade"], "Quant.": linha["quantidade"],
            "Coef.": None, "Valor unit.": linha["custo_unitario"],
            "Total": linha["custo_total"],
            "Preco de": linha["origem_do_preco"] or linha["status"],
        })
        estrutura.append({"id": ref, "pai": ref[:-3], "nivel": 4,
                          "folha": not tem_itens})
        if not tem_itens:
            continue

        # ---- os itens da composicao ----
        for posicao, item in enumerate(analitica["itens"]):
            linhas_do_relatorio.append({
                "Item": "", "Descricao": item["descricao"],
                "Tipo": "› " + item["tipo"].capitalize(),
                "Codigo": item["codigo"], "Banco": item["banco"],
                "Und": item["unidade"], "Quant.": None,
                "Coef.": item["coeficiente"], "Valor unit.": item["custo_unitario"],
                "Total": item["total"],
                "Preco de": item["origem_do_custo"] or "SEM PRECO",
            })
            estrutura.append({"id": f"{ref}#{posicao}", "pai": ref,
                              "nivel": 5, "folha": True})

    return pd.DataFrame(linhas_do_relatorio), estrutura


def nos_do_analitico(na_tela, estrutura):
    """Junta a estrutura da arvore com as celulas ja formatadas."""
    nos = []
    for posicao_na_arvore, (_, linha) in zip(estrutura, na_tela.iterrows()):
        no = dict(posicao_na_arvore)
        no["celulas"] = [linha[coluna["nome"]] for coluna in COLUNAS_DO_ANALITICO]
        no["classes"] = ({"Preco de": "destaque"}
                         if linha["Preco de"] in ("SEM PRECO", "BANCO A DEFINIR")
                         else {})
        nos.append(no)
    return nos


def aba_analitico(orcamento):
    st.subheader("Composicoes analiticas com preco unitario", anchor=False)
    cabecalho(orcamento)
    tabela, estrutura = montar_analitico(orcamento)
    servicos = sum(1 for e in estrutura if e["nivel"] == 4)
    st.caption(
        f"A EAP inteira — {servicos} servicos — com cada composicao abrindo nos "
        "seus itens. 'Preco de' diz de onde veio o preco: PRECO = insumo coletado "
        "pelo SINAPI, COTACAO = preco nosso, CALCULADO = somado dos insumos, "
        "PUBLICADO = galho que o SINAPI so divulga pronto.  \n"
        "**Atencao ao Total:** nos niveis da EAP e o custo do ramo; na linha de "
        "servico e quantidade x custo unitario; nos itens e o custo POR UNIDADE "
        "do servico — somando os itens chega-se ao custo unitario, nao ao total.")
    arvore_tabela(COLUNAS_DO_ANALITICO,
                  nos_do_analitico(para_a_tela(tabela), estrutura),
                  altura=620, abrir_ate=0, key="arvore_analitico")
    baixar_excel(tabela, "WEZIG composicoes analiticas.xlsx", "baixar_analitico")


# =============================================================
# CURVA ABC DE INSUMOS — o que a obra consome
# =============================================================
def montar_abc_insumos(orcamento):
    custo_direto = orcamento["resumo"]["custo_direto"]
    linhas_do_relatorio = []
    acumulado = 0.0
    for insumo in orcamento["insumos"]:      # ja vem do maior para o menor
        antes = (acumulado / custo_direto) if custo_direto else 0
        acumulado += insumo["total"]
        linhas_do_relatorio.append({
            "Faixa": faixa_abc(antes),
            "Codigo": insumo["codigo"],
            "Banco": insumo["banco"],
            "Descricao": insumo["descricao"],
            "Tipo": insumo["classe"] or "—",
            "Und": insumo["unidade"],
            "Quantidade": insumo["quantidade"],
            "Valor unit.": insumo["preco_unitario"],
            "Total": insumo["total"],
            "Peso": (insumo["total"] / custo_direto) if custo_direto else None,
            "Peso acumulado": (acumulado / custo_direto) if custo_direto else None,
        })
    return pd.DataFrame(linhas_do_relatorio)


def legenda_das_faixas(tabela):
    """A linha de texto que explica as cores, com a contagem de cada faixa."""
    contagem = tabela["Faixa"].value_counts()
    total = len(tabela)
    partes = []
    for letra, ate in (("A", f"ate {formatar_porcentagem(CORTE_DA_FAIXA_A)}"),
                       ("B", f"ate {formatar_porcentagem(CORTE_DA_FAIXA_B)}"),
                       ("C", "o resto")):
        quantos = int(contagem.get(letra, 0))
        partes.append(f"**{letra}** {quantos} itens ({quantos / total:.0%}) · {ate}")
    return " · ".join(partes)


def aba_abc_insumos(orcamento):
    st.subheader("Curva ABC de insumos", anchor=False)
    cabecalho(orcamento)
    custo_direto = orcamento["resumo"]["custo_direto"]
    fechadas = [i for i in orcamento["insumos"] if i["tipo"] == "COMPOSICAO"]
    if fechadas:
        peso = sum(i["total"] for i in fechadas) / custo_direto if custo_direto else 0
        st.warning(
            f"{len(fechadas)} itens desta lista ainda sao COMPOSICOES fechadas, "
            f"e nao insumos — {formatar_porcentagem(peso)} do custo direto. "
            "Sao composicoes que nao podem ser abertas porque falta o preco de "
            "algum insumo na praca. Cotar esses insumos "
            "(5 ORCAMENTO, pasta 1 PARAMETROS, arquivo cotacoes.py) abre a lista.",
            icon=":material/lock:")
    tabela = montar_abc_insumos(orcamento)
    st.caption(legenda_das_faixas(tabela))
    mostrar(tabela, "WEZIG curva ABC de insumos.xlsx", "baixar_abc_insumos",
            {"Faixa": st.column_config.TextColumn(width=60),
             "Quantidade": st.column_config.TextColumn(width=130)},
            cores_por_linha=[COR_DA_FAIXA[f] for f in tabela["Faixa"]])


# =============================================================
# CURVA ABC DE SERVICOS — os servicos, do maior gasto para o menor
# =============================================================
def montar_abc_servicos(orcamento):
    """Junta as linhas do mesmo servico.

    A mesma composicao aparece varias vezes na EAP, uma por pavimento.
    Na curva ABC ela e UMA so: quantidade somada e custo somado. Sem isso
    a curva mostraria treze linhas de armacao em vez de uma.
    """
    juntos = {}
    for linha in orcamento["linhas"]:
        if not linha["custo_total"]:
            continue
        chave = (linha["banco"], linha["codigo"])
        registro = juntos.setdefault(chave, {
            "banco": linha["banco"], "codigo": linha["codigo"],
            "descricao": linha["descricao"], "unidade": linha["unidade"],
            "custo_unitario": linha["custo_unitario"],
            "origem_do_preco": linha["origem_do_preco"],
            "quantidade": 0.0, "total": 0.0, "linhas": 0,
        })
        registro["quantidade"] += linha["quantidade"]
        registro["total"] += linha["custo_total"]
        registro["linhas"] += 1

    custo_direto = orcamento["resumo"]["custo_direto"]
    linhas_do_relatorio = []
    acumulado = 0.0
    for servico in sorted(juntos.values(), key=lambda s: -s["total"]):
        antes = (acumulado / custo_direto) if custo_direto else 0
        acumulado += servico["total"]
        linhas_do_relatorio.append({
            "Faixa": faixa_abc(antes),
            "Codigo": servico["codigo"],
            "Banco": servico["banco"],
            "Descricao": servico["descricao"],
            "Und": servico["unidade"],
            "Quant.": servico["quantidade"],
            "Linhas na EAP": servico["linhas"],
            "Valor unit.": servico["custo_unitario"],
            "Total": servico["total"],
            "Preco de": servico["origem_do_preco"],
            "Peso": (servico["total"] / custo_direto) if custo_direto else None,
            "Peso acumulado": (acumulado / custo_direto) if custo_direto else None,
        })
    return pd.DataFrame(linhas_do_relatorio)


def aba_abc_servicos(orcamento):
    st.subheader("Curva ABC de servicos", anchor=False)
    cabecalho(orcamento)
    st.caption("Uma linha por composicao: as varias linhas da EAP do mesmo "
               "servico (uma por pavimento) entram somadas. 'Linhas na EAP' "
               "diz quantas foram juntadas.")
    tabela = montar_abc_servicos(orcamento)
    st.caption(legenda_das_faixas(tabela))
    mostrar(tabela, "WEZIG curva ABC de servicos.xlsx", "baixar_abc_servicos",
            {"Faixa": st.column_config.TextColumn(width=60),
             "Quant.": st.column_config.TextColumn(width=120),
             "Linhas na EAP": st.column_config.NumberColumn(format="%d")},
            cores_por_linha=[COR_DA_FAIXA[f] for f in tabela["Faixa"]])


# =============================================================
# RESUMO — o total por macro-servico e o que falta
# =============================================================
def montar_resumo(orcamento):
    somas = {}
    for linha in orcamento["linhas"]:
        chave = (linha["referencia"][:-9], linha["macro"])
        somas[chave] = somas.get(chave, 0.0) + (linha["custo_total"] or 0)
    custo_direto = orcamento["resumo"]["custo_direto"]
    return pd.DataFrame([{
        "Item": id_do_macro,
        "Macro-servico": nome,
        "Total": valor or None,
        "Peso": (valor / custo_direto) if custo_direto else None,
    } for (id_do_macro, nome), valor in sorted(
        somas.items(), key=lambda x: (len(x[0][0]), x[0][0]))])


def aba_resumo(orcamento):
    st.subheader("Resumo do orcamento", anchor=False)
    cabecalho(orcamento)
    resumo = orcamento["resumo"]
    conferencia = orcamento["conferencia"]

    with st.container(horizontal=True):
        st.metric("Custo direto", formatar_reais(resumo["custo_direto"]))
        if resumo["bdi"]:
            st.metric(f"BDI {formatar_porcentagem(resumo['bdi'])}",
                      formatar_reais(resumo["total"] - resumo["custo_direto"]))
            st.metric("Total", formatar_reais(resumo["total"]))
        st.metric("Servicos orcados", resumo["por_status"].get("ORCADO", 0))
        st.metric("Insumos distintos", resumo["insumos_distintos"])

    mostrar(montar_resumo(orcamento), "WEZIG resumo do orcamento.xlsx",
            "baixar_resumo",
            {"Macro-servico": st.column_config.TextColumn(width="large")},
            altura="content")

    # ---- o que ainda nao entrou ----
    st.subheader("O que ainda nao entrou no total", anchor=False)
    st.caption("Nada disso foi somado como zero: cada caso aparece nomeado.")
    with st.container(horizontal=True):
        st.metric("Sem quantidade", conferencia["linhas_sem_quantidade"],
                  help="Tem preco, falta medir nos modelos (etapa 4)")
        st.metric("Sem preco", len(conferencia["linhas_sem_preco"]),
                  help="Tem quantidade, falta o preco de algum insumo")
        st.metric("Banco a definir", len(conferencia["linhas_banco_a_definir"]),
                  help="A linha ainda nao tem composicao escolhida (etapa 3)")

    if conferencia["insumos_a_cotar"]:
        st.markdown("**Insumos a cotar** — cada um destes derruba o preco dos "
                    "servicos listados ao lado:")
        st.dataframe(
            pd.DataFrame([{
                "Codigo": insumo["codigo"],
                "Banco": insumo["banco"],
                "Descricao": insumo["descricao"],
                "Classe": insumo["classe"] or "—",
                "Servicos": len(insumo["servicos"]),
                "Quais": ", ".join(insumo["servicos"]),
            } for insumo in conferencia["insumos_a_cotar"]]),
            hide_index=True,
            column_config={"Descricao": st.column_config.TextColumn(width="large")})

    # ---- a conferencia da conta ----
    pelas_linhas = formatar_reais(conferencia["custo_direto_pelas_linhas"])
    if conferencia["fecha"]:
        st.success(f"Conferencia: somando os servicos da {pelas_linhas}, e somando "
                   "os insumos da o mesmo. A expansao ate o insumo esta certa.",
                   icon=":material/check_circle:")
    else:
        st.error(
            f"Conferencia: somando os servicos da {pelas_linhas}, mas somando os "
            f"insumos da {formatar_reais(conferencia['custo_direto_pelos_insumos'])} "
            f"(diferenca de {formatar_reais(conferencia['diferenca'])}). "
            "Ha galho perdido na expansao.",
            icon=":material/error:")
