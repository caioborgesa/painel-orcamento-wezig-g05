# =============================================================
# PAINEL DO ORCAMENTO — quantitativo, custo e relatorios
# =============================================================
#
# O QUE ESTE APP FAZ
#   Junta numa tela so as duas metades do orcamento:
#     QUANTO TEM   o quantitativo mais recente da etapa 4, tirado dos IFC
#     QUANTO CUSTA o orcamento mais recente da etapa 5, calculado do insumo
#
#   Ele nao calcula nada: le os dois JSON ja carimbados e mostra. Assim o
#   que aparece na tela e exatamente o que esta gravado em disco.
#
#   Sao seis abas:
#     Auditoria        conferir cada linha contra o modelo 3D
#     Sintetico        a planilha orcamentaria, na ordem da EAP
#     Analitico        cada composicao aberta item a item
#     ABC de insumos   o que a obra consome, do maior gasto para o menor
#     ABC de servicos  os servicos, do maior gasto para o menor
#     Resumo           total por macro-servico e o que ainda falta
#
#   Na aba Auditoria da para:
#     - quais modelos IFC foram a base da extracao, e se ha versao mais nova
#     - a EAP em arvore (abre e fecha os niveis), com filtros
#     - o criterio, a memoria e o valor de cada elemento
#     - o 3D de todos os modelos medidos (os mesmos IFC da extracao),
#       com os elementos da linha ou do ramo em destaque
#     - clicando num elemento: em quais linhas ele entrou
#     - o botao "Marcar como verificado"
#
# COMO ABRIR
#   Dois cliques em "ABRIR PAINEL DO ORCAMENTO.bat" (pasta 06 ORCAMENTO)
#
# POR QUE ELE MORA AQUI, E NAO DENTRO DE UMA ETAPA
#   O painel atravessa as etapas 4 (quantidade) e 5 (custo). Enterrado
#   dentro de uma delas, viraria de novo o problema de "onde esta isso?".
#
# O app so LE os dois JSON. O unico arquivo que ele grava e o
# "verificacoes WEZIG.json".
#
# VERSAO ONLINE (config.MODO_ONLINE)
#   O mesmo app roda publicado na internet, so para consulta. La nao ha
#   IFC nem 02 RECEBIDO CDE: o 3D usa as malhas publicadas, a situacao dos
#   modelos nao e conferida e nao da para marcar verificacao (as ja feitas
#   no computador local aparecem normalmente).
# =============================================================

import json
import sys
from pathlib import Path, PureWindowsPath

import pandas as pd
import streamlit as st

# O painel mora em 06 ORCAMENTO\\PAINEL. O config.py, o verificacoes.py e
# o ler_modelos.py sao da etapa 4 e continuam la — este e o caminho ate eles.
PASTA_PAINEL = Path(__file__).resolve().parent
PASTA_ORCAMENTO = PASTA_PAINEL.parent
sys.path.insert(0, str(PASTA_ORCAMENTO / "4 QUANTITATIVOS" / "SCRIPTS"))
sys.path.insert(0, str(PASTA_PAINEL))

import config  # noqa: E402
import verificacoes  # noqa: E402
if not config.MODO_ONLINE:
    # o ler_modelos traz o ifcopenshell, que o servidor online nao instala
    from ler_modelos import data_do_arquivo  # noqa: E402
from preparar_malhas import preparar_malha  # noqa: E402
from arvore_eap import arvore_eap  # noqa: E402
from formatos import formatar_numero, formatar_reais, reais_no_texto  # noqa: E402
import relatorios  # noqa: E402
from visor_3d import visor_3d  # noqa: E402

st.set_page_config(
    page_title="Painel do orcamento",
    page_icon=":material/view_in_ar:",
    layout="wide",
)


# =============================================================
# 1. LEITURA DOS DADOS (guardada em cache: so rele se o arquivo mudar)
# =============================================================
def quantitativo_mais_recente():
    """O JSON oficial de carimbo mais recente (o carimbo ordena pelo nome)."""
    arquivos = sorted(config.PASTA_SAIDA.glob("quantitativos WEZIG *.json"))
    return arquivos[-1] if arquivos else None


@st.cache_data(max_entries=5)
def carregar_quantitativos(caminho, modificado_em):
    # 'modificado_em' entra so para o cache saber quando reler
    with open(caminho, encoding="utf-8") as arquivo:
        return json.load(arquivo)


def orcamento_mais_recente():
    """O orcamento de carimbo mais recente (etapa 5), se ja houver um.

    O painel funciona sem ele: a coluna de custo simplesmente nao aparece.
    """
    arquivos = sorted(config.PASTA_ORCAMENTO_RESULTADOS.glob("orcamento WEZIG *.json"))
    return arquivos[-1] if arquivos else None


