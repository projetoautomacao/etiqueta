import tkinter as tk
import unicodedata
import json
from pathlib import Path
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime


if __package__ and "." in __package__:
    from ..controllers.controller import Controller
    from ..services.etiqueta import abrir_etiqueta, recuperar_etiqueta
    from . import dashboard_design as design
else:
    from controllers.controller import Controller
    from services.etiqueta import abrir_etiqueta, recuperar_etiqueta
    from views import dashboard_design as design


class DashboardCTe(tk.Tk):
    """Janela principal do cadastro de CT-e."""

    def __init__(self):
        super().__init__()

        self.controller = Controller()
        self.modal_motorista = None
        self.modal_resultados = None

        self.title(design.WINDOW_TITLE)
        self.geometry(design.WINDOW_SIZE)
        self.minsize(design.WINDOW_MIN_WIDTH, design.WINDOW_MIN_HEIGHT)
        self.configure(bg=design.BG)

        design.configurar_estilos(self)
        self._criar_variaveis()
        self._criar_interface()
        self._configurar_autocomplete_clientes()
        self._configurar_autocomplete_cidades()
        self._carregar_ultimo_documento()
        self._atualizar_relogio()

    def _criar_variaveis(self):
        """Cria as variáveis vinculadas aos campos e aos cards da tela."""
        self.placeholder_data = "dd/mm/aaaa"
        self.placeholder_ajuda="leia uma chave de 44 digitos"
        self.remetente_var = tk.StringVar()
        self.destinatario_var=tk.StringVar()
        self.codigo_var = tk.StringVar(value=self.placeholder_ajuda)
        self._consulta_chave_agendada = None
        self._preenchendo_documento = False
        self.documento_em_edicao = None
        self._campos_em_atualizacao = set()
        self.numero_documento_var = tk.StringVar()
        self.cidade_origem_var = tk.StringVar()
        self.uf_origem_var = tk.StringVar()
        self.cidade_destino_var = tk.StringVar()
        self.uf_destino_var = tk.StringVar()
        self.placa_var = tk.StringVar()
        self.motorista_var = tk.StringVar()
        self.data_var = tk.StringVar(value=self.placeholder_data)#tk.StringVar(value=datetime.now().strftime("%d/%m/%Y"))
        self.observacao_var = tk.StringVar()

        self.ultimo_cte_var = tk.StringVar(value="")
        self.cliente_var = tk.StringVar(value="")
        self.card_motorista_var = tk.StringVar(value="")
        self.card_placa_var = tk.StringVar(value="")

    def _criar_interface(self):
        """Monta a estrutura principal da janela."""
        area = tk.Frame(self, bg=design.BG)
        area.pack(fill="both", expand=True)

        self._criar_topbar(area)

        # O rodapé é reservado antes do conteúdo expansível para que
        # os botões permaneçam visíveis na janela normal e maximizada.
        self._criar_rodape(area)

        # Somente o conteúdo rola; o rodapé permanece acessível.
        conteudo = tk.Frame(area, bg=design.BG)
        conteudo.pack(
            fill="both",
            expand=True,
            padx=design.CONTENT_PAD_X,
            pady=(design.CONTENT_PAD_TOP, design.CONTENT_PAD_BOTTOM),
        )
        self._criar_cabecalho(conteudo)
        self._criar_cards(conteudo)
        self._criar_formulario(conteudo)

    def _criar_topbar(self, parent):
        """Cria a barra superior com marca, data, hora e indicador."""
        topbar = tk.Frame(parent, bg=design.WHITE, height=design.TOPBAR_HEIGHT)
        topbar.pack(fill="x")
        topbar.pack_propagate(False)

        marca = tk.Label(
            topbar,
            text="TRANSANCHES TRANSPORTES",
            font=design.FONT_LABEL,
            fg=design.NAVY,
            bg=design.WHITE,
        )
        marca.pack(side="left", padx=1)

        direita = tk.Frame(topbar, bg=design.WHITE)
        direita.pack(side="right", padx=18, fill="y")

        self.relogio_label = tk.Label(
            direita,
            text="--/--/----  •  --:--:--",
            **design.LABEL_MUTED,
        )
        self.relogio_label.pack(side="left", pady=16)

        tk.Label(
            direita,
            text="●",
            font=design.FONT_SMALL,
            fg=design.SUCCESS,
            bg=design.WHITE,
        ).pack(side="left", padx=(10, 0), pady=16)

        tk.Frame(parent, bg=design.BORDER, height=1).pack(fill="x")

    def _criar_cabecalho(self, parent):
        """Cria o título e a descrição da tela."""
        cabecalho = tk.Frame(parent, bg=design.BG)
        cabecalho.pack(fill="x", pady=(12, 8))

        textos = tk.Frame(cabecalho, bg=design.BG)
        textos.pack(side="left", fill="x", expand=True)

        tk.Label(
            textos,
            text="Cadastro de CT-e",
            **design.TITLE_STYLE,
        ).pack(anchor="w")

        tk.Label(
            textos,
            text="Registre e consulte os dados do transporte",
            font=design.FONT_NORMAL,
            fg=design.MUTED,
            bg=design.BG,
        ).pack(anchor="w", pady=(2, 0))

    def _criar_cards(self, parent):
        """Cria os cards com os dados do último documento trabalhado."""
        cards = tk.Frame(parent, bg=design.BG)
        cards.pack(fill="x", pady=(0, 10))

        dados = (
            ("Último documento", self.ultimo_cte_var),
            ("Cliente", self.cliente_var),
            ("Motorista", self.card_motorista_var),
            ("Placa", self.card_placa_var),
        )

        for coluna, (titulo, variavel) in enumerate(dados):
            cards.grid_columnconfigure(coluna, weight=1, uniform="cards")
            self._criar_card(cards, titulo, variavel, coluna)

    def _criar_card(self, parent, titulo, variavel, coluna):
        card = tk.Frame(parent, **design.CARD_STYLE)
        card.grid(row=0, column=coluna, sticky="nsew", padx=4)

        tk.Label(
            card,
            text=titulo,
            font=design.FONT_LABEL,
            fg=design.MUTED,
            bg=design.WHITE,
        ).pack(anchor="w", padx=12, pady=(8, 1))

        tk.Label(
            card,
            textvariable=variavel,
            font=design.FONT_CARD_VALUE,
            fg=design.NAVY,
            bg=design.WHITE,
            anchor="w",
        ).pack(fill="x", padx=12, pady=(0, 7))

    def _criar_formulario(self, parent):
        """Cria os campos do formulário principal e registra seus eventos."""
        container = tk.Frame(
            parent,
            **design.FORM_CONTAINER_STYLE
        )
        container.pack(fill="both", expand=True)

        # Cabeçalho
        cabecalho = tk.Frame(
            container,
            bg=design.WHITE
        )
        cabecalho.pack(
            fill="x",
            padx=16,
            pady=8
        )

        tk.Label(
            cabecalho,
            text="Dados de Transporte",
            **design.SECTION_TITLE_STYLE,
        ).pack(side="left")

        tk.Label(
            cabecalho,
            text="Preencha os dados abaixo para cadastrar o CT-e",
            **design.LABEL_MUTED,
        ).pack(
            side="left",
            padx=16,
            pady=3
        )

        tk.Frame(
            container,
            bg=design.BORDER,
            height=1
        ).pack(
            fill="x",
            padx=16
        )

        # Corpo do formulário
        corpo = tk.Frame(
            container,
            bg=design.WHITE
        )
        corpo.pack(
            fill="both",
            expand=True,
            padx=design.FORM_PAD_X,
            pady=design.FORM_PAD_Y,
        )

        for coluna in range(6):
            corpo.grid_columnconfigure(
                coluna,
                weight=1,
                uniform="campos"
            )

        # Linha 1
        self.remetente_entry = self._criar_campo(
            corpo,
            "Remetente",
            self.remetente_var,
            0,
            0,
            2
        )
        self.destinatario_entry=self._criar_campo(
            corpo,
            "Destinatario",
            self.destinatario_var,
            0,
            2,
            2

        )

        self.codigo_entry = self._criar_campo(
            corpo,
            "Chave NF-e / CT-e",
            self.codigo_var,
            0,
            4,
            2,

        )
        # O placeholder não faz parte da chave digitada ou lida pelo scanner.
        self.codigo_entry.bind("<KeyPress>", self._limpar_ajuda_chave)
        self.codigo_entry.bind("<<Paste>>", self._limpar_ajuda_chave)

        # Linha 2
        self.numero_documento_entry = self._criar_campo(
            corpo,
            "Número NF-e / CT-e",
            self.numero_documento_var,
            1,
            0,
            2
        )
        # Começa livre para permitir digitação manual do número do CT-e.
        # Será bloqueado apenas quando vier de um código de barras válido.
        self.numero_documento_entry.config(
            state="normal",
            style="TEntry",
        )
        # Ao iniciar uma consulta pelo número do CT-e/NF-e, remove a
        # orientação do campo da chave, sem apagar o primeiro caractere.
        self.numero_documento_entry.bind(
            "<KeyPress>", self._limpar_chave_ao_digitar_numero
        )
        self.numero_documento_entry.bind(
            "<<Paste>>", self._limpar_chave_ao_digitar_numero
        )


        self.placa_entry = self._criar_campo(
            corpo,
            "Placa",
            self.placa_var,
            1,
            2,
            2
        )

        self.motorista_entry = self._criar_campo(
            corpo,
            "Motorista",
            self.motorista_var,
            1,
            4,
            2
        )

        # O motorista é preenchido pela consulta da placa ou pelo modal.
        self.motorista_entry.config(
            state="readonly",
            style="Data.TEntry",
        )

        # Linha 3: data e rota, com cidades expansíveis e UFs estreitas.
        linha_rota = tk.Frame(corpo, bg=design.WHITE)
        linha_rota.grid(row=2, column=0, columnspan=6, sticky="ew")
        for coluna in (2, 4):
            linha_rota.grid_columnconfigure(coluna, weight=1, uniform="cidades")
        self.data_entry = self._criar_campo(
            linha_rota, "Data", self.data_var, 0, 0,
        )
        self.data_entry.configure(width=11)

        self.data_entry.config(
            state="normal",
            foreground=design.MUTED
        )
        self.data_entry.bind(
            "<FocusIn>",
            lambda event: (
                self.data_var.set(""),
                self.data_entry.configure(foreground=design.TEXT),
            )
            if self.data_var.get() == self.placeholder_data
            else None,
        )

        self.data_entry.bind(
            "<FocusOut>",
            lambda event: (
                self.data_var.set(self.placeholder_data),
                self.data_entry.configure(foreground=design.MUTED),
            )
            if not self.data_var.get().strip()
            else None,
        )
        # Primeiro a UF; depois a cidade, tanto na origem quanto no destino.
        for local, coluna in (("origem", 1), ("destino", 3)):
            bloco = tk.Frame(linha_rota, bg=design.WHITE)
            bloco.grid(row=0, column=coluna, sticky="ew",
                       padx=design.FIELD_PAD_X, pady=(0, design.FIELD_PAD_BOTTOM))
            tk.Label(bloco, text=f"UF de {local}", **design.LABEL_NORMAL).pack(anchor="w")
            uf = ttk.Combobox(bloco, textvariable=getattr(self, f"uf_{local}_var"),
                              values=Controller.UFS, state="readonly", width=5)
            uf.pack(fill="x", pady=(4, 0))
            setattr(self, f"uf_{local}_entry", uf)

            entrada = self._criar_campo(
                linha_rota, f"Cidade de {local}", getattr(self, f"cidade_{local}_var"),
                0, coluna + 1,
            )
            entrada.configure(width=10)
            setattr(self, f"cidade_{local}_entry", entrada)
            uf.bind("<<ComboboxSelected>>", lambda event, loc=local: self._uf_escolhida(loc))

        # Último campo, depois de origem e destino.
        self.observacao_entry = self._criar_campo(
            corpo, "Observação", self.observacao_var, 3, 0, 6,
        )

        def chave_alterada(*args):
            # Cancela a consulta anterior quando a chave é alterada.
            if self._consulta_chave_agendada is not None:
                self.after_cancel(self._consulta_chave_agendada)
                self._consulta_chave_agendada = None
            if self._preenchendo_documento:
                return
            self.numero_documento_var.set("")
            self.numero_documento_entry.configure(state="normal", style="TEntry")
            codigo = self.codigo_var.get().strip()
            if codigo == self.placeholder_ajuda:
                return
            if len(codigo) == 44 and codigo.isascii() and codigo.isdecimal():
                # Pequena espera para concluir a leitura e evitar buscas repetidas.
                self._consulta_chave_agendada = self.after(120, self._buscar_chave_completa)

        self.codigo_var.trace_add("write", chave_alterada)

        # Eventos
        self.codigo_entry.bind(
            "<Return>",
            self._ao_confirmar_codigo
        )

        self.placa_entry.bind(
            "<Return>",
            self._consultar_motorista_placa
        )
        # Ao abrir, posiciona o cursor no código
        self.codigo_entry.focus_set()
    def _criar_campo(
        self,
        parent,
        titulo,
        variavel,
        linha,
        coluna,
        quantidade_colunas=1,
        ajuda=None,
    ):
        bloco = tk.Frame(parent, bg=design.WHITE)
        bloco.grid(
            row=linha,
            column=coluna,
            columnspan=quantidade_colunas,
            sticky="ew",
            padx=design.FIELD_PAD_X,
            pady=(0, design.FIELD_PAD_BOTTOM),
        )

        tk.Label(
            bloco,
            text=titulo,
            font=design.FONT_LABEL,
            fg=design.TEXT,
            bg=design.WHITE,
        ).pack(anchor="w", pady=(0, 4))

        entrada = ttk.Entry(bloco, textvariable=variavel)
        entrada.pack(fill="x")

        if ajuda:
            tk.Label(
                bloco,
                text=ajuda,
                font=design.FONT_HELP,
                fg=design.MUTED,
                bg=design.WHITE,
            ).pack(anchor="w", pady=(3, 0))

        return entrada

    def _atualizar_cards_documento(self, documento=None):
        """Exibe nos quatro cards os dados de um único documento cadastrado."""
        documento = documento or {}
        numero = (documento.get("numero_documento")
                  or documento.get("numero_cte")
                  or documento.get("numero_nf") or "")
        self.ultimo_cte_var.set(str(numero))
        self.cliente_var.set(str(documento.get("remetente") or ""))
        self.card_motorista_var.set(str(documento.get("motorista") or ""))
        self.card_placa_var.set(str(documento.get("placa") or ""))

    def _carregar_ultimo_documento(self):
        """Busca o cadastro mais recente diretamente na tabela documentos."""
        try:
            with self.controller.repository.conectar() as conexao:
                registro = conexao.execute(
                    "SELECT * FROM documentos ORDER BY id DESC LIMIT 1"
                ).fetchone()

            documento = dict(registro) if registro is not None else None
            self._atualizar_cards_documento(documento)
            pass  # Saída de depuração removida
        except Exception as erro:
            self._atualizar_cards_documento()
            self._mostrar_status(
                f"Erro ao carregar último cadastro: {erro}", design.DANGER
            )
            pass  # Saída de depuração removida

    def _configurar_autocomplete_cidades(self):
        """Carrega cidades.json uma vez e ativa autocomplete por UF e 3 letras."""
        # Aceita o JSON na raiz do projeto, em data/ ou junto à view.
        arquivo_view = Path(__file__).resolve()
        candidatos = (
            arquivo_view.parent.parent / "cidades.json",
            arquivo_view.parent.parent / "dados" / "cidades" / "cidades.json",
            arquivo_view.parent.parent / "dados" / "cidades.json",
            arquivo_view.parent.parent / "data" / "cidades.json",
            arquivo_view.parent / "cidades.json",
        )
        caminho = next((p for p in candidatos if p.is_file()), None)
        self._cidades_por_uf = {}
        if caminho is None:
            self._mostrar_status(
                "cidades.json não encontrado. Verifique a pasta dados/cidades na raiz do projeto.",
                design.DANGER,
            )
        else:
            try:
                with caminho.open("r", encoding="utf-8-sig") as arquivo:
                    registros = json.load(arquivo)
                if not isinstance(registros, list):
                    raise ValueError("A raiz do JSON deve ser uma lista de cidades.")
                for item in registros:
                    if not isinstance(item, dict):
                        continue
                    cidade = str(item.get("cidade") or "").strip()
                    uf = str(item.get("estado") or "").strip().upper()
                    if cidade and len(uf) == 2:
                        self._cidades_por_uf.setdefault(uf, []).append(cidade)
                for uf in self._cidades_por_uf:
                    self._cidades_por_uf[uf] = sorted(
                        set(self._cidades_por_uf[uf]), key=self._normalizar_busca
                    )
                total = sum(len(lista) for lista in self._cidades_por_uf.values())
                pass  # Saída de depuração removida
                if total == 0:
                    self._mostrar_status(
                        "O cidades.json foi localizado, mas não contém cidades no formato esperado.",
                        design.DANGER,
                    )
            except (OSError, ValueError, TypeError) as erro:
                self._mostrar_status(f"Erro ao carregar cidades.json: {erro}", design.DANGER)

        self._listas_sugestoes_cidades = {}
        self._atualizando_cidade = False
        for local in ("origem", "destino"):
            entrada_antiga = getattr(self, f"cidade_{local}_entry")
            bloco = entrada_antiga.master
            variavel = getattr(self, f"cidade_{local}_var")
            entrada_antiga.destroy()

            # Campo de digitação; as sugestões aparecem abaixo, sem clicar na seta.
            entrada = ttk.Entry(bloco, textvariable=variavel)
            entrada.pack(fill="x")
            setattr(self, f"cidade_{local}_entry", entrada)

            lista = tk.Listbox(
                bloco, height=5, exportselection=False,
                font=design.FONT_NORMAL, activestyle="dotbox",
                selectmode="browse", relief="solid", borderwidth=1,
            )
            self._listas_sugestoes_cidades[local] = lista
            variavel.trace_add("write", lambda *args, loc=local: self._filtrar_cidades(loc))
            entrada.bind("<Down>", lambda event, loc=local: self._navegar_cidades(loc))
            entrada.bind("<Escape>", lambda event, loc=local: self._ocultar_cidades(loc))
            entrada.bind("<Return>", lambda event, loc=local: self._confirmar_cidade_digitada(loc))
            lista.bind("<ButtonRelease-1>", lambda event, loc=local: self._selecionar_cidade_lista(loc))
            lista.bind("<Return>", lambda event, loc=local: self._selecionar_cidade_lista(loc))
            lista.bind("<Escape>", lambda event, loc=local: self._ocultar_cidades(loc))

    def _uf_escolhida(self, local):
        """Ao mudar a UF manualmente, descarta a cidade anterior."""
        getattr(self, f"cidade_{local}_var").set("")
        self._ocultar_cidades(local)

    def _ocultar_cidades(self, local):
        lista = self._listas_sugestoes_cidades.get(local)
        if lista is not None:
            lista.pack_forget()
        return "break"

    def _filtrar_cidades(self, local):
        """Exibe sugestões imediatamente abaixo do campo após 3 letras."""
        if self._atualizando_cidade:
            return
        lista = self._listas_sugestoes_cidades[local]
        uf = getattr(self, f"uf_{local}_var").get().strip().upper()
        texto = getattr(self, f"cidade_{local}_var").get().strip()
        if len(texto) < 3 or not uf:
            self._ocultar_cidades(local)
            return
        termo = self._normalizar_busca(texto)
        encontrados = [
            cidade for cidade in self._cidades_por_uf.get(uf, [])
            if termo in self._normalizar_busca(cidade)
        ][:30]
        lista.delete(0, tk.END)
        if not encontrados:
            self._ocultar_cidades(local)
            return
        for cidade in encontrados:
            lista.insert(tk.END, cidade)
        lista.configure(height=min(len(encontrados), 6))
        if not lista.winfo_manager():
            lista.pack(fill="x", pady=(2, 0))

    def _navegar_cidades(self, local):
        """Seta para baixo leva à lista sem exigir uso do mouse."""
        lista = self._listas_sugestoes_cidades[local]
        if lista.winfo_manager() and lista.size():
            lista.focus_set()
            lista.selection_clear(0, tk.END)
            lista.selection_set(0)
            lista.activate(0)
        return "break"

    def _confirmar_cidade_digitada(self, local):
        lista = self._listas_sugestoes_cidades[local]
        if lista.winfo_manager() and lista.size():
            lista.selection_clear(0, tk.END)
            lista.selection_set(0)
            self._selecionar_cidade_lista(local)
        return "break"

    def _selecionar_cidade_lista(self, local):
        """Aplica a cidade escolhida e fecha as sugestões."""
        lista = self._listas_sugestoes_cidades[local]
        indices = lista.curselection()
        if not indices:
            return "break"
        cidade = lista.get(indices[0])
        self._atualizando_cidade = True
        try:
            getattr(self, f"cidade_{local}_var").set(cidade)
        finally:
            self._atualizando_cidade = False
        self._ocultar_cidades(local)
        getattr(self, f"cidade_{local}_entry").focus_set()
        return "break"

    def _configurar_autocomplete_clientes(self):
        """Autocomplete compartilhado para remetente e destinatário."""
        self._clientes_cache = self.controller.consultar_clientes()
        pass  # Saída de depuração removida
        self._clientes_selecionados = {"remetente": None, "destinatario": None}
        self._atualizando_cliente = False
        self._avisos_cliente = {}

        for tipo in ("remetente", "destinatario"):
            entrada_antiga = getattr(self, f"{tipo}_entry")
            bloco = entrada_antiga.master
            variavel = getattr(self, f"{tipo}_var")
            entrada_antiga.destroy()
            combo = ttk.Combobox(bloco, textvariable=variavel, state="normal", height=8)
            combo.pack(fill="x")
            setattr(self, f"{tipo}_entry", combo)
            aviso = tk.Label(bloco, text="", font=design.FONT_SMALL,
                             fg=design.DANGER, bg=design.WHITE, anchor="w",
                             justify="left", wraplength=330)
            aviso.pack(fill="x", anchor="w")
            self._avisos_cliente[tipo] = aviso
            variavel.trace_add("write", lambda *args, t=tipo: self._filtrar_cliente(t))
            combo.bind("<<ComboboxSelected>>", lambda e, t=tipo: self._selecionar_cliente(t))
            combo.bind("<FocusIn>", lambda e: self._recarregar_clientes())
            combo.bind("<FocusOut>", lambda e, t=tipo: self.after(120, self._validar_cliente, t))

    def _recarregar_clientes(self):
        """Reconsulta o banco para incluir clientes cadastrados recentemente."""
        try:
            self._clientes_cache = self.controller.consultar_clientes()
        except Exception as erro:
            self._mostrar_status(f"Erro ao carregar clientes: {erro}", design.DANGER)

    @staticmethod
    def _normalizar_busca(texto):
        texto = unicodedata.normalize("NFKD", str(texto or ""))
        return "".join(c for c in texto if not unicodedata.combining(c)).casefold().strip()

    def _filtrar_cliente(self, tipo):
        if self._atualizando_cliente:
            return
        nome = getattr(self, f"{tipo}_var").get().strip()
        self._clientes_selecionados[tipo] = None
        combo = getattr(self, f"{tipo}_entry")
        aviso = self._avisos_cliente[tipo]
        if len(nome) < 3:
            combo.configure(values=[])
            aviso.configure(text="")
            return
        termo = self._normalizar_busca(nome)
        encontrados = [c["nome"] for c in self._clientes_cache
                       if termo in self._normalizar_busca(c["nome"])]
        combo.configure(values=list(dict.fromkeys(encontrados)))
        if encontrados:
            aviso.configure(text=f"{len(encontrados)} cliente(s) encontrado(s). Selecione pela seta.", fg=design.SUCCESS)
            # O ttk.Combobox não abre a lista automaticamente ao digitar.
            # A seta permanece disponível sem interromper a digitação.
        else:
            aviso.configure(text="Cliente não consta no banco de dados. Será cadastrado ao salvar o documento.", fg=design.DANGER)

    def _encontrar_cliente(self, tipo):
        nome = self._normalizar_busca(getattr(self, f"{tipo}_var").get())
        cidade = getattr(self, "cidade_origem_var" if tipo == "remetente"
                         else "cidade_destino_var").get().strip().casefold()
        uf = getattr(self, "uf_origem_var" if tipo == "remetente"
                     else "uf_destino_var").get().strip().casefold()
        candidatos = [c for c in self._clientes_cache
                      if self._normalizar_busca(c["nome"]) == nome]
        if len(candidatos) == 1:
            return candidatos[0]
        candidatos = [c for c in candidatos if c["cidade"].strip().casefold() == cidade
                      and c["uf"].strip().casefold() == uf]
        return candidatos[0] if len(candidatos) == 1 else None

    def _selecionar_cliente(self, tipo):
        cliente = self._encontrar_cliente(tipo)
        if cliente is None:
            return
        self._atualizando_cliente = True
        try:
            getattr(self, f"{tipo}_var").set(cliente["nome"])
            local = "origem" if tipo == "remetente" else "destino"
            getattr(self, f"uf_{local}_var").set(cliente["uf"])
            getattr(self, f"cidade_{local}_var").set(cliente["cidade"])
            self._clientes_selecionados[tipo] = cliente["id"]
            self._avisos_cliente[tipo].configure(text="")
        finally:
            self._atualizando_cliente = False

    def _validar_cliente(self, tipo):
        if not self.winfo_exists():
            return
        cliente = self._encontrar_cliente(tipo)
        if cliente:
            self._selecionar_cliente(tipo)
        elif len(getattr(self, f"{tipo}_var").get().strip()) >= 3:
            self._avisos_cliente[tipo].configure(
                text="Cliente não consta no banco de dados. "
                     "Será cadastrado ao salvar o documento.")

    def _criar_rodape(self, parent):
        """Cria a barra de status e os quatro botões principais."""

        rodape = tk.Frame(
            parent,
            bg=design.WHITE,
            height=design.FOOTER_HEIGHT,
            highlightbackground=design.BORDER,
            highlightthickness=1,
        )
        rodape.pack(side="bottom", fill="x")

        informacoes = tk.Frame(rodape, bg=design.WHITE)
        informacoes.pack(fill="x", padx=14, pady=(7, 3))

        self.status_label = tk.Label(
            informacoes,
            text="● Pronto para receber um CT-e",
            font=design.FONT_SMALL,
            fg=design.SUCCESS,
            bg=design.WHITE,
            anchor="w",
        )
        self.status_label.pack(side="left", fill="x", expand=True)

        botoes = tk.Frame(rodape, bg=design.WHITE)
        botoes.pack(fill="x", padx=10, pady=(0, 7))

        # Agora são quatro colunas.
        for coluna in range(4):
            botoes.grid_columnconfigure(
                coluna,
                weight=1,
                uniform="acoes",
            )

        tk.Button(
            botoes,
            text="Cad. Motorista",
            command=self._abrir_modal_motorista,
            **design.BUTTON_OUTLINE,
        ).grid(row=0, column=0, sticky="ew", padx=1)

        tk.Button(
            botoes,
            text="Consultar",
            command=self._consultar,
            **design.BUTTON_SECONDARY,
        ).grid(row=0, column=1, sticky="ew", padx=1)

        tk.Button(
            botoes,
            text="Recuperar Etiqueta",
            command=self._recuperar_etiqueta,
            **design.BUTTON_OUTLINE,
        ).grid(row=0, column=2, sticky="ew", padx=1)

        self.botao_cadastrar = tk.Button(
            botoes,
            text="Cadastrar",
            command=self._salvar_documento,
            **design.BUTTON_PRIMARY,
        )
        self.botao_cadastrar.grid(row=0, column=3, sticky="ew", padx=1)

    # --------------------------------------------------------
    # COMUNICAÇÃO ENTRE A VIEW E O CONTROLLER
    # --------------------------------------------------------
    def _obter_dados_formulario(self):
        """Lê os campos e devolve os dados esperados pelo Controller."""
        return {
            "remetente": self.remetente_var.get().strip(),
            "id_remetente": self._clientes_selecionados.get("remetente"),
            "codigo_barras": ("" if self.codigo_var.get().strip() == self.placeholder_ajuda
                             else self.codigo_var.get().strip()),
            "numero_documento": self.numero_documento_var.get().strip(),
            "destinatario": self.destinatario_var.get().strip(),
            "id_destinatario": self._clientes_selecionados.get("destinatario"),
            "cidade_origem": self.cidade_origem_var.get().strip(),
            "uf_origem": self.uf_origem_var.get().strip(),
            "cidade_destino": self.cidade_destino_var.get().strip(),
            "uf_destino": self.uf_destino_var.get().strip(),
            "placa": self.placa_var.get().strip(),
            "motorista": self.motorista_var.get().strip(),
            "data": self.data_var.get().strip(),
            "observacao": self.observacao_var.get().strip(),
        }

    def _executar_acao(
        self,
        acao,
        mensagem_padrao,
        limpar_apos_sucesso=False,
    ):
        """Captura os campos, chama o Controller e trata seu retorno."""

        try:
            dados = self._obter_dados_formulario()
            resultado = acao(dados)
        except Exception as erro:
            self._mostrar_status(f"Erro: {erro}", design.DANGER)
            return

        if not isinstance(resultado, dict):
            self._mostrar_status(
                "O Controller devolveu uma resposta inválida.",
                design.DANGER,
            )
            return

        self._mostrar_resultado(resultado, mensagem_padrao)

        if resultado.get("sucesso", False) and limpar_apos_sucesso:
            self._atualizar_cards_apos_cadastro(dados, resultado)
            dados_salvos = dict(resultado.get("dados") or dados)
            if dados_salvos.get("tipo_documento") == "NFE" and not self._campos_em_atualizacao:
                self._adicionar_notas_apos_cadastro(dados_salvos)
            imprimir = messagebox.askyesno(
                "Cadastro confirmado",
                "Cadastro realizado com sucesso.\n\nDeseja imprimir a etiqueta?",
                parent=self,
            )
            if imprimir:
                quantidade_plt = simpledialog.askinteger(
                    "Quantidade de paletes", "Quantos paletes deseja imprimir?",
                    parent=self, minvalue=1,
                )
                if quantidade_plt is not None:
                    vol = simpledialog.askinteger(
                        "Quantidade de volumes", "Quantos volumes?",
                        parent=self, minvalue=1,)
                else:
                    vol = None

                if quantidade_plt is not None and vol is not None:
                    # Primeiro prepara os nomes fiscais/de impressão originais.
                    dados_impressao = self._preparar_nomes_etiqueta(dados_salvos, dados)
                    if dados_impressao is not None:
                        if dados_salvos.get("tipo_documento") == "NFE":
                            notas = self.controller.notas_vinculadas(dados_salvos)
                            if notas:
                                numeros = " / ".join(n["numero_nf"] for n in notas)
                                dados_impressao["numero_nf"] = numeros
                                dados_impressao["numero_documento"] = numeros
                        # A pergunta e o modal ocorrem ANTES de chamar abrir_etiqueta.
                        redespacho = self._abrir_modal_redespacho()
                        if redespacho is not False:
                            if redespacho:
                                # Substituição exclusiva na cópia usada na etiqueta.
                                dados_impressao["redespacho"] = True
                                dados_impressao["destinatario"] = redespacho["nome_impressao"]
                                dados_impressao["cidade_destino"] = redespacho["cidade"]
                                dados_impressao["uf_destino"] = redespacho["uf"]
                            try:
                                abrir_etiqueta(dados_impressao, quantidade=quantidade_plt, volumes=vol)
                                self._mostrar_status(
                                    "Cadastro salvo. Etiqueta aberta no navegador para impressão.",
                                    design.SUCCESS,
                                )
                            except Exception as erro:
                                messagebox.showwarning(
                                    "Cadastro salvo — impressão não aberta",
                                    f"O documento já está salvo. Não cadastre novamente.\n\n{erro}",
                                    parent=self,
                                )
                    else:
                        self._mostrar_status(
                            "Documento salvo. Impressão cancelada pelo usuário.", design.MUTED
                        )
            self._clientes_cache = self.controller.consultar_clientes()
            self._limpar_formulario_principal()

    def _salvar_documento(self):
        """Cadastra um documento novo ou grava uma atualização solicitada."""
        campos = getattr(self, "_campos_em_atualizacao", set())
        documento = getattr(self, "documento_em_edicao", None)

        if documento and campos:
            self._executar_acao(
                lambda dados: self.controller.atualizar_documento(
                    documento.get("id"),
                    dados,
                    campos,
                ),
                "Não foi possível atualizar o documento.",
                limpar_apos_sucesso=True,
            )
            return

        self._executar_acao(
            self.controller.cadastrar,
            "Não foi possível cadastrar o CT-e.",
            limpar_apos_sucesso=True,
        )

    def _adicionar_notas_apos_cadastro(self, primeira):
        """Solicita as chaves adicionais; cada NF-e é um registro independente."""
        if not messagebox.askyesno(
            "NF-e adicionais", "Deseja adicionar outras NF-e a este carregamento?",
            parent=self,
        ):
            return
        grupo = primeira.get("carregamento_id") or primeira["id"]
        while True:
            chave = simpledialog.askstring(
                "Adicionar NF-e", "Leia ou digite a chave de 44 dígitos da próxima NF-e.\n"
                "Cancelar encerra a inclusão.", parent=self,
            )
            if chave is None:
                break
            chave = "".join(str(chave).split())
            resultado = self.controller.cadastrar_nfe_vinculada(
                {"codigo_barras": chave, "chave_original": primeira["codigo_barras"]}, grupo
            )
            if not resultado.get("sucesso"):
                messagebox.showwarning("NF-e não adicionada", resultado.get("mensagem"), parent=self)
                continue
            numero = resultado["dados"]["numero_nf"]
            if not messagebox.askyesno(
                "NF-e cadastrada", f"NF-e {numero} vinculada com sucesso.\n\nAdicionar outra?",
                parent=self,
            ):
                break

    def _abrir_modal_redespacho(self):
        """Busca redespacho no cadastro; se novo, cadastra antes da impressão."""
        resposta = messagebox.askyesnocancel(
            "Redespacho", "Esta entrega possui reespacho?\n\n"
            "Sim: selecionar ou cadastrar cliente.\n"
            "Não: manter destinatário.\nCancelar: não imprimir.", parent=self
        )
        if resposta is None:
            return False
        if not resposta:
            return None

        try:
            clientes = self.controller.consultar_clientes()
        except Exception as erro:
            messagebox.showerror("Redespacho", f"Erro ao consultar clientes: {erro}", parent=self)
            return False

        modal = tk.Toplevel(self)
        modal.title("Redespacho da etiqueta")
        modal.geometry("540x510")
        modal.resizable(False, False)
        modal.configure(bg=design.WHITE)
        modal.transient(self)
        modal.grab_set()
        self._centralizar_modal(modal, 540, 510)
        resultado = {"dados": False}
        nome_var = tk.StringVar(master=modal)
        nome_impressao_var = tk.StringVar(master=modal)
        uf_var = tk.StringVar(master=modal)
        cidade_var = tk.StringVar(master=modal)
        selecionado = {"cliente": None}

        area = tk.Frame(modal, bg=design.WHITE)
        area.pack(fill="both", expand=True, padx=24, pady=18)
        tk.Label(area, text="Cliente de redespacho", **design.SECTION_TITLE_STYLE).pack(anchor="w")
        tk.Label(area, text="Selecione um existente ou informe nome, UF e cidade para cadastrar.",
                 **design.LABEL_MUTED).pack(anchor="w", pady=(4, 12))
        bloco = tk.Frame(area, bg=design.WHITE)
        bloco.pack(fill="x", pady=(0, 10))
        tk.Label(bloco, text="Nome do redespacho", **design.LABEL_NORMAL).pack(anchor="w")
        campo_nome = ttk.Entry(bloco, textvariable=nome_var)
        campo_nome.pack(fill="x", pady=(4, 0))
        lista = tk.Listbox(bloco, height=5, exportselection=False)
        lista.pack(fill="x", pady=(3, 0))

        bloco_impressao = tk.Frame(area, bg=design.WHITE)
        bloco_impressao.pack(fill="x", pady=(0, 10))
        tk.Label(bloco_impressao, text="Nome para impressão (REDES)",
                 **design.LABEL_NORMAL).pack(anchor="w")
        campo_impressao = ttk.Entry(bloco_impressao, textvariable=nome_impressao_var)
        campo_impressao.pack(fill="x", pady=(4, 0))
        tk.Label(bloco_impressao,
                 text="Pode abreviar. O nome cadastrado do cliente não será alterado.",
                 **design.LABEL_MUTED).pack(anchor="w", pady=(3, 0))

        linha = tk.Frame(area, bg=design.WHITE)
        linha.pack(fill="x", pady=(0, 10))
        tk.Label(linha, text="UF", **design.LABEL_NORMAL).pack(side="left")
        combo_uf = ttk.Combobox(linha, textvariable=uf_var, values=Controller.UFS,
                                state="readonly", width=5)
        combo_uf.pack(side="left", padx=(8, 22))
        tk.Label(linha, text="Cidade", **design.LABEL_NORMAL).pack(side="left")
        combo_cidade = ttk.Combobox(linha, textvariable=cidade_var, state="normal")
        combo_cidade.pack(side="left", fill="x", expand=True, padx=(8, 0))
        aviso = tk.Label(area, text="", font=design.FONT_SMALL,
                         fg=design.DANGER, bg=design.WHITE, wraplength=470)
        aviso.pack(anchor="w")
        candidatos = []
        alterando = {"valor": False}
        ultimo_nome = {"valor": ""}

        def filtrar(*_):
            if alterando["valor"]:
                return
            selecionado["cliente"] = None
            nome_atual = nome_var.get()
            if nome_impressao_var.get() == ultimo_nome["valor"]:
                nome_impressao_var.set(nome_atual)
            ultimo_nome["valor"] = nome_atual
            lista.delete(0, tk.END)
            candidatos.clear()
            termo = self._normalizar_busca(nome_var.get())
            if len(termo) < 3:
                aviso.configure(text="Digite pelo menos 3 letras para pesquisar.")
                return
            candidatos.extend(c for c in clientes
                              if termo in self._normalizar_busca(c.get("nome", "")))
            for cliente in candidatos[:100]:
                lista.insert(tk.END, f'{cliente.get("nome", "")} — '
                            f'{cliente.get("cidade", "")}/{cliente.get("uf", "")}')
            aviso.configure(text="Selecione um cliente da lista." if candidatos
                            else "Não encontrado. Informe UF e cidade para cadastrar.")

        def escolher(event=None):
            indices = lista.curselection()
            if not indices or indices[0] >= min(len(candidatos), 100):
                return "break"
            cliente = candidatos[indices[0]]
            alterando["valor"] = True
            try:
                nome_var.set(str(cliente.get("nome") or ""))
                nome_impressao_var.set(
                    str(cliente.get("nome_etiqueta") or cliente.get("nome") or "")
                )
                ultimo_nome["valor"] = nome_var.get()
                uf_var.set(str(cliente.get("uf") or "").upper())
                cidade_var.set(str(cliente.get("cidade") or ""))
                selecionado["cliente"] = cliente
            finally:
                alterando["valor"] = False
            aviso.configure(text="Cliente cadastrado selecionado.")
            return "break"

        def atualizar_cidades(*_):
            cidades = self._cidades_por_uf.get(uf_var.get().upper(), [])
            termo = self._normalizar_busca(cidade_var.get())
            combo_cidade.configure(values=[c for c in cidades
                                           if not termo or termo in self._normalizar_busca(c)][:50])

        def confirmar():
            nome = nome_var.get().strip()
            nome_impressao = nome_impressao_var.get().strip()
            cidade = cidade_var.get().strip()
            uf = uf_var.get().strip().upper()
            if not nome or not cidade or uf not in Controller.UFS:
                messagebox.showwarning("Redespacho", "Informe nome, cidade e UF válida.", parent=modal)
                return
            if not nome_impressao:
                messagebox.showwarning("Redespacho", "Informe o nome para impressão.", parent=modal)
                campo_impressao.focus_set()
                return
            cliente = selecionado["cliente"]
            if cliente and (self._normalizar_busca(cliente.get("nome")) != self._normalizar_busca(nome)
                            or self._normalizar_busca(cliente.get("cidade")) != self._normalizar_busca(cidade)
                            or str(cliente.get("uf", "")).upper() != uf):
                cliente = None
            if cliente is None:
                if not messagebox.askyesno("Cadastrar redespacho",
                    f"Cadastrar como cliente?\n\n{nome}\n{cidade}/{uf}", parent=modal):
                    return
                try:
                    cliente = self.controller.cadastrar_cliente(nome, cidade, uf)
                    self._recarregar_clientes()
                except Exception as erro:
                    messagebox.showerror("Erro no cadastro", str(erro), parent=modal)
                    return
            resultado["dados"] = {
                "nome": str(cliente.get("nome") or nome).strip(),
                "nome_impressao": nome_impressao,
                "cidade": str(cliente.get("cidade") or cidade).strip(),
                "uf": str(cliente.get("uf") or uf).strip().upper(),
            }
            modal.destroy()

        nome_var.trace_add("write", filtrar)
        cidade_var.trace_add("write", atualizar_cidades)
        combo_uf.bind("<<ComboboxSelected>>", lambda e: (cidade_var.set(""), atualizar_cidades()))
        lista.bind("<<ListboxSelect>>", escolher)
        lista.bind("<Double-1>", escolher)
        lista.bind("<Return>", escolher)
        botoes = tk.Frame(area, bg=design.WHITE)
        botoes.pack(side="bottom", fill="x")
        tk.Button(botoes, text="Cancelar", command=modal.destroy,
                  **design.BUTTON_OUTLINE).pack(side="left", fill="x", expand=True, padx=(0, 5))
        tk.Button(botoes, text="Confirmar", command=confirmar,
                  **design.BUTTON_PRIMARY).pack(side="left", fill="x", expand=True, padx=(5, 0))
        campo_nome.focus_set()
        modal.wait_window()
        return resultado["dados"]

    def _preparar_nomes_etiqueta(self, dados_salvos, dados_formulario):
        """Permite revisar nomes impressos e persiste alterações por ID de cliente.

        Não modifica o nome fiscal armazenado no documento ou em clientes.nome.
        Retorna uma cópia dos dados para impressão ou None ao cancelar.
        """
        dados_impressao = dict(dados_salvos)
        clientes = {}
        nomes_iniciais = {}

        for tipo, local in (("remetente", "origem"), ("destinatario", "destino")):
            nome = str(dados_salvos.get(tipo) or dados_formulario.get(tipo) or "").strip()
            cliente_id = (dados_formulario.get(f"id_{tipo}")
                          or dados_salvos.get(f"id_{tipo}"))
            cidade = (dados_salvos.get(f"cidade_{local}")
                      or dados_formulario.get(f"cidade_{local}") or "")
            uf = (dados_salvos.get(f"uf_{local}")
                  or dados_formulario.get(f"uf_{local}") or "")
            cliente = self.controller.localizar_cliente_etiqueta(
                nome, cidade=cidade, uf=uf, cliente_id=cliente_id
            )
            clientes[tipo] = cliente
            nomes_iniciais[tipo] = (
                str(cliente.get("nome_etiqueta") or "").strip() if cliente else ""
            ) or nome

        modal = tk.Toplevel(self)
        modal.title("Nomes para impressão da etiqueta")
        modal.geometry("560x310")
        modal.resizable(False, False)
        modal.configure(bg=design.WHITE)
        modal.transient(self)
        modal.grab_set()
        self._centralizar_modal(modal, 560, 310)
        resultado = {"confirmado": False}
        variaveis = {}
        area = tk.Frame(modal, bg=design.WHITE)
        area.pack(fill="both", expand=True, padx=24, pady=18)
        tk.Label(area, text="Nomes que serão impressos",
                 **design.SECTION_TITLE_STYLE).pack(anchor="w")
        tk.Label(area, text="Edite somente se desejar abreviar. O nome cadastrado não será alterado.",
                 **design.LABEL_MUTED).pack(anchor="w", pady=(4, 15))
        for tipo, titulo in (("remetente", "Remetente (REM)"),
                             ("destinatario", "Destinatário (DES)")):
            variavel = tk.StringVar(master=modal, value=nomes_iniciais[tipo])
            variaveis[tipo] = variavel
            self._criar_campo_modal(area, titulo, variavel)

        def confirmar():
            nomes = {tipo: variaveis[tipo].get().strip() for tipo in variaveis}
            if not all(nomes.values()):
                messagebox.showwarning("Nome obrigatório",
                                       "Informe os nomes de remetente e destinatário.", parent=modal)
                return
            try:
                for tipo, nome_impressao in nomes.items():
                    cliente = clientes[tipo]
                    if cliente and str(cliente.get("id") or "").strip():
                        # Só persiste quando o nome foi efetivamente alterado.
                        if nome_impressao != nomes_iniciais[tipo]:
                            salvo = self.controller.atualizar_nome_etiqueta(
                                cliente["id"], nome_impressao
                            )
                            if salvo is False:
                                raise ValueError(f"Não foi possível atualizar {tipo}.")
                    dados_impressao[tipo] = nome_impressao
            except Exception as erro:
                messagebox.showerror("Erro ao salvar nome da etiqueta", str(erro), parent=modal)
                return
            resultado["confirmado"] = True
            modal.destroy()

        botoes = tk.Frame(area, bg=design.WHITE)
        botoes.pack(side="bottom", fill="x", pady=(8, 0))
        tk.Button(botoes, text="Cancelar", command=modal.destroy,
                  **design.BUTTON_OUTLINE).pack(side="left", fill="x", expand=True, padx=(0, 5))
        tk.Button(botoes, text="Salvar e imprimir", command=confirmar,
                  **design.BUTTON_PRIMARY).pack(side="left", fill="x", expand=True, padx=(5, 0))
        modal.wait_window()
        return dados_impressao if resultado["confirmado"] else None

    # --------------------------------------------------------
    # MODAL DE MOTORISTA E PLACA
    # --------------------------------------------------------
    def _abrir_modal_motorista(self):
        """Permite selecionar um motorista existente ou digitar um novo."""
        if self.modal_motorista and self.modal_motorista.winfo_exists():
            self.modal_motorista.lift()
            self.modal_motorista.focus_force()
            return

        # Consulta pelo Controller antes de abrir o modal.
        try:
            motoristas = self.controller.listar_motoristas()
        except Exception as erro:
            self._mostrar_status(
                f"Erro ao carregar motoristas: {erro}",
                design.DANGER,
            )
            return

        # O Controller devolve registros no formato
        # {"nome": "...", "rg": "..."}. O Combobox trabalha apenas
        # com textos; convertemos para a lista de nomes preservando também
        # compatibilidade com versões antigas que já retornavam strings.
        nomes_motoristas = []
        for motorista in motoristas:
            nome = (
                motorista.get("nome", "")
                if isinstance(motorista, dict)
                else str(motorista or "")
            ).strip()
            if nome and nome.casefold() not in {
                item.casefold() for item in nomes_motoristas
            }:
                nomes_motoristas.append(nome)

        modal = tk.Toplevel(self)
        self.modal_motorista = modal

        modal.title("Cadastro de motorista e placa")
        modal.geometry("480x420")
        modal.resizable(False, False)
        modal.configure(bg=design.WHITE)
        modal.transient(self)
        modal.grab_set()
        modal.protocol(
            "WM_DELETE_WINDOW",
            self._fechar_modal_motorista,
        )

        self._centralizar_modal(modal, 480, 420)

        placa_modal_var = tk.StringVar(
            master=modal,
            value=self.placa_var.get(),
        )
        motorista_modal_var = tk.StringVar(
            master=modal,
            value=self.motorista_var.get(),
        )

        container = tk.Frame(modal, bg=design.WHITE)
        container.pack(
            fill="both",
            expand=True,
            padx=28,
            pady=24,
        )

        tk.Label(
            container,
            text="Cadastrar motorista e placa",
            **design.SECTION_TITLE_STYLE,
        ).pack(anchor="w")

        tk.Label(
            container,
            text="Placa existente: atualiza o motorista vinculado.",
            **design.LABEL_MUTED,
        ).pack(anchor="w", pady=(3, 18))

        placa_entry = self._criar_campo_modal(
            container,
            "Placa",
            placa_modal_var,
        )

        # Combobox editável: seleção ou digitação de um nome novo.
        bloco_motorista = tk.Frame(
            container,
            bg=design.WHITE,
        )
        bloco_motorista.pack(fill="x", pady=(0, 14))

        tk.Label(
            bloco_motorista,
            text="Motorista",
            font=design.FONT_LABEL,
            fg=design.TEXT,
            bg=design.WHITE,
        ).pack(anchor="w", pady=(0, 5))

        motorista_entry = ttk.Combobox(
            bloco_motorista,
            textvariable=motorista_modal_var,
            values=nomes_motoristas,
            state="normal",
            height=8,
        )
        motorista_entry.pack(fill="x")

        tk.Label(
            bloco_motorista,
            text="Digite para filtrar e abra a seta para selecionar.\n"
                 "Para cadastrar, digite um nome novo e clique em Salvar.",
            **design.LABEL_MUTED,
        ).pack(anchor="w", pady=(5, 0))

        mensagem_label = tk.Label(
            container,
            text="",
            font=design.FONT_SMALL,
            fg=design.DANGER,
            bg=design.WHITE,
            anchor="w",
            justify="left",
            wraplength=420,
        )
        mensagem_label.pack(fill="x", pady=(2, 12))

        def filtrar_motoristas(*args):
            termo = motorista_modal_var.get().strip().casefold()

            encontrados = [
                nome
                for nome in nomes_motoristas
                if termo in nome.casefold()
            ]

            motorista_entry.configure(values=encontrados)
            mensagem_label.configure(text="")

        motorista_modal_var.trace_add(
            "write",
            filtrar_motoristas,
        )

        def salvar(event=None):
            # Usa a grafia do cadastro existente quando o nome coincide.
            nome_digitado = motorista_modal_var.get().strip()

            for nome in nomes_motoristas:
                if nome.casefold() == nome_digitado.casefold():
                    motorista_modal_var.set(nome)
                    break

            self._salvar_motorista_modal(
                placa_modal_var,
                motorista_modal_var,
                mensagem_label,
            )
            return "break"

        botoes_modal = tk.Frame(container, bg=design.WHITE)
        botoes_modal.pack(side="bottom", fill="x")

        tk.Button(
            botoes_modal,
            text="Cancelar",
            command=self._fechar_modal_motorista,
            **design.BUTTON_OUTLINE,
        ).pack(
            side="left",
            fill="x",
            expand=True,
            padx=(0, 5),
        )

        tk.Button(
            botoes_modal,
            text="Salvar",
            command=salvar,
            **design.BUTTON_PRIMARY,
        ).pack(
            side="left",
            fill="x",
            expand=True,
            padx=(5, 0),
        )

        placa_entry.bind(
            "<FocusOut>",
            lambda event: placa_modal_var.set(
                self._normalizar_placa(placa_modal_var.get())
            ),
        )

        def focar_motorista(event=None):
            motorista_entry.focus_set()
            return "break"

        placa_entry.bind("<Return>", focar_motorista)

        # No Combobox, Enter fica disponível para selecionar um nome.
        # A gravação é feita pelo botão Salvar.
        placa_entry.focus_set()

    def _criar_campo_modal(self, parent, titulo, variavel):
        bloco = tk.Frame(parent, bg=design.WHITE)
        bloco.pack(fill="x", pady=(0, 14))

        tk.Label(
            bloco,
            text=titulo,
            font=design.FONT_LABEL,
            fg=design.TEXT,
            bg=design.WHITE,
        ).pack(anchor="w", pady=(0, 5))

        entrada = ttk.Entry(bloco, textvariable=variavel)
        entrada.pack(fill="x")
        return entrada

    def _fechar_modal_motorista(self):
        if self.modal_motorista and self.modal_motorista.winfo_exists():
            self.modal_motorista.grab_release()
            self.modal_motorista.destroy()

        self.modal_motorista = None

    def _centralizar_modal(self, modal, largura, altura):
        self.update_idletasks()
        posicao_x = self.winfo_rootx() + (self.winfo_width() - largura) // 2
        posicao_y = self.winfo_rooty() + (self.winfo_height() - altura) // 2
        modal.geometry(f"{largura}x{altura}+{posicao_x}+{posicao_y}")

    @staticmethod
    def _normalizar_placa(valor):
        placa = str(valor).strip().upper()
        placa = placa.replace("-", "").replace(" ", "")
        return f"{placa[:3]}-{placa[3:]}" if len(placa) == 7 else placa

    def _limpar_ajuda_chave(self, event=None):
        """Apaga a orientação antes do primeiro caractere ou colagem."""
        if self.codigo_var.get() != self.placeholder_ajuda:
            return
        # Ignora teclas de navegação; mantém o texto até começar a entrada.
        if event is not None and event.type == tk.EventType.KeyPress:
            if event.keysym in {"Tab", "Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R", "Left", "Right", "Up", "Down"}:
                return
        self.codigo_var.set("")

    def _limpar_chave_ao_digitar_numero(self, event=None):
        """Remove a orientação da chave ao iniciar consulta pelo número."""
        if self.codigo_var.get() != self.placeholder_ajuda:
            return
        if event is not None and event.type == tk.EventType.KeyPress:
            if event.keysym in {
                "Tab", "Shift_L", "Shift_R", "Control_L", "Control_R",
                "Alt_L", "Alt_R", "Left", "Right", "Up", "Down",
                "Home", "End", "Escape",
            }:
                return
        self.codigo_var.set("")

    def _buscar_chave_completa(self):
        """Extrai o número e consulta exclusivamente a chave de 44 dígitos."""
        self._consulta_chave_agendada = None
        codigo = self.codigo_var.get().strip()
        if len(codigo) != 44 or not codigo.isascii() or not codigo.isdecimal():
            return
        if self._extrair_numero_cte_nfe():
            self._consultar(somente_chave=True)

    def _ao_confirmar_codigo(self, event=None):
        """Confirma a leitura manual ou por scanner que envia Enter."""
        if self._consulta_chave_agendada is not None:
            self.after_cancel(self._consulta_chave_agendada)
            self._consulta_chave_agendada = None
        codigo = self.codigo_var.get().strip()
        if len(codigo) != 44 or not codigo.isascii() or not codigo.isdecimal():
            self._mostrar_status("Informe uma chave de 44 dígitos numéricos.", design.DANGER)
        else:
            self._buscar_chave_completa()
        return "break"

    def _consultar(self, somente_chave=False):
        """Consulta documentos e permite iniciar uma nova consulta."""
        try:
            filtros = self._obter_dados_formulario()
            if somente_chave:
                filtros = {"codigo_barras": filtros["codigo_barras"]}
            elif filtros["codigo_barras"] == self.placeholder_ajuda:
                filtros["codigo_barras"] = ""
            resultado = self.controller.consultar(filtros)
        except Exception as erro:
            self._mostrar_status(
                f"Erro ao consultar: {erro}",
                design.DANGER,
            )
            return

        # Valida a resposta do Controller.
        if not isinstance(resultado, dict):
            self._mostrar_status(
                "O Controller devolveu uma resposta inválida.",
                design.DANGER,
            )
            return

        mensagem = resultado.get("mensagem") or "Consulta realizada."

        if not resultado.get("sucesso", False):
            self._mostrar_status(mensagem, design.DANGER)
            return

        registros = resultado.get("dados")

        if isinstance(registros, dict):
            registros = [registros]

        if registros is None:
            registros = []

        if not isinstance(registros, list) or any(
            not isinstance(registro, dict)
            for registro in registros
        ):
            self._mostrar_status(
                "Os dados retornados pelo Controller são inválidos.",
                design.DANGER,
            )
            return

        if not registros:
            self._mostrar_status(
                "Nenhum documento encontrado.",
                design.DANGER,
            )
            return

        # Vários documentos: a seleção acontece no modal.
        if len(registros) > 1:
            self._mostrar_status(mensagem, design.SUCCESS)
            self._abrir_modal_resultados(registros)
            return

        # Um documento: preenche o formulário e registra sua identidade
        # original para uma possível atualização.
        registro = registros[0]

        self._preencher_formulario(registro)
        self._mostrar_status(mensagem, design.SUCCESS)

        # Guarda a identidade original do documento.
        self.documento_em_edicao = {
            "id": registro.get("id"),
            "codigo_barras": registro.get("codigo_barras"),
        }

        # Ao escolher atualizar, os campos são liberados para edição. Não
        # perguntamos por nova consulta nesse momento, pois ela apagaria os
        # dados antes da correção ser gravada.
        atualizando = self._perguntar_atualizacao_documento()
        if not atualizando:
            self._perguntar_nova_consulta()
    def _formatar_placa(self, event=None):
        self.placa_var.set(self._normalizar_placa(self.placa_var.get()))

    def _mostrar_resultado(self, resultado, mensagem_padrao):
        if isinstance(resultado, dict):
            sucesso = resultado.get("sucesso", False)
            mensagem = resultado.get("mensagem", mensagem_padrao)
            cor = design.SUCCESS if sucesso else design.DANGER
        else:
            mensagem = str(resultado) if resultado else mensagem_padrao
            cor = design.DANGER

        self._mostrar_status(mensagem, cor)

    def _mostrar_status(self, texto, cor=design.MUTED):
        self.status_label.config(text=f"● {texto}" if texto else "", fg=cor)

    def _atualizar_relogio(self):
        agora = datetime.now()
        self.relogio_label.config(text=agora.strftime("%d/%m/%Y  •  %H:%M:%S"))
        #self.hora_label.config(text=agora.strftime("Hora atual: %H:%M:%S"))
        self.after(1000, self._atualizar_relogio)
    def _extrair_numero_cte_nfe(self):
        """Uma chave identifica um documento: NF-e ou CT-e."""
        self.numero_documento_var.set("")
        self.numero_documento_entry.configure(state="normal", style="TEntry")
        codigo = self.codigo_var.get().strip()
        if not codigo:
            self._mostrar_status("", design.MUTED)
            return False
        try:
            resultado = self.controller.extrair_numero_cte_nf(codigo)
        except Exception as erro:
            self._mostrar_status(f"Erro: {erro}", design.DANGER)
            return False
        if not isinstance(resultado, dict):
            self._mostrar_status("Resposta inválida do Controller.", design.DANGER)
            return False
        if not resultado.get("sucesso"):
            self._mostrar_resultado(resultado, "Chave inválida.")
            return False
        self.numero_documento_var.set(resultado.get("numero_cte") or resultado.get("numero_nf") or "")
        self.numero_documento_entry.configure(state="readonly", style="Data.TEntry")
        self.data_var.set(datetime.now().strftime("%d/%m/%Y"))
        self.data_entry.configure(state="readonly", style="Data.TEntry")
        self._mostrar_status("", design.MUTED)
        return True

    def _consultar_motorista_placa(self, event=None):
        """Consulta o motorista vinculado à placa informada."""
        placa = self._normalizar_placa(self.placa_var.get())
        self.placa_var.set(placa)



        if not placa:
            self.motorista_var.set("")
            self._mostrar_status("Informe uma placa.", design.DANGER)
            return "break"

        try:
            resultado = self.controller.consultar_motorista_por_placa(placa)
        except Exception as erro:
            self.motorista_var.set("")
            self._mostrar_status(f"Erro ao consultar placa: {erro}", design.DANGER)
            return "break"

        if not isinstance(resultado, dict):
            self.motorista_var.set("")
            self._mostrar_status(
                "O Controller devolveu uma resposta inválida.",
                design.DANGER,
            )
            return "break"

        dados = resultado.get("dados") or {}
        if resultado.get("sucesso", False):
            motorista = dados.get("motorista", "")
            placa_encontrada = dados.get("placa", placa)
            self.motorista_var.set(motorista)

        else:
            self.motorista_var.set("")

        self._mostrar_resultado(
            resultado,
            "Não foi possível consultar a placa.",
        )

        return "break"

    def _salvar_motorista_modal(
            self,
            placa_variavel,
            motorista_variavel,
            mensagem_label,
    ):
        """Cadastra uma placa nova ou atualiza seu motorista."""

        placa = self._normalizar_placa(placa_variavel.get())
        motorista = motorista_variavel.get().strip()

        if not placa:
            mensagem_label.config(
                text="● Informe a placa.",
                fg=design.DANGER,
            )
            return

        if not motorista:
            mensagem_label.config(
                text="● Informe o nome do motorista.",
                fg=design.DANGER,
            )
            return

        dados = {
            "placa": placa,
            "motorista": motorista,
        }

        try:
            resultado = self.controller.atualizar_motorista(dados)
        except Exception as erro:
            resultado = {
                "sucesso": False,
                "mensagem": f"Erro ao salvar motorista: {erro}",
            }

        if not isinstance(resultado, dict):
            resultado = {
                "sucesso": False,
                "mensagem": "O Controller devolveu uma resposta inválida.",
            }

        sucesso = resultado.get("sucesso", False)
        mensagem = resultado.get(
            "mensagem",
            "Não foi possível salvar o motorista.",
        )

        cor = design.SUCCESS if sucesso else design.DANGER
        mensagem_label.config(text=f"● {mensagem}", fg=cor)

        if not sucesso:
            return

        dados_salvos = resultado.get("dados") or dados

        # Atualiza os campos da tela principal.
        self.placa_var.set(
            dados_salvos.get("placa", placa)
        )
        self.motorista_var.set(
            dados_salvos.get("motorista", motorista)
        )

        self._mostrar_status(mensagem, design.SUCCESS)

        self._fechar_modal_motorista()

    def _atualizar_cards_apos_cadastro(self, dados_enviados, resultado):
        """Atualiza os quatro cards com o documento recém-gravado."""
        dados_salvos = dict(resultado.get("dados") or {})
        for campo in ("numero_documento", "numero_cte", "numero_nf",
                      "remetente", "motorista", "placa"):
            if not dados_salvos.get(campo):
                dados_salvos[campo] = dados_enviados.get(campo)
        self._atualizar_cards_documento(dados_salvos)

    def _limpar_formulario_principal(self):
        """Limpa o formulário somente após o cadastro bem-sucedido."""
        self.destinatario_var.set("")
        self.cidade_origem_var.set("")
        self.uf_origem_var.set("")
        self.cidade_destino_var.set("")
        self.uf_destino_var.set("")
        self.remetente_var.set("")
        self.codigo_var.set("")
        self.numero_documento_var.set("")
        self.placa_var.set("")
        self.motorista_var.set("")
        self.observacao_var.set("")
        self.data_var.set(self.placeholder_data)
        self.data_entry.configure(state="normal", style="TEntry")

        self.numero_documento_entry.configure(
            state="normal",
            style="TEntry",
        )
        self.motorista_entry.configure(
            state="readonly",
            style="Data.TEntry",
        )
        self.placa_entry.configure(state="normal", style="TEntry")
        self.remetente_entry.configure(state="normal", style="TEntry")
        self.destinatario_entry.configure(state="normal", style="TEntry")
        self.documento_em_edicao = None
        self._campos_em_atualizacao = set()
        if hasattr(self, "botao_cadastrar"):
            self.botao_cadastrar.configure(text="Cadastrar")

        for tipo in ("remetente", "destinatario"):
            self._clientes_selecionados[tipo] = None
            self._avisos_cliente[tipo].configure(text="")
        self.update_idletasks()
        self.codigo_entry.focus_set()

    # --------------------------------------------------------
    # RESULTADOS DA CONSULTA DE DOCUMENTOS
    # --------------------------------------------------------
    def _preencher_formulario(self, dados):
        """Preenche a tela principal com o documento selecionado."""
        if not isinstance(dados, dict):
            self._mostrar_status(
                "Os dados do documento são inválidos.",
                design.DANGER,
            )
            return

        self.destinatario_var.set(dados.get("destinatario", ""))
        self.uf_origem_var.set(dados.get("uf_origem", ""))
        self.cidade_origem_var.set(dados.get("cidade_origem", ""))
        self.uf_destino_var.set(dados.get("uf_destino", ""))
        self.cidade_destino_var.set(dados.get("cidade_destino", ""))
        self.remetente_var.set(dados.get("remetente", ""))
        self._preenchendo_documento = True
        try:
            self.codigo_var.set(dados.get("codigo_barras", ""))
        finally:
            self._preenchendo_documento = False
        self.numero_documento_var.set(dados.get("numero_documento") or dados.get("numero_cte") or dados.get("numero_nf", ""))
        self.placa_var.set(dados.get("placa", ""))
        self.motorista_var.set(dados.get("motorista", ""))
        self.data_var.set(dados.get("data", ""))
        self.observacao_var.set(self.controller.observacao_com_notas(dados))

        # Os cards mostram o último cadastro, não o documento consultado.

        # Dados encontrados no banco não devem ser alterados diretamente.
        self.numero_documento_entry.configure(
            state="readonly",
            style="Data.TEntry",
        )
        self.remetente_entry.configure(state="readonly", style="Data.TEntry")
        self.destinatario_entry.configure(state="readonly", style="Data.TEntry")
        self.placa_entry.configure(state="readonly", style="Data.TEntry")
        self.motorista_entry.configure(
            state="readonly",
            style="Data.TEntry",
        )

    def _abrir_modal_resultados(self, registros):
        """Exibe uma tabela quando a consulta encontra vários documentos."""
        if self.modal_resultados and self.modal_resultados.winfo_exists():
            self.modal_resultados.lift()
            self.modal_resultados.focus_force()
            return

        modal = tk.Toplevel(self)
        self.modal_resultados = modal

        modal.title("Resultados da consulta")
        modal.geometry("900x420")
        modal.minsize(720, 360)
        modal.configure(bg=design.WHITE)
        modal.transient(self)
        modal.grab_set()
        modal.protocol("WM_DELETE_WINDOW", self._fechar_modal_resultados)

        self._centralizar_modal(modal, 900, 420)

        container = tk.Frame(modal, bg=design.WHITE)
        container.pack(fill="both", expand=True, padx=20, pady=20)

        tk.Label(
            container,
            text=f"{len(registros)} documentos encontrados",
            **design.SECTION_TITLE_STYLE,
        ).pack(anchor="w", pady=(0, 12))

        # A tabela mostra somente os campos necessários para escolher.
        colunas = (
            "numero_cte",
            "remetente",
            "placa",
            "motorista",
            "data",
        )

        area_tabela = tk.Frame(container, bg=design.WHITE)
        area_tabela.pack(fill="both", expand=True)

        tabela = ttk.Treeview(
            area_tabela,
            columns=colunas,
            show="headings",
            selectmode="browse",
        )
        rolagem = ttk.Scrollbar(
            area_tabela,
            orient="vertical",
            command=tabela.yview,
        )
        tabela.configure(yscrollcommand=rolagem.set)

        tabela.heading("numero_cte", text="NF-e / CT-e")
        tabela.heading("remetente", text="Remetente")
        tabela.heading("placa", text="Placa")
        tabela.heading("motorista", text="Motorista")
        tabela.heading("data", text="Data")

        tabela.column("numero_cte", width=90, anchor="center")
        tabela.column("remetente", width=230)
        tabela.column("placa", width=100, anchor="center")
        tabela.column("motorista", width=180)
        tabela.column("data", width=100, anchor="center")

        tabela.pack(side="left", fill="both", expand=True)
        rolagem.pack(side="right", fill="y")

        # O iid guarda o índice do registro correspondente na lista.
        for indice, registro in enumerate(registros):
            tabela.insert(
                "",
                "end",
                iid=str(indice),
                values=(
                    (registro.get("tipo_documento", "CTE") + " " + (registro.get("numero_documento") or registro.get("numero_cte", ""))),
                    registro.get("remetente", ""),
                    registro.get("placa", ""),
                    registro.get("motorista", ""),
                    registro.get("data", ""),
                ),
            )

        def selecionar_documento(event=None):
            """Carrega o registro selecionado na tela principal."""
            selecionados = tabela.selection()

            if not selecionados:
                self._mostrar_status(
                    "Selecione um documento.",
                    design.DANGER,
                )
                return

            indice = int(selecionados[0])
            documento = registros[indice]

            # Preenche os campos da tela principal.
            self._preencher_formulario(documento)
            self.documento_em_edicao = {
                "id": documento.get("id"),
                "codigo_barras": documento.get("codigo_barras"),
            }

            # Fecha somente o modal de resultados.
            self._fechar_modal_resultados()

            # Apaga a mensagem, mantendo os dados preenchidos.
            self.status_label.configure(text="")

            self.lift()
            atualizando = self._perguntar_atualizacao_documento()
            if not atualizando:
                self._perguntar_nova_consulta()

        # Fora da função, ainda dentro de _abrir_modal_resultados.
        tabela.bind("<Double-1>", selecionar_documento)
        tabela.bind("<Return>", selecionar_documento)

        botoes = tk.Frame(container, bg=design.WHITE)
        botoes.pack(fill="x", pady=(12, 0))
        tk.Button(botoes, text="Cancelar", command=self._fechar_modal_resultados,
                  **design.BUTTON_OUTLINE).pack(side="right", padx=(8, 0))
        tk.Button(botoes, text="Selecionar", command=selecionar_documento,
                  **design.BUTTON_PRIMARY).pack(side="right")
        if registros:
            tabela.selection_set("0")
            tabela.focus("0")
        tabela.focus_set()

    def _fechar_modal_resultados(self):

        """Fecha o modal de consulta e libera a janela principal."""
        if self.modal_resultados and self.modal_resultados.winfo_exists():
            self.modal_resultados.grab_release()
            self.modal_resultados.destroy()

        self.modal_resultados = None

    def _perguntar_nova_consulta(self):
        nova_consulta = messagebox.askyesno(
            "Nova consulta",
            "Deseja efetuar uma nova consulta?\n\n"
            "Sim: limpa o formulário.\n"
            "Não: mantém os dados.",
            parent=self,
        )

        if nova_consulta:
            self._limpar_formulario_principal()
            self.remetente_entry.focus_set()

        self.status_label.configure(text="")

    def _recuperar_etiqueta(self):
        """Recupera a etiqueta do documento atual."""

        dados = self._obter_dados_formulario()

        recuperar_etiqueta(dados, parent=self)
        self._limpar_formulario_principal()

    def _perguntar_atualizacao_documento(self):
        """Pergunta quais dados do documento serão atualizados."""

        modal = tk.Toplevel(self)
        modal.title("Atualizar documento")
        modal.geometry("360x310")
        modal.resizable(False, False)
        modal.transient(self)
        modal.grab_set()
        modal.protocol("WM_DELETE_WINDOW", modal.destroy)

        tk.Label(
            modal,
            text="Deseja atualizar os dados?",
            font=("Arial", 12, "bold")
        ).pack(pady=15)

        atualizar_remetente = tk.BooleanVar(value=False)
        atualizar_destinatario = tk.BooleanVar(value=False)
        atualizar_placa = tk.BooleanVar(value=False)
        modal.atualizando = False

        tk.Checkbutton(
            modal,
            text="Remetente",
            variable=atualizar_remetente
        ).pack(anchor="w", padx=35, pady=5)

        tk.Checkbutton(
            modal,
            text="Destinatário",
            variable=atualizar_destinatario
        ).pack(anchor="w", padx=35, pady=5)

        tk.Checkbutton(
            modal,
            text="Placa e motorista",
            variable=atualizar_placa
        ).pack(anchor="w", padx=35, pady=5)

        def confirmar():
            campos = {
                "remetente": atualizar_remetente.get(),
                "destinatario": atualizar_destinatario.get(),
                "placa": atualizar_placa.get(),
            }

            if not any(campos.values()):
                messagebox.showwarning(
                    "Atualização",
                    "Selecione pelo menos um campo.",
                    parent=modal
                )
                return

            self._habilitar_campos_atualizacao(campos)
            modal.atualizando = True
            modal.destroy()

        tk.Button(
            modal,
            text="Atualizar",
            command=confirmar
        ).pack(pady=10)

        tk.Button(
            modal,
            text="Não atualizar",
            command=modal.destroy
        ).pack()

        # Mantém a execução neste ponto até o usuário fechar o modal. Assim,
        # a pergunta "Nova consulta" não é exibida junto deste modal.
        modal.wait_window()
        return modal.atualizando

    def _habilitar_campos_atualizacao(self, campos):
        """Libera apenas os dados escolhidos para correção do documento."""
        self._campos_em_atualizacao = {
            campo for campo, selecionado in campos.items() if selecionado
        }

        if campos.get("remetente"):
            self.remetente_entry.configure(state="normal", style="TEntry")

        if campos.get("destinatario"):
            self.destinatario_entry.configure(state="normal", style="TEntry")

        if campos.get("placa"):
            # Placa e motorista formam um vínculo: a correção libera os dois.
            self.placa_entry.configure(state="normal", style="TEntry")
            self.motorista_entry.configure(state="normal", style="TEntry")

        if hasattr(self, "botao_cadastrar"):
            self.botao_cadastrar.configure(text="Salvar atualização")

        self._mostrar_status(
            "Corrija os campos liberados e clique em Salvar atualização.",
            design.SUCCESS,
        )

