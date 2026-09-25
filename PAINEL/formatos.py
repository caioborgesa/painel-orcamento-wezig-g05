# =============================================================
# FORMATOS — numeros do jeito brasileiro, num lugar so
# =============================================================
#
# Ficam aqui, e nao dentro do app, porque os relatorios usam os mesmos.
# Ter dois formatadores levaria ao que ja aconteceu uma vez: a mesma
# quantidade aparecendo como 117.879 numa tela e 117,879 na outra.
# =============================================================


def formatar_numero(valor):
    """1234.5 -> '1.234,500' (tres casas, como na arvore)."""
    if valor is None:
        return "—"
    return f"{valor:,.3f}".replace(",", "_").replace(".", ",").replace("_", ".")


def formatar_reais(valor):
    """1234.5 -> 'R$ 1.234,50'. Sem valor vira travessao, nunca zero."""
    if not valor:
        return "—"
    return "R$ " + f"{valor:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def reais_no_texto(valor):
    """O mesmo que formatar_reais, mas para texto corrido.

    Em markdown o cifrao abre formula matematica: "R$ 746,81 · R$ 746,77"
    apareceria como "R 746,81 · R 746,77" com o meio em italico. Por isso
    o cifrao vai escapado. Em st.metric nao precisa — la nao ha markdown.
    """
    return formatar_reais(valor).replace("$", "\\$")


def formatar_coeficiente(valor):
    """0.094 -> '0,0940' (quatro casas, como o SINAPI publica)."""
    if valor is None:
        return "—"
    return f"{valor:,.4f}".replace(",", "_").replace(".", ",").replace("_", ".")


def formatar_porcentagem(fracao):
    """0.2476 -> '24,76%'."""
    if fracao is None:
        return "—"
    return f"{fracao * 100:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".") + "%"