@st.cache_data(max_entries=5)
def carregar_orcamento(caminho, modificado_em):
    with open(caminho, encoding="utf-8") as arquivo:
        return json.load(arquivo)


@st.cache_data(max_entries=5)
def indice_de_elementos(caminho, modificado_em):
    """{GlobalId: [linhas em que o elemento entrou]} — para o clique no 3D."""
    dados = carregar_quantitativos(caminho, modificado_em)
    indice = {}
    for linha in dados["linhas"]:
        for c in linha["contribuicoes"]:
            if c["global_id"]:
                indice.setdefault(c["global_id"], []).append({
                    "referencia": linha["referencia"],
                    "codigo": linha["codigo"],
                    "descricao": linha["descricao"],
                    "valor": c["valor"],
                    "unidade": linha["unidade"],
                })
    return indice


@st.cache_resource(max_entries=10)
def malha_do_modelo(nome_do_modelo, caminho_do_ifc, versao_do_ifc):
    # 'versao_do_ifc' entra so para o cache refazer quando o IFC mudar
    return preparar_malha(nome_do_modelo, caminho_do_ifc)


# =============================================================
# MODELOS BASE: qual IFC foi medido, e se ja existe um mais novo
# =============================================================
def caminho_registrado(info):
    """Caminho completo do IFC registrado no quantitativo."""
    return config.PASTA_TFM / info["caminho"]


def formatar_data(texto):
    """'2026-09-13 064649' -> '13/09/2026 06:46'."""
    if not texto:
        return "—"
    return f"{texto[8:10]}/{texto[5:7]}/{texto[0:4]} {texto[11:13]}:{texto[13:15]}"


@st.cache_data(ttl=60)
def ifc_mais_novos(caminho, modificado_em):
    """IFC do mesmo modelo com data mais nova que a do arquivo medido.

    "Mesmo modelo" = nome comecando pelo mesmo codigo (ex.:
    "CRZ-CBE-ZZZ-ZZZ-M3-EST-0001"). Procura na pasta do proprio IFC e em
    todo o 02 RECEBIDO CDE, fora dos _ARQUIVO.
    """
    caminho = Path(caminho)
    codigo = caminho.stem.split(" ")[0].lower()
    candidatos = set(caminho.parent.glob("*")) | set(config.PASTA_CDE.rglob("*"))
    mais_novos = []
    for outro in candidatos:
        if (outro.suffix.lower() != ".ifc" or outro == caminho
                or "_ARQUIVO" in outro.parts
                or not outro.stem.lower().startswith(codigo)):
            continue
        data = data_do_arquivo(outro)
        if data > modificado_em:
            mais_novos.append({"arquivo": outro.name,
                               "pasta": str(outro.parent.relative_to(config.PASTA_TFM)),
                               "data": data})
    return sorted(mais_novos, key=lambda item: item["data"], reverse=True)


def situacao_do_modelo(nome, info):
    """(icone, texto) dizendo se o IFC medido ainda e o que vale."""
    if not info.get("aberto_nesta_rodada"):
        return "➖", "nao medido nesta geracao"
    if config.MODO_ONLINE:
        return "🌐", "versao online: a conferencia do IFC e feita no computador local"
    if "caminho" not in info:
        return "⚠️", "quantitativo antigo, sem o caminho do IFC: gerar de novo"
    caminho = caminho_registrado(info)
    if not caminho.exists():
        return "❌", "o IFC medido nao existe mais neste caminho"
    if data_do_arquivo(caminho) != info["modificado_em"]:
        return "⚠️", "o IFC foi alterado depois da geracao: gerar de novo"
    if config.MODELOS[nome] != caminho:
        return "⚠️", f"o config.py agora aponta para {config.MODELOS[nome].name}: gerar de novo"
    novos = ifc_mais_novos(str(caminho), info["modificado_em"])
    if novos:
        return "⚠️", (f"ha versao mais nova: {novos[0]['arquivo']} "
                      f"({formatar_data(novos[0]['data'])}, em {novos[0]['pasta']})")
    return "✅", "e o IFC mais recente encontrado"


# =============================================================
# 2. ESTADO DA TELA E CALLBACKS
# =============================================================
st.session_state.setdefault("elemento_selecionado", None)
st.session_state.setdefault("escolha", None)  # {"tipo": "linha" ou "ramo", "id": REFERENCIA}


def ao_clicar_na_arvore():
    clicado = st.session_state["arvore_eap"].clicado
    if not clicado:
        return
    # tipo "nenhum" = o usuario desmarcou (clicou de novo ou usou "Limpar escolha")
    st.session_state["escolha"] = None if clicado["tipo"] == "nenhum" else clicado
    st.session_state["elemento_selecionado"] = None


