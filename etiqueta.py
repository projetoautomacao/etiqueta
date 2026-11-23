
"""Geração, abertura e recuperação de etiquetas HTML 80 x 100 mm."""

from pathlib import Path
from html import escape
import base64
import re
import unicodedata
import webbrowser
from tkinter import messagebox


def _normalizar_nome(valor):
    """Converte texto em parte segura e previsível do nome do arquivo."""
    texto = unicodedata.normalize("NFKD", str(valor or ""))
    texto = "".join(
        c for c in texto if not unicodedata.combining(c)
    )
    texto = re.sub(r"[^A-Za-z0-9]+", "_", texto.upper()).strip("_")
    return texto or "NAO_INFORMADO"


def _nome_arquivo(dados):
    """Identifica o tipo de documento pela chave de 44 dígitos."""
    chave = re.sub(
        r"\D", "", str(dados.get("codigo_barras") or "")
    )

    if len(chave) != 44:
        raise ValueError(
            "Informe uma chave de acesso com 44 dígitos."
        )

    modelo = chave[20:22]

    if modelo == "57":
        tipo = "CTE"
    elif modelo == "55":
        tipo = "NFE"
    else:
        raise ValueError(
            f"Modelo de documento não reconhecido: {modelo}"
        )

    return f"{tipo}_{chave}.html"


def gerar_etiqueta(dados, pasta=None, quantidade=1, volumes=1):
    """Gera uma etiqueta por palete no formato 80 x 100 mm."""

    if type(quantidade) is not int or quantidade < 1:
        raise ValueError(
            "Informe uma quantidade inteira de paletes maior que zero."
        )

    if type(volumes) is not int or volumes < 1:
        raise ValueError(
            "Informe uma quantidade inteira de volumes maior que zero."
        )

    raiz = Path(__file__).resolve().parents[1]
    pasta = Path(pasta) if pasta else raiz / "etiquetas"
    pasta.mkdir(parents=True, exist_ok=True)

    nome_arquivo = _nome_arquivo(dados)

    numero_cte = str(dados.get("numero_cte") or "").strip()
    numero_nf = str(dados.get("numero_nf") or "").strip()

    tipo_documento = "CTE:" if numero_cte else "NF:"
    numero_documento = escape(numero_cte or numero_nf)

    remetente = escape(str(dados.get("remetente") or ""))
    destinatario = escape(str(dados.get("destinatario") or ""))

    rotulo_destino = (
        "REDES:" if dados.get("redespacho") else "DES:"
    )

    cidade_destino = str(
        dados.get("cidade_destino") or ""
    ).strip()

    uf_destino = str(
        dados.get("uf_destino") or ""
    ).strip()

    cidade = escape(
        " / ".join(
            valor for valor in (cidade_destino, uf_destino)
            if valor
        )
    )

    # --------------------------------------------------------
    # LOGOTIPO
    # --------------------------------------------------------

    logo = raiz / "assets" / "logo.png"

    if logo.is_file():
        imagem = base64.b64encode(
            logo.read_bytes()
        ).decode("ascii")

        marca = (
            f'<img class="logo" '
            f'src="data:image/png;base64,{imagem}" '
            f'alt="Transanches Transportes">'
        )
    else:
        marca = """
        <div class="marca">
            TRANSANCHES
            <small>TRANSPORTES</small>
        </div>
        """

    # --------------------------------------------------------
    # HTML E CSS DA ETIQUETA
    # --------------------------------------------------------

    pagina = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<title>Etiquetas de transporte</title>

<style>

@page {
    size: 80mm 100mm;
    margin: 0;
}

* {
    box-sizing: border-box;
}

body {
    margin: 0;
    background: #fff;
    color: #000;
    font-family: Arial, sans-serif;
}

/* ÁREA DA ETIQUETA */

.etiqueta {
    width: 80mm;
    height: 100mm;
    padding: 25mm 6mm 7mm;
    overflow: hidden;
    background: #fff;
    break-after: page;
    page-break-after: always;
}

.etiqueta:last-child {
    break-after: auto;
    page-break-after: auto;
}

.layout {
    width: 100%;
    height: 100%;
    display: flex;
    flex-direction: column;
    min-width: 0;
    transform: none;
}

/* CABEÇALHO E LOGOTIPO */

.cabecalho {
    height: 17mm;
    flex: 0 0 17mm;
    display: flex;
    align-items: center;
    justify-content: center;
}

.logo {
    width: 58mm;
    max-height: 14mm;
    object-fit: contain;
}

.marca {
    font-family: "Arial Black", Arial, sans-serif;
    font-size: 21pt;
    font-weight: 900;
    font-style: italic;
    line-height: 1;
    text-align: center;
}

.marca small {
    display: block;
    margin-top: 1mm;
    font-family: Arial, sans-serif;
    font-size: 9pt;
    font-weight: normal;
    letter-spacing: 3px;
}

/* LINHAS DOS DOCUMENTOS */

.linha {
    display: flex;
    align-items: center;
    height: 10mm;
    flex: 0 0 10mm;
    min-width: 0;
}

/* TÍTULOS - 18 PT EM NEGRITO */

.rotulo {
    flex-shrink: 0;
    font-family: "Arial Black", Arial, sans-serif;
    font-size: 18pt;
    font-weight: 900;
}

.sublinhado {
    text-decoration: underline;
    text-underline-offset: 1mm;
}

/* DADOS - 16 PT EM ITÁLICO */

.valor {
    flex: 1 1 auto;
    min-width: 0;
    margin-left: 2mm;
    font-size: 16pt;
    font-weight: normal;
    font-style: italic;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: clip;
}

/* AJUSTE AUTOMÁTICO PARA NOMES EXTENSOS */