def ao_clicar_no_3d():
    clicado = st.session_state["visor_3d"].elemento_clicado
    if clicado:
        st.session_state["elemento_selecionado"] = clicado


def ao_escolher_contribuicao():
    escolhidas = st.session_state["tabela_contribuicoes"].selection.rows
    ids = st.session_state.get("_ids_das_contribuicoes", [])
    if escolhidas and escolhidas[0] < len(ids) and ids[escolhidas[0]]:
        st.session_state["elemento_selecionado"] = ids[escolhidas[0]]


def ao_escolher_servico_do_elemento():
    """Escolher um servico na lista do elemento leva a auditoria ate ele.

    E o caminho inverso do normal: em vez de partir do servico e ver as
    pecas, parte-se da peca ("por que este pilar custa isso?") e vai-se
    ao servico. O elemento continua selecionado no 3D.
    """
    escolhidas = st.session_state["tabela_do_elemento"].selection.rows
    referencias = st.session_state.get("_referencias_do_elemento", [])
    if escolhidas and escolhidas[0] < len(referencias):
        st.session_state["escolha"] = {"tipo": "linha",
                                       "id": referencias[escolhidas[0]]}


def limpar_selecao():
    st.session_state["elemento_selecionado"] = None


# =============================================================
# 3. BARRA LATERAL: arquivo, filtros e conferencia
# =============================================================
arquivo_escolhido = quantitativo_mais_recente()
if arquivo_escolhido is None:
    st.warning("Nenhum quantitativo gerado ainda. Rode `python gerar_quantitativos.py`.")
    st.stop()

modificado_em = arquivo_escolhido.stat().st_mtime
dados = carregar_quantitativos(str(arquivo_escolhido), modificado_em)
procedencia = dados["procedencia"]

with st.sidebar:
    st.header("Painel do orcamento", anchor=False)
    st.caption(f"**{arquivo_escolhido.stem}**  \n"
               f"EAP: {procedencia['eap_servicos']['arquivo']}")

    # As verificacoes sao aplicadas na hora: marcar no app ja muda o status
    registros = verificacoes.ler_verificacoes()
    linhas = [dict(linha) for linha in dados["linhas"]]
    for linha in linhas:
        verificacoes.aplicar_verificacao(linha, registros)

    # ---- o custo vem do orcamento mais recente (etapa 5) ----
    # A ligacao entre as duas etapas e a REFERENCIA, a mesma chave que
    # liga a EAP as regras. O painel nao calcula nada: so junta.
    arquivo_do_orcamento = orcamento_mais_recente()
    orcamento = None
    if arquivo_do_orcamento:
        orcamento = carregar_orcamento(str(arquivo_do_orcamento),
                                       arquivo_do_orcamento.stat().st_mtime)
        orcada_por_referencia = {l["referencia"]: l for l in orcamento["linhas"]}
        for linha in linhas:
            orcada = orcada_por_referencia.get(linha["referencia"])
            if not orcada:
                continue
            for campo in ("custo_unitario", "custo_total", "custo_publicado",
                          "origem_do_preco", "uf", "regime", "referencia_do_banco"):
                linha[campo] = orcada[campo]
            linha["status_preco"] = orcada["status"]

        resumo_do_orcamento = orcamento["resumo"]
        st.metric("Custo direto", formatar_reais(resumo_do_orcamento["custo_direto"]))
        procedencia_do_banco = list(orcamento["procedencia"]["bancos"].values())[0]
        st.caption(
            f"{arquivo_do_orcamento.stem}  \n"
            f"{procedencia_do_banco['banco']} {procedencia_do_banco['referencia']} · "
            f"{procedencia_do_banco['uf']} · {procedencia_do_banco['regime'].lower()}  \n"
            f"{resumo_do_orcamento['por_status'].get('ORCADO', 0)} servicos orcados · "
            f"{resumo_do_orcamento['por_status'].get('SEM PRECO', 0)} sem preco · "
            f"{resumo_do_orcamento['por_status'].get('SEM QUANTIDADE', 0)} sem quantidade")
    else:
        st.warning("Sem orcamento gerado. Rode GERAR ORCAMENTO.bat para ver o custo.",
                   icon=":material/payments:")

    st.subheader("Filtros", anchor=False)
    origens = sorted({linha["origem"] for linha in linhas})
    # Sem origem escolhida = todas as origens
    origens_escolhidas = st.pills("Origem", origens, selection_mode="multi")
    todos_status = sorted({linha["status"] for linha in linhas})
    status_escolhidos = st.multiselect(
        "Status", todos_status,
        default=[s for s in todos_status if s != "SEM REGRA"])
    macros = sorted({linha["macro"] for linha in linhas})
    macro_escolhido = st.selectbox("Macro-servico", ["Todos"] + macros)
    # O mesmo filtro vale para a arvore e para o 3D
    pavimentos_escolhidos = st.pills("Pavimento (arvore e 3D)", config.PAVIMENTOS_DA_EAP,
                                     selection_mode="multi")
    busca = st.text_input("Buscar no codigo ou na descricao")

    st.subheader("Conferencia", anchor=False)
    conferencia = dados["conferencia"]
    st.table({
        "Linhas da EAP sem regra": len(conferencia["linhas_da_eap_sem_regra"]),
        "Regras desatualizadas": len(conferencia["regras_desatualizadas"]),
        "Elementos repetidos": len(conferencia.get("elementos_repetidos_no_mesmo_servico", [])),
        "Elementos sem regra": len(conferencia.get("elementos_sem_regra", [])),
    }, border="horizontal", width="content")
    mostrar_sem_regra = st.toggle("Destacar no 3D os elementos sem regra",
                                  disabled=not conferencia.get("elementos_sem_regra"))