.valor.ajustado {
    font-size: var(--fonte-ajustada, 16pt);
}

/* RODAPÉ */

.rodape {
    height: 10mm;
    flex: 0 0 10mm;
    margin-top: auto;
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 2mm;
    padding-bottom: 2mm;
    white-space: nowrap;
}

.grupo-rodape {
    display: flex;
    align-items: baseline;
    gap: 1mm;
    min-width: 0;
}

/* NÚMEROS DE PLT E VOL - 17 PT */

.sequencia {
    font-family: Arial, sans-serif;
    font-size: 17pt;
    font-weight: normal;
    font-style: italic;
    white-space: nowrap;
}

/* RODAPÉ COMPACTO */

.rodape.compacto .rotulo {
    font-size: 14pt;
}

.rodape.compacto .sequencia {
    font-size: 13pt;
}

/* BOTÃO DE IMPRESSÃO */

.acoes {
    padding: 12px;
    font-size: 14px;
}

@media print {
    .acoes {
        display: none;
    }
}

</style>
</head>

<body>

<div class="acoes">
    <button onclick="window.print()">
        Imprimir todas as etiquetas
    </button>

    <p>
        Papel 80 × 100 mm, escala 100%,
        sem cabeçalhos e rodapés.
    </p>
</div>

<div class="lote">
"""

    # --------------------------------------------------------
    # GERAÇÃO DAS ETIQUETAS EM SEQUÊNCIA
    # --------------------------------------------------------

    for sequencia in range(1, quantidade + 1):

        numero = f"{sequencia:02d}"
        total = f"{quantidade:02d}"
        vol = f"{volumes:02d}"

        pagina += f"""
    <main class="etiqueta">

        <div class="layout">

            <header class="cabecalho">
                {marca}
            </header>

            <div class="linha">
                <span class="rotulo sublinhado">
                    {tipo_documento}
                </span>
                <span class="valor">
                    {numero_documento}
                </span>
            </div>

            <div class="linha">
                <span class="rotulo">
                    REM:
                </span>
                <span class="valor">
                    {remetente}
                </span>
            </div>

            <div class="linha">
                <span class="rotulo sublinhado">
                    {rotulo_destino}
                </span>
                <span class="valor">
                    {destinatario}
                </span>
            </div>

            <div class="linha">
                <span class="rotulo">
                    CID:
                </span>
                <span class="valor">
                    {cidade}
                </span>
            </div>

            <footer class="rodape">

                <div class="grupo-rodape">
                    <span class="rotulo">PLT:</span>
                    <span class="sequencia">
                        {numero} / {total}
                    </span>
                </div>

                <div class="grupo-rodape">
                    <span class="rotulo">VOL:</span>
                    <span class="sequencia">
                        {vol}
                    </span>
                </div>

            </footer>

        </div>

    </main>
"""

    # --------------------------------------------------------
    # JAVASCRIPT - AJUSTE AUTOMÁTICO DA FONTE
    # --------------------------------------------------------

    pagina += """
</div>

<script>

(function () {

    function ajustarFonte(elemento, minimoPx) {

        var fonte = parseFloat(
            getComputedStyle(elemento).fontSize
        );

        var tentativas = 0;

        while (
            elemento.scrollWidth > elemento.clientWidth + 1 &&
            fonte > minimoPx &&
            tentativas < 60
        ) {
            fonte -= 0.5;
            elemento.style.fontSize = fonte + "px";
            tentativas++;
        }

        elemento.classList.add("ajustado");
    }

    function prepararImpressao() {

        document.querySelectorAll(
            ".linha .valor"
        ).forEach(function (elemento) {

            ajustarFonte(elemento, 10);

        });

        document.querySelectorAll(
            ".rodape"
        ).forEach(function (rodape) {

            if (
                rodape.scrollWidth >
                rodape.clientWidth + 1
            ) {
                rodape.classList.add("compacto");
            }

        });
    }

    window.addEventListener("load", function () {

        prepararImpressao();
        window.print();

    });

    window.addEventListener(
        "beforeprint",
        prepararImpressao
    );

})();

</script>

</body>
</html>
"""

    # --------------------------------------------------------
    # SALVAR ETIQUETA HTML
    # --------------------------------------------------------

    destino = pasta / nome_arquivo

    destino.write_text(
        pagina,
        encoding="utf-8"
    )

    return destino


def abrir_etiqueta(dados, quantidade=1, volumes=1):
    """Gera e abre a etiqueta no navegador."""

    caminho = gerar_etiqueta(
        dados,
        quantidade=quantidade,
        volumes=volumes
    )

    if not webbrowser.open(
        caminho.resolve().as_uri()
    ):
        raise OSError(
            "Não foi possível abrir o navegador. "
            f"Abra o arquivo: {caminho}"
        )

    return caminho


def recuperar_etiqueta(dados, parent=None):
    """Recupera uma etiqueta HTML já salva."""

    try:
        nome_arquivo = _nome_arquivo(dados)

    except (ValueError, AttributeError) as erro:

        messagebox.showwarning(
            "Recuperar Etiqueta",
            str(erro),
            parent=parent
        )

        return False

    raiz = Path(__file__).resolve().parents[1]

    caminho = (
        raiz /
        "etiquetas" /
        nome_arquivo
    )

    if not caminho.is_file():

        messagebox.showwarning(
            "Recuperar Etiqueta",
            f"Arquivo não encontrado:\n{nome_arquivo}",
            parent=parent
        )

        return False

    try:

        if not webbrowser.open(
            caminho.resolve().as_uri()
        ):
            raise OSError(
                "Não foi possível abrir o navegador."
            )

    except OSError as erro:

        messagebox.showerror(
            "Erro",
            str(erro),
            parent=parent
        )

        return False

    return True