# =============================================================
# 4. FILTRAR AS LINHAS
# =============================================================
def passa_nos_filtros(linha):
    if origens_escolhidas and linha["origem"] not in origens_escolhidas:
        return False
    if status_escolhidos and linha["status"] not in status_escolhidos:
        return False
    if macro_escolhido != "Todos" and linha["macro"] != macro_escolhido:
        return False
    if pavimentos_escolhidos and linha["pavimento"] not in pavimentos_escolhidos:
        return False
    if busca and busca.lower() not in (linha["codigo"] + " " + linha["descricao"]).lower():
        return False
    return True


linhas_filtradas = [linha for linha in linhas if passa_nos_filtros(linha)]


# =============================================================
# 5. TELA PRINCIPAL
# =============================================================
st.title("Painel do orcamento", anchor=False)
if config.MODO_ONLINE:
    # quem abre o link precisa saber de quando sao os dados
    carimbo_do_quantitativo = arquivo_escolhido.stem.split(" ", 2)[-1]
    texto_do_orcamento = (
        f" · orcamento de {formatar_data(arquivo_do_orcamento.stem.split(' ', 2)[-1])}"
        if arquivo_do_orcamento else "")
    st.caption(f":material/public: Versao de consulta · quantitativo de "
               f"{formatar_data(carimbo_do_quantitativo)}{texto_do_orcamento}")

abas = st.tabs(["Auditoria", "Sintetico", "Analitico", "ABC de insumos",
                "ABC de servicos", "Resumo"])

# Os relatorios sao desenhados ANTES da aba de auditoria de proposito: a
# auditoria tem um st.stop() para o caso de nenhum modelo ter sido medido,
# e o st.stop() pararia o app antes de os relatorios aparecerem.
for numero_da_aba, desenhar in enumerate(
        [relatorios.aba_sintetico, relatorios.aba_analitico,
         relatorios.aba_abc_insumos, relatorios.aba_abc_servicos,
         relatorios.aba_resumo], start=1):
    with abas[numero_da_aba]:
        if orcamento:
            desenhar(orcamento)
        else:
            st.info("Sem orcamento gerado ainda. Rode GERAR ORCAMENTO.bat "
                    "(pasta 5 ORCAMENTO) para ver custo e relatorios.",
                    icon=":material/payments:")

with abas[0]:
    # ---------------- modelos base deste quantitativo ----------------
    situacoes = {nome: situacao_do_modelo(nome, info)
                 for nome, info in procedencia["modelos"].items()}
    problemas = [nome for nome, (icone, _) in situacoes.items() if icone in ("⚠️", "❌")]
    with st.expander(
            "Modelos base deste quantitativo"
            + (f" · :orange[atencao em {', '.join(problemas)}]" if problemas else " · todos em dia"),
            icon=":material/deployed_code:", expanded=bool(problemas)):
        st.dataframe(
            pd.DataFrame([{
                "": situacoes[nome][0],
                "Modelo": nome,
                "Arquivo IFC": info["arquivo"],
                # o caminho foi gravado no Windows (com "\"); o PureWindowsPath
                # le certo tambem no servidor online, que e Linux
                "Pasta": str(PureWindowsPath(info["caminho"]).parent) if "caminho" in info else "—",
                "Data do arquivo": formatar_data(info.get("modificado_em")),
                "Elementos": info.get("elementos_lidos"),
                "Situacao": situacoes[nome][1],
            } for nome, info in procedencia["modelos"].items()]),
            hide_index=True,
            column_config={"": st.column_config.TextColumn(width=40),
                           "Elementos": st.column_config.NumberColumn(format="%d"),
                           "Situacao": st.column_config.TextColumn(width="large")},
        )
        if config.MODO_ONLINE:
            st.caption(f"Gerado em {formatar_data(procedencia['gerado_em'])} · "
                       "os IFC ficam no computador local e no CDE, nao nesta versao online.")
        else:
            st.caption(f"Gerado em {formatar_data(procedencia['gerado_em'])} · "
                       "a situacao compara o IFC medido com o config.py e com os IFC "
                       "da pasta do modelo e do 02 RECEBIDO CDE (fora dos _ARQUIVO).")

    # ---------------- arvore da EAP (largura toda) ----------------
    st.caption(f"{len(linhas_filtradas)} de {len(linhas)} linhas passam pelos filtros")
    escolha = st.session_state["escolha"]
    arvore_eap(linhas_filtradas, escolha["id"] if escolha else None,
               altura=440, ao_clicar=ao_clicar_na_arvore)


    def pertence_ao_ramo(linha, id_do_ramo):
        """A linha esta abaixo do ramo? (item, grupo ou macro-servico)

        Compara pelo pedaco da REFERENCIA, e nao por "comeca com": o macro
        "1" nao pode pegar as linhas do macro "11".
        """
        ref = linha["referencia"]
        return id_do_ramo in (ref[:-3], ref[:-6], ref[:-9])


    # O que esta escolhido: uma linha de servico ou um ramo inteiro
    linha, linhas_do_ramo = None, []
    if escolha and escolha["tipo"] == "linha":
        linha = next((l for l in linhas_filtradas if l["referencia"] == escolha["id"]), None)
    elif escolha and escolha["tipo"] == "ramo":
        linhas_do_ramo = [l for l in linhas_filtradas if pertence_ao_ramo(l, escolha["id"])]

    coluna_detalhe, coluna_3d = st.columns([5, 6], gap="medium")

    # ---------------- esquerda: detalhe ----------------
    with coluna_detalhe:
        if linha is None and not linhas_do_ramo:
            st.info("Escolha na arvore uma linha de servico (detalhe e elementos no 3D) "
                    "ou o nome de um nivel (todos os elementos do ramo no 3D).",
                    icon=":material/touch_app:")

        elif linhas_do_ramo:
            # ---- um ramo inteiro ----
            exemplo = linhas_do_ramo[0]
            ref = exemplo["referencia"]
            caminho = {ref[:-9]: [exemplo["macro"]],
                       ref[:-6]: [exemplo["macro"], exemplo["grupo"]],
                       ref[:-3]: [exemplo["macro"], exemplo["grupo"], exemplo["item"]]}[escolha["id"]]
            com_medida = [l for l in linhas_do_ramo if l["quantidade"] is not None]
            with st.container(border=True):
                st.markdown(f"**{escolha['id']}** · " + " › ".join(caminho))
                custo_do_ramo = sum(l.get("custo_total") or 0 for l in linhas_do_ramo)
                sem_preco_no_ramo = sum(1 for l in linhas_do_ramo
                                        if l.get("status_preco") == "SEM PRECO")
                with st.container(horizontal=True):
                    st.metric("Linhas", len(linhas_do_ramo))
                    st.metric("Com quantidade", len(com_medida))
                    st.metric("Elementos", len({c["global_id"] for l in linhas_do_ramo
                                                for c in l["contribuicoes"] if c["global_id"]}))
                    st.metric("Custo do ramo", formatar_reais(custo_do_ramo),
                              delta=(f"{sem_preco_no_ramo} sem preco" if sem_preco_no_ramo else None),
                              delta_color="inverse")
                st.caption("O 3D destaca os elementos de todas as linhas deste ramo. "
                           "Para ver o detalhe de uma linha, escolha-a na arvore.")
            # (a tabela do ramo fica embaixo, na largura toda)

        else:
            # ---- uma linha de servico ----
            with st.container(border=True):
                st.markdown(f"**{linha['referencia']}** · {linha['macro']} › "
                            f"{linha['grupo']} › {linha['item']}")
                st.markdown(f"`{linha['codigo']}` {linha['descricao']}")
                with st.container(horizontal=True):
                    quantidade = ("—" if linha["quantidade"] is None
                                  else f"{formatar_numero(linha['quantidade'])} {linha['unidade']}")
                    st.metric("Quantidade", quantidade)
                    st.metric("Status", linha["status"])
                    st.metric("Elementos", len(linha["contribuicoes"]))
                st.caption(f"Origem: {linha['origem']}")

                # ---- o custo desta linha (etapa 5) ----
                if linha.get("status_preco"):
                    with st.container(horizontal=True):
                        st.metric("Custo unitario",
                                  formatar_reais(linha.get("custo_unitario")))
                        st.metric("Custo total", formatar_reais(linha.get("custo_total")))
                        st.metric("Preco", linha.get("origem_do_preco")
                                  or linha["status_preco"])
                    if linha["status_preco"] == "SEM PRECO":
                        st.caption(":red[Sem preco: falta a coleta de algum insumo. "
                                   "Ver a pauta em 5 ORCAMENTO\\1 PARAMETROS\\cotacoes.py]")
                    elif linha["status_preco"] == "BANCO A DEFINIR":
                        st.caption(":red[Esta linha ainda nao tem composicao definida "
                                   "(BANCO = A DEFINIR na etapa 3)]")
                    else:
                        st.caption(f"{linha['banco']} {linha.get('referencia_do_banco')} · "
                                   f"{linha.get('uf')} · "
                                   f"{str(linha.get('regime') or '').lower()}")
                st.markdown("**Criterio**")
                st.write(linha["criterio"] or "—")
                st.markdown("**Memoria de calculo**")
                st.caption(linha["memoria"] or "—")

            # (a tabela de contribuicoes fica embaixo, na largura toda)

            # (a composicao aberta fica embaixo, na largura toda)

            # ---- verificacao ----
            with st.container(border=True):
                registro = linha.get("verificacao")
                if registro and linha["status"] == "VERIFICADO":
                    st.success(f"Verificado em {registro['verificado_em']}"
                               + (f" — {registro['observacao']}" if registro["observacao"] else ""),
                               icon=":material/verified:")
                elif registro and linha["status"] == "DIVERGENTE":
                    st.warning(f"Verificado em {registro['verificado_em']} com "
                               f"{registro['quantidade']} {registro['unidade']}, mas agora a "
                               f"quantidade e {linha['quantidade']}. Conferir de novo.",
                               icon=":material/error:")

                if config.MODO_ONLINE:
                    # Online o disco do servidor e apagado a cada reinicio: uma
                    # verificacao gravada la se perderia. Marca-se so no local.
                    if not registro:
                        st.caption("Linha ainda nao verificada.")
                else:
                    observacao = st.text_input("Observacao da verificacao",
                                               key=f"observacao_{linha['referencia']}")
                    with st.container(horizontal=True):
                        if st.button("Marcar como verificado", icon=":material/check_circle:",
                                     type="primary", disabled=linha["quantidade"] is None):
                            verificacoes.gravar_verificacao(linha, observacao,
                                                            arquivo_escolhido.name)
                            st.rerun()
                        if registro and st.button("Remover verificacao", icon=":material/undo:"):
                            verificacoes.remover_verificacao(linha["referencia"])
                            st.rerun()

    # ---------------- direita: 3D e elemento ----------------
    with coluna_3d:
        # O 3D mostra JUNTOS todos os modelos medidos neste quantitativo,
        # cada um a partir do IFC registrado nele.
        modelos_medidos = [nome for nome, info in procedencia["modelos"].items()
                           if info.get("aberto_nesta_rodada")]

        if not modelos_medidos:
            st.info("Nenhum modelo foi medido nesta geracao de quantitativos.",
                    icon=":material/view_in_ar:")
            st.stop()

        malhas = {}
        for nome in modelos_medidos:
            if config.MODO_ONLINE:
                # Online nao ha IFC: usa a malha publicada junto com o painel.
                # A data do IFC (gravada no quantitativo) faz o cache recarregar
                # o 3D quando um quantitativo novo for publicado.
                malha = malha_do_modelo(nome, None,
                                        procedencia["modelos"][nome].get("modificado_em"))
                if malha is None:
                    st.warning(f"O 3D do modelo {nome} nao foi publicado.",
                               icon=":material/view_in_ar:")
                else:
                    malhas[nome] = malha
                continue

            info_do_modelo = procedencia["modelos"][nome]
            caminho_do_ifc = (caminho_registrado(info_do_modelo) if "caminho" in info_do_modelo
                              else config.MODELOS[nome])
            if not caminho_do_ifc.exists():
                st.error(f"O IFC medido do modelo {nome} nao existe mais: {caminho_do_ifc}",
                         icon=":material/error:")
                continue
            with st.spinner(f"Preparando o 3D do modelo {nome}..."):
                malhas[nome] = malha_do_modelo(nome, str(caminho_do_ifc),
                                               data_do_arquivo(caminho_do_ifc))

        modelos_ligados = st.pills("Modelos no 3D", list(malhas), selection_mode="multi",
                                   default=list(malhas), key="modelos_no_3d")

        # Linhas cujos elementos vao para o 3D: a linha escolhida ou o ramo
        linhas_em_destaque = [linha] if linha else linhas_do_ramo

        destacados, destacados_zero = set(), set()
        if mostrar_sem_regra:
            destacados = {e["global_id"] for e in conferencia.get("elementos_sem_regra", [])
                          if e["modelo"] in malhas}
        else:
            for l in linhas_em_destaque:
                for c in l["contribuicoes"]:
                    if c["global_id"] and c["valor"] != 0:
                        destacados.add(c["global_id"])
                    elif c["global_id"]:
                        destacados_zero.add(c["global_id"])
            # quem somou em alguma linha do ramo nao aparece como "zero"
            destacados_zero -= destacados

        # Explica o que o 3D esta (ou nao esta) mostrando
        modelos_da_escolha = {l.get("modelo") for l in linhas_em_destaque if l["contribuicoes"]}
        desligados = sorted(m for m in modelos_da_escolha if m in malhas and m not in modelos_ligados)
        if desligados and not mostrar_sem_regra:
            st.warning(f"Os elementos escolhidos estao no modelo {', '.join(desligados)}, "
                       "que esta desligado no 3D.", icon=":material/visibility_off:")
        elif linhas_em_destaque and not mostrar_sem_regra and not destacados and not destacados_zero:
            st.info("O que foi escolhido nao tem elementos em nenhum modelo medido "
                    f"({', '.join(sorted({l['status'] for l in linhas_em_destaque}))}).",
                    icon=":material/info:")

        pavimentos_texto = ", ".join(pavimentos_escolhidos) if pavimentos_escolhidos else "todos"
        arquivos = " · ".join(f"{nome}: {Path(malhas[nome]['ifc']).name}" for nome in malhas)
        st.caption(f"{arquivos} · pavimentos: {pavimentos_texto} (filtro da barra lateral) · "
                   "laranja: somou · laranja claro: entrou com zero · rosa: selecionado")
        visor_3d([{"nome": nome, "url": malha["url"]} for nome, malha in malhas.items()],
                 sorted(destacados), sorted(destacados_zero),
                 st.session_state["elemento_selecionado"],
                 modelos_visiveis=modelos_ligados,
                 pavimentos=pavimentos_escolhidos,
                 altura=600, ao_clicar=ao_clicar_no_3d)

        # ---- elemento selecionado ----
        global_id = st.session_state["elemento_selecionado"]
        if global_id:
            with st.container(border=True):
                # procura o elemento nos modelos carregados
                modelo_do_elemento, info = next(
                    ((nome, malha["elementos"][global_id]) for nome, malha in malhas.items()
                     if global_id in malha["elementos"]), (None, None))
                with st.container(horizontal=True, vertical_alignment="center"):
                    if info:
                        st.markdown(f"**{info['nome']}** · {info['classe']} · "
                                    f"{info['pavimento'] or 'sem pavimento'} · modelo {modelo_do_elemento}")
                    else:
                        st.markdown("**Elemento fora dos modelos carregados**")
                    st.button("Limpar selecao", icon=":material/close:",
                              on_click=limpar_selecao, type="tertiary")
                st.caption(f"GlobalId {global_id}")

                indice = indice_de_elementos(str(arquivo_escolhido), modificado_em)
                linhas_do_elemento = indice.get(global_id, [])
                if linhas_do_elemento:
                    st.markdown(f"Entrou em **{len(linhas_do_elemento)}** linhas. "
                                "Escolha uma para a auditoria ir ate ela:")
                    st.session_state["_referencias_do_elemento"] = [
                        l["referencia"] for l in linhas_do_elemento]
                    st.dataframe(
                        pd.DataFrame([{
                            "Referencia": l["referencia"],
                            "Codigo": l["codigo"],
                            "Servico": l["descricao"],
                            "Valor": l["valor"],
                            "Un.": l["unidade"],
                        } for l in linhas_do_elemento]),
                        on_select=ao_escolher_servico_do_elemento,
                        selection_mode="single-row",
                        hide_index=True,
                        key="tabela_do_elemento",
                        column_config={
                            "Servico": st.column_config.TextColumn(width="medium"),
                            "Valor": st.column_config.NumberColumn(format="%.4f")},
                    )
                else:
                    st.markdown("Este elemento **nao entrou em nenhuma linha**.")

                if info:
                    with st.expander("Parametros do elemento"):
                        st.dataframe(
                            pd.DataFrame([{"Parametro": nome, "Valor": str(valor)}
                                          for nome, valor in info["parametros"].items()]),
                            hide_index=True,
                        )

    # ---------------- linhas do ramo (largura toda) ----------------
    # Mesma razao das outras tabelas largas: na coluna da esquerda as colunas
    # de quantidade e custo ficavam fora da vista.
    if linhas_do_ramo:
        st.subheader(f"Linhas do ramo {escolha['id']} · "
                     f"{formatar_reais(sum(l.get('custo_total') or 0 for l in linhas_do_ramo))}",
                     anchor=False)
        st.dataframe(
            pd.DataFrame([{
                "Referencia": l["referencia"],
                "Codigo": l["codigo"],
                "Descricao": l["descricao"],
                "Quantidade": l["quantidade"],
                "Un.": l["unidade"],
                "Custo": formatar_reais(l.get("custo_total")),
                "Preco": l.get("status_preco"),
                "Status": l["status"],
            } for l in linhas_do_ramo]),
            hide_index=True,
            height=min(38 + 35 * len(linhas_do_ramo), 520),
            column_config={"Descricao": st.column_config.TextColumn(width="large"),
                           "Quantidade": st.column_config.NumberColumn(format="%.3f"),
                           "Custo": st.column_config.TextColumn(width=110)},
        )

    # ---------------- a composicao aberta (largura toda) ----------------
    # E aqui que o custo deixa de ser um numero e vira uma conta: cada item,
    # seu coeficiente e de onde saiu o preco. Fica na largura toda pelo mesmo
    # motivo da tabela de contribuicoes — na coluna estreita as colunas de
    # numero ficavam fora da vista.
    analitica = (((orcamento or {}).get("analiticas", {})
                  .get(f"{linha['banco']}/{linha['codigo']}")) if linha else None)
    if analitica and analitica["custo_unitario"] is not None:
        st.subheader(f"Composicao {linha['codigo']} · "
                     f"{formatar_reais(analitica['custo_unitario'])} por {analitica['unidade']}",
                     anchor=False)
        # o nome da composicao, que e o que diz o que esta sendo pago
        st.markdown(f"**{analitica['descricao']}**")
        publicado = analitica["custo_publicado"]
        st.caption(
            f"calculado {reais_no_texto(analitica['custo_unitario'])}"
            + (f" · publicado pelo SINAPI {reais_no_texto(publicado)}"
               if publicado else " · o SINAPI nao publica custo desta composicao")
            + ". O custo e somado a partir dos insumos; item com 'Preco de' = PUBLICADO "
              "e galho que o SINAPI so divulga pronto (custo horario de equipamento).")
        st.dataframe(
            pd.DataFrame([{
                "Tipo": i["tipo"],
                "Codigo": i["codigo"],
                "Descricao": i["descricao"],
                "Un.": i["unidade"],
                "Coeficiente": i["coeficiente"],
                "Custo unitario": formatar_reais(i["custo_unitario"]),
                "Total": formatar_reais(i["total"]),
                "Preco de": i["origem_do_custo"],
            } for i in analitica["itens"]]),
            hide_index=True,
            column_config={
                "Descricao": st.column_config.TextColumn(width="large"),
                "Coeficiente": st.column_config.NumberColumn(format="localized"),
                "Custo unitario": st.column_config.TextColumn(width=120),
                "Total": st.column_config.TextColumn(width=120),
            },
        )

    # ---------------- contribuicoes (largura toda) ----------------
    # Fica embaixo do detalhe e do 3D, na largura toda, para caberem as
    # colunas dos parametros usados sem precisar rolar para o lado.
    if linha and linha["contribuicoes"]:
        contribuicoes = linha["contribuicoes"]
        st.subheader(f"Contribuicoes de cada elemento · {linha['referencia']}", anchor=False)
        st.caption("Uma linha por peca. As colunas entre 'Valor' e 'Explicacao' sao os "
                   "parametros que a regra consultou, com o valor naquela peca ('—' = a peca "
                   "nao tem o parametro). Clique numa linha para destacar a peca no 3D.")
        st.session_state["_ids_das_contribuicoes"] = [c["global_id"] for c in contribuicoes]
        # Os valores dos parametros viram texto para colunas com numero e
        # texto misturados nao darem erro na tabela. Numeros com casas demais
        # (240.04832013550458) sao arredondados a 3 casas.
        def valor_para_mostrar(valor):
            if valor is None:
                return "—"
            if isinstance(valor, float):
                return str(round(valor, 3))
            return str(valor)

        st.dataframe(
            pd.DataFrame([{
                "Elemento": c["elemento"],
                "Classe": c["classe"],
                "Pav.": c["pavimento"],
                "Valor": c["valor"],
                **{nome: valor_para_mostrar(valor)
                   for nome, valor in c.get("parametros_usados", {}).items()},
                "Explicacao": c["explicacao"],
            } for c in contribuicoes]),
            on_select=ao_escolher_contribuicao,
            selection_mode="single-row",
            hide_index=True,
            height=min(38 + 35 * len(contribuicoes), 420),
            key="tabela_contribuicoes",
            column_config={"Elemento": st.column_config.TextColumn(width="medium"),
                           "Valor": st.column_config.NumberColumn(format="%.4f")},
        )
