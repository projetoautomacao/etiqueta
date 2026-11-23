from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
import sqlite3


class SQLiteRepository:
    """Repositório responsável pelo acesso ao banco SQLite."""

    def __init__(self, caminho=None):
        self.caminho = (
            Path(caminho)
            if caminho
            else Path(__file__).resolve().parents[1]
            / "dados"
            / "controle_entrega.db"
        )

        self.caminho.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        # Cria as tabelas caso ainda não existam.
        with self.conectar() as con:
            con.executescript(
                """
                CREATE TABLE IF NOT EXISTS motoristas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome TEXT NOT NULL,
                    rg TEXT UNIQUE
                );

                CREATE TABLE IF NOT EXISTS clientes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome TEXT NOT NULL,
                    cpf_cnpj TEXT UNIQUE,
                    cidade TEXT NOT NULL,
                    uf TEXT NOT NULL
                        CHECK (
                            length(uf) = 2
                            AND uf = upper(uf)
                        ),
                    nome_etiqueta TEXT DEFAULT NULL
                );

                CREATE TABLE IF NOT EXISTS veiculos (
                    placa TEXT PRIMARY KEY,
                    motorista_id INTEGER NOT NULL,

                    FOREIGN KEY (motorista_id)
                        REFERENCES motoristas(id)
                );

                CREATE TABLE IF NOT EXISTS documentos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    id_remetente INTEGER,
                    id_destinatario INTEGER,

                    codigo_barras TEXT NOT NULL UNIQUE,

                    numero_cte TEXT NOT NULL DEFAULT '',
                    numero_nf TEXT NOT NULL DEFAULT '',

                    tipo_documento TEXT NOT NULL DEFAULT '',
                    numero_documento TEXT NOT NULL DEFAULT '',

                    remetente TEXT NOT NULL DEFAULT '',
                    destinatario TEXT NOT NULL DEFAULT '',

                    cidade_origem TEXT NOT NULL DEFAULT '',
                    uf_origem TEXT NOT NULL DEFAULT '',

                    cidade_destino TEXT NOT NULL DEFAULT '',
                    uf_destino TEXT NOT NULL DEFAULT '',

                    placa TEXT NOT NULL,
                    motorista TEXT NOT NULL DEFAULT '',
                    motorista_id INTEGER,

                    data TEXT NOT NULL DEFAULT '',
                    observacao TEXT NOT NULL DEFAULT '',

                    FOREIGN KEY (id_remetente)
                        REFERENCES clientes(id),

                    FOREIGN KEY (id_destinatario)
                        REFERENCES clientes(id),

                    FOREIGN KEY (placa)
                        REFERENCES veiculos(placa),

                    FOREIGN KEY (motorista_id)
                        REFERENCES motoristas(id)
                );

                """
            )

        # Atualiza bancos criados em versões anteriores.
        self._migrar_documentos()
        self._migrar_cpf_opcional()
        self._migrar_carregamentos()

    # ==========================================================
    # CONEXÃO
    # ==========================================================

    @contextmanager
    def conectar(self):
        """Abre uma conexão SQLite com configurações padrão."""

        con = sqlite3.connect(
            self.caminho,
            timeout=10,
        )

        con.row_factory = sqlite3.Row

        # Ativa as chaves estrangeiras.
        con.execute(
            "PRAGMA foreign_keys = ON"
        )

        # Função utilizada nas consultas de texto.
        con.create_function(
            "MAIUSCULA",
            1,
            lambda valor: str(valor or "").upper(),
        )

        try:
            with con:
                yield con

        finally:
            con.close()

    # ==========================================================
    # MIGRAÇÃO
    # ==========================================================

    def _migrar_documentos(self):
        """
        Atualiza bancos antigos sem apagar os dados existentes.

        Antes de alterar a estrutura do banco é criado um backup.
        """

        with self.conectar() as con:

            # --------------------------------------------------
            # MOTORISTAS
            # --------------------------------------------------

            colunas_motoristas = {
                linha["name"]
                for linha in con.execute(
                    "PRAGMA table_info(motoristas)"
                )
            }

            if "rg" not in colunas_motoristas:

                con.execute(
                    """
                    ALTER TABLE motoristas
                    ADD COLUMN rg TEXT
                    """
                )

            # --------------------------------------------------
            # CLIENTES: compatibilidade com banco já existente
            # --------------------------------------------------
            colunas_clientes = {
                linha["name"]
                for linha in con.execute("PRAGMA table_info(clientes)")
            }
            if "nome_etiqueta" not in colunas_clientes:
                con.execute(
                    "ALTER TABLE clientes ADD COLUMN nome_etiqueta TEXT DEFAULT NULL"
                )

            # --------------------------------------------------
            # DOCUMENTOS
            # --------------------------------------------------

            colunas_documentos = {
                linha["name"]
                for linha in con.execute(
                    "PRAGMA table_info(documentos)"
                )
            }

            novos_campos = {
                "numero_nf": "TEXT NOT NULL DEFAULT ''",
                "tipo_documento": "TEXT NOT NULL DEFAULT ''",
                "numero_documento": "TEXT NOT NULL DEFAULT ''",
                "remetente": "TEXT NOT NULL DEFAULT ''",
                "destinatario": "TEXT NOT NULL DEFAULT ''",
                "cidade_origem": "TEXT NOT NULL DEFAULT ''",
                "uf_origem": "TEXT NOT NULL DEFAULT ''",
                "cidade_destino": "TEXT NOT NULL DEFAULT ''",
                "uf_destino": "TEXT NOT NULL DEFAULT ''",
                "motorista": "TEXT NOT NULL DEFAULT ''",
                "motorista_id": "INTEGER",
            }

            faltantes = [
                campo
                for campo in novos_campos
                if campo not in colunas_documentos
            ]

            # --------------------------------------------------
            # BACKUP
            # --------------------------------------------------

            if faltantes:

                backup = self.caminho.with_name(
                    self.caminho.name
                    + ".backup_"
                    + datetime.now().strftime(
                        "%Y%m%d_%H%M%S_%f"
                    )
                )

                with sqlite3.connect(backup) as destino:
                    con.backup(destino)

                # --------------------------------------------------
                # ALTERAÇÃO ESTRUTURAL
                # --------------------------------------------------

                for campo in faltantes:

                    con.execute(
                        f"""
                        ALTER TABLE documentos
                        ADD COLUMN {campo}
                        {novos_campos[campo]}
                        """
                    )

            # --------------------------------------------------
            # MIGRAÇÃO DOS DOCUMENTOS ANTIGOS
            # --------------------------------------------------

            colunas_documentos = {
                linha["name"]
                for linha in con.execute(
                    "PRAGMA table_info(documentos)"
                )
            }

            # Se existir numero_cte, utiliza-o para preencher
            # numero_documento dos registros antigos.

            if (
                "numero_documento" in colunas_documentos
                and "numero_cte" in colunas_documentos
                and "codigo_barras" in colunas_documentos
            ):

                con.execute(
                    """
                    UPDATE documentos
                    SET numero_documento =
                        CASE
                            WHEN numero_cte != ''
                                THEN numero_cte

                            ELSE
                                COALESCE(
                                    NULLIF(
                                        ltrim(
                                            substr(
                                                codigo_barras,
                                                26,
                                                9
                                            ),
                                            '0'
                                        ),
                                        ''
                                    ),
                                    '0'
                                )
                        END
                    WHERE numero_documento = ''
                    """
                )

            # --------------------------------------------------
            # IDENTIFICA NFE / CTE
            # --------------------------------------------------

            if (
                "tipo_documento" in colunas_documentos
                and "codigo_barras" in colunas_documentos
            ):

                con.execute(
                    """
                    UPDATE documentos
                    SET tipo_documento =
                        CASE
                            WHEN substr(codigo_barras, 21, 2) = '55'
                                THEN 'NFE'
                            ELSE 'CTE'
                        END
                    WHERE tipo_documento = ''
                    """
                )

            # --------------------------------------------------
            # NFE
            # --------------------------------------------------

            if (
                "numero_nf" in colunas_documentos
                and "numero_documento" in colunas_documentos
            ):

                con.execute(
                    """
                    UPDATE documentos
                    SET numero_nf = numero_documento,
                        numero_cte = ''
                    WHERE tipo_documento = 'NFE'
                      AND numero_nf = ''
                    """
                )

            # --------------------------------------------------
            # ÍNDICES
            # --------------------------------------------------

            for nome_indice, coluna in (
                ("idx_documentos_cte", "numero_cte"),
                ("idx_documentos_nf", "numero_nf"),
                ("idx_documentos_numero", "numero_documento"),
                ("idx_documentos_placa", "placa"),
                ("idx_documentos_motorista", "motorista"),
                ("idx_documentos_tipo", "tipo_documento"),
            ):
                con.execute(
                    f"CREATE INDEX IF NOT EXISTS {nome_indice} ON documentos({coluna})"
                )

    def _migrar_cpf_opcional(self):
        """Remove NOT NULL do CPF/CNPJ existente sem perder clientes/documentos."""
        with sqlite3.connect(self.caminho) as con:
            colunas = con.execute("PRAGMA table_info(clientes)").fetchall()
            cpf = next((c for c in colunas if c[1] == "cpf_cnpj"), None)
            if not cpf or not cpf[3]:
                return
            backup = self.caminho.with_name(
                self.caminho.name + ".antes_cpf_opcional_" +
                datetime.now().strftime("%Y%m%d_%H%M%S_%f") + ".bak"
            )
            with sqlite3.connect(backup) as destino:
                con.backup(destino)
            # Desabilitar FK antes de iniciar a transação é essencial.
            con.execute("PRAGMA foreign_keys=OFF")
            try:
                con.execute("BEGIN IMMEDIATE")
                con.execute("""CREATE TABLE clientes_nova (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome TEXT NOT NULL,
                    cpf_cnpj TEXT UNIQUE,
                    cidade TEXT NOT NULL,
                    uf TEXT NOT NULL CHECK(length(uf)=2 AND uf=upper(uf)),
                    nome_etiqueta TEXT DEFAULT NULL
                )""")
                con.execute("""INSERT INTO clientes_nova
                    (id,nome,cpf_cnpj,cidade,uf,nome_etiqueta)
                    SELECT id,nome,cpf_cnpj,cidade,uf,nome_etiqueta FROM clientes""")
                con.execute("DROP TABLE clientes")
                con.execute("ALTER TABLE clientes_nova RENAME TO clientes")
                erros = con.execute("PRAGMA foreign_key_check").fetchall()
                if erros:
                    raise sqlite3.IntegrityError(f"Falha nas referências: {erros[:3]}")
                con.commit()
            except Exception:
                con.rollback()
                raise
            finally:
                con.execute("PRAGMA foreign_keys=ON")

    def _migrar_carregamentos(self):
        """Adiciona vínculo entre NF-e sem modificar documentos anteriores."""
        with self.conectar() as con:
            colunas = {linha["name"] for linha in con.execute("PRAGMA table_info(documentos)")}
            if "carregamento_id" not in colunas:
                # Backup anterior à alteração de esquema.
                backup = self.caminho.with_name(
                    self.caminho.name + ".antes_carregamentos_" +
                    datetime.now().strftime("%Y%m%d_%H%M%S_%f") + ".bak"
                )
                with sqlite3.connect(backup) as destino:
                    con.backup(destino)
                con.execute("ALTER TABLE documentos ADD COLUMN carregamento_id INTEGER")
            con.execute("CREATE INDEX IF NOT EXISTS idx_documentos_carregamento ON documentos(carregamento_id)")

    def consultar_notas_carregamento(self, documento):
        """Retorna as NF-e do mesmo carregamento, ordenadas pelo cadastro."""
        if not documento or documento.get("tipo_documento") != "NFE":
            return []
        grupo = documento.get("carregamento_id") or documento.get("id")
        with self.conectar() as con:
            rows = con.execute(
                "SELECT id, numero_nf, codigo_barras FROM documentos "
                "WHERE tipo_documento = 'NFE' AND carregamento_id = ? ORDER BY id",
                (grupo,),
            ).fetchall()
        return [dict(row) for row in rows]

    def vincular_primeira_nfe(self, documento_id):
        """Marca a primeira nota como raiz do carregamento."""
        with self.conectar() as con:
            con.execute(
                "UPDATE documentos SET carregamento_id = id "
                "WHERE id = ? AND tipo_documento = 'NFE' AND carregamento_id IS NULL",
                (documento_id,),
            )

    def cadastrar_cliente(self, nome, cidade, uf):
        """Insere cliente manual sem CPF/CNPJ, retornando seu registro."""
        nome, cidade, uf = str(nome).strip(), str(cidade).strip(), str(uf).strip().upper()
        if not nome or not cidade or len(uf) != 2:
            raise ValueError("Informe nome, cidade e UF válidos.")
        with self.conectar() as con:
            existente = con.execute("""SELECT id,nome,cidade,uf,nome_etiqueta
                FROM clientes WHERE nome = ? COLLATE NOCASE AND cidade = ? COLLATE NOCASE
                AND uf = ? COLLATE NOCASE LIMIT 1""", (nome,cidade,uf)).fetchone()
            if existente:
                return dict(existente)
            cursor = con.execute("""INSERT INTO clientes (nome,cidade,uf,cpf_cnpj)
                VALUES (?,?,?,NULL)""", (nome,cidade,uf))
            return {"id":cursor.lastrowid,"nome":nome,"cidade":cidade,"uf":uf,"nome_etiqueta":None}

    # ==========================================================
    # CLIENTES
    # ==========================================================

    def consultar_clientes(self):
        """Retorna clientes cadastrados sem repetir nomes."""

        with self.conectar() as con:

            registros = con.execute(
                """
                SELECT id, nome, cidade, uf, nome_etiqueta
                FROM clientes
                ORDER BY nome
                """
            ).fetchall()

        clientes = {}

        for registro in registros:

            nome = (
                registro["nome"] or ""
            ).strip()

            cidade = (
                registro["cidade"] or ""
            ).strip()

            uf = (
                registro["uf"] or ""
            ).strip().upper()

            if nome:

                clientes.setdefault(
                    nome.casefold(),
                    {
                        "id": registro["id"],
                        "nome": nome,
                        "cidade": cidade,
                        "uf": uf,
                        "nome_etiqueta": registro["nome_etiqueta"],
                    },
                )

        return sorted(
            clientes.values(),
            key=lambda cliente:
                cliente["nome"].casefold(),
        )

    # Mantém o nome antigo para não quebrar
    # código existente no projeto.
    def conultarClientes(self):
        """Compatibilidade com o método antigo."""

        return self.consultar_clientes()

    def consultar_nome_etiqueta(self, cliente_id):
        """Obtém nome original e nome personalizado de um cliente pelo ID."""
        with self.conectar() as con:
            registro = con.execute(
                "SELECT id, nome, nome_etiqueta FROM clientes WHERE id = ?",
                (cliente_id,),
            ).fetchone()
        return dict(registro) if registro else None

    def atualizar_nome_etiqueta(self, cliente_id, nome_etiqueta):
        """Salva a preferência de impressão; vazio restaura nome original."""
        valor = str(nome_etiqueta or "").strip() or None
        with self.conectar() as con:
            cursor = con.execute(
                "UPDATE clientes SET nome_etiqueta = ? WHERE id = ?",
                (valor, cliente_id),
            )
            return cursor.rowcount > 0

    # ==========================================================
    # MOTORISTAS
    # ==========================================================

    def listar_motoristas(self):
        """
        Retorna os motoristas cadastrados sem repetição.

        Cada motorista possui:
            nome
            rg
        """

        with self.conectar() as con:

            registros = con.execute(
                """
                SELECT nome, rg
                FROM motoristas
                ORDER BY nome
                """
            ).fetchall()

        motoristas = {}

        for registro in registros:

            nome = (
                registro["nome"] or ""
            ).strip()

            rg = (
                registro["rg"] or ""
            ).strip()

            if nome:

                motoristas.setdefault(
                    nome.casefold(),
                    {
                        "nome": nome,
                        "rg": rg,
                    },
                )

        return sorted(
            motoristas.values(),
            key=lambda motorista:
                motorista["nome"].casefold(),
        )

    # ==========================================================
    # CONSULTAR MOTORISTA PELA PLACA
    # ==========================================================

    def consultar_motorista(self, placa):
        """Consulta o motorista atualmente vinculado à placa."""

        placa = (
            placa or ""
        ).strip().upper()

        if not placa:
            return None

        with self.conectar() as con:

            row = con.execute(
                """
                SELECT
                    v.placa,
                    m.id AS motorista_id,
                    m.nome AS motorista,
                    m.rg AS rg
                FROM veiculos v

                INNER JOIN motoristas m
                    ON m.id = v.motorista_id

                WHERE v.placa = ?
                """,
                (placa,),
            ).fetchone()

        return dict(row) if row else None

    # ==========================================================
    # SALVAR MOTORISTA / PLACA
    # ==========================================================

    def salvar_motorista(
        self,
        placa,
        motorista,
        rg="",
    ):
        """
        Vincula uma placa a um motorista existente
        ou cadastra um novo motorista.

        Retorna:
            True  -> placa já existia e foi atualizada.
            False -> placa foi cadastrada.
        """

        placa = (
            placa or ""
        ).strip().upper()

        motorista = (
            motorista or ""
        ).strip()

        rg = (
            rg or ""
        ).strip()

        if not placa:
            raise ValueError(
                "A placa é obrigatória."
            )

        if not motorista:
            raise ValueError(
                "O nome do motorista é obrigatório."
            )

        with self.conectar() as con:

            con.execute(
                "BEGIN IMMEDIATE"
            )

            # --------------------------------------------------
            # VERIFICA SE A PLACA JÁ EXISTE
            # --------------------------------------------------

            veiculo = con.execute(
                """
                SELECT motorista_id
                FROM veiculos
                WHERE placa = ?
                """,
                (placa,),
            ).fetchone()

            # --------------------------------------------------
            # PROCURA MOTORISTA EXISTENTE
            # --------------------------------------------------

            # SQLite lower() não trata corretamente todos os caracteres
            # acentuados (ex.: João/JOÃO). A comparação em Python com
            # casefold() preserva um único cadastro para o mesmo motorista.
            motorista_existente = next(
                (
                    registro
                    for registro in con.execute(
                        "SELECT id, nome, rg FROM motoristas ORDER BY id"
                    ).fetchall()
                    if (registro["nome"] or "").strip().casefold()
                    == motorista.casefold()
                ),
                None,
            )

            # --------------------------------------------------
            # MOTORISTA EXISTENTE
            # --------------------------------------------------

            if motorista_existente:

                motorista_id = (
                    motorista_existente["id"]
                )

            # --------------------------------------------------
            # NOVO MOTORISTA
            # --------------------------------------------------

            else:

                cursor = con.execute(
                    """
                    INSERT INTO motoristas (
                        nome,
                        rg
                    )
                    VALUES (?, ?)
                    """,
                    (
                        motorista,
                        rg or None,
                    ),
                )

                motorista_id = (
                    cursor.lastrowid
                )

            # --------------------------------------------------
            # ATUALIZA PLACA
            # --------------------------------------------------

            if veiculo:

                con.execute(
                    """
                    UPDATE veiculos
                    SET motorista_id = ?
                    WHERE placa = ?
                    """,
                    (
                        motorista_id,
                        placa,
                    ),
                )

            # --------------------------------------------------
            # CADASTRA PLACA
            # --------------------------------------------------

            else:

                con.execute(
                    """
                    INSERT INTO veiculos (
                        placa,
                        motorista_id
                    )
                    VALUES (?, ?)
                    """,
                    (
                        placa,
                        motorista_id,
                    ),
                )

            return veiculo is not None

    # ==========================================================
    # DOCUMENTOS
    # ==========================================================

    def cadastrar_documento(self, dados):
        """
        Cadastra um documento.

        O método aceita o dicionário utilizado
        pelo restante do projeto.
        """

        campos = (
            "id_remetente", "id_destinatario", "remetente", "codigo_barras",
            "numero_cte", "numero_nf", "tipo_documento", "numero_documento",
            "destinatario", "cidade_origem", "uf_origem", "cidade_destino",
            "uf_destino", "placa", "motorista", "data", "observacao",
            "carregamento_id",
        )
        cadastro = dict(dados)
        with self.conectar() as con:
            # Uma única transação: cliente novo e documento são gravados juntos.
            for tipo, local in (("remetente", "origem"), ("destinatario", "destino")):
                nome = str(cadastro.get(tipo) or "").strip()
                cidade = str(cadastro.get(f"cidade_{local}") or "").strip()
                uf = str(cadastro.get(f"uf_{local}") or "").strip().upper()
                id_chave = f"id_{tipo}"
                cliente_id = cadastro.get(id_chave)
                if cliente_id:
                    existente = con.execute(
                        "SELECT id, nome, cidade, uf FROM clientes WHERE id = ?", (cliente_id,)
                    ).fetchone()
                    if (not existente or existente["nome"].strip().casefold() != nome.casefold()
                        or existente["cidade"].strip().casefold() != cidade.casefold()
                        or existente["uf"].strip().casefold() != uf.casefold()):
                        cliente_id = None
                if not cliente_id:
                    # Não duplicar nome e localização, mesmo se o usuário não selecionou.
                    registros = con.execute(
                        "SELECT id, nome, cidade, uf FROM clientes"
                    ).fetchall()
                    existente = next((c for c in registros
                        if c["nome"].strip().casefold() == nome.casefold()
                        and c["cidade"].strip().casefold() == cidade.casefold()
                        and c["uf"].strip().casefold() == uf.casefold()), None)
                    if existente:
                        cliente_id = existente["id"]
                    else:
                        if not cidade or len(uf) != 2:
                            raise ValueError(
                                f"Para cadastrar o {tipo} '{nome}', informe cidade e UF."
                            )
                        cursor = con.execute(
                            "INSERT INTO clientes (nome, cpf_cnpj, cidade, uf) VALUES (?, NULL, ?, ?)",
                            (nome, cidade, uf),
                        )
                        cliente_id = cursor.lastrowid
                cadastro[id_chave] = cliente_id

            valores = [cadastro.get(campo, "") for campo in campos]
            cur = con.execute(
                f"INSERT INTO documentos ({', '.join(campos)}) "
                f"VALUES ({', '.join('?' for _ in campos)})", valores,
            )
            if cadastro.get("tipo_documento") == "NFE" and not cadastro.get("carregamento_id"):
                con.execute("UPDATE documentos SET carregamento_id = ? WHERE id = ?",
                            (cur.lastrowid, cur.lastrowid))
                cadastro["carregamento_id"] = cur.lastrowid
            return {"id": cur.lastrowid, **cadastro}

    # ==========================================================
    # CONSULTAR DOCUMENTOS
    # ==========================================================

    def atualizar_documento(self, documento_id, dados, campos):
        """Atualiza somente os campos autorizados de um documento existente."""
        permitidos = {"remetente", "destinatario", "placa", "motorista"}
        campos = set(campos or ()) & permitidos
        if "placa" in campos:
            # A placa nunca é alterada sem seu motorista vinculado.
            campos.add("motorista")
        if not campos:
            raise ValueError("Selecione ao menos um campo para atualizar.")

        try:
            documento_id = int(documento_id)
        except (TypeError, ValueError) as erro:
            raise ValueError("Documento inválido para atualização.") from erro

        valores = {
            campo: str(dados.get(campo) or "").strip()
            for campo in campos
        }

        with self.conectar() as con:
            existente = con.execute(
                "SELECT * FROM documentos WHERE id = ?", (documento_id,)
            ).fetchone()
            if existente is None:
                raise ValueError("O documento não foi encontrado para atualização.")

            # A correção de grafia também atualiza o cliente vinculado, para
            # que o autocomplete passe a mostrar o nome corrigido.
            for campo, coluna_id in (
                ("remetente", "id_remetente"),
                ("destinatario", "id_destinatario"),
            ):
                if campo in campos:
                    cliente_id = existente[coluna_id]
                    if cliente_id:
                        con.execute(
                            "UPDATE clientes SET nome = ? WHERE id = ?",
                            (valores[campo], cliente_id),
                        )

            atribuicoes = ", ".join(f"{campo} = ?" for campo in campos)
            parametros = [valores[campo] for campo in campos]
            parametros.append(documento_id)
            con.execute(
                f"UPDATE documentos SET {atribuicoes} WHERE id = ?",
                parametros,
            )
            atualizado = con.execute(
                "SELECT * FROM documentos WHERE id = ?", (documento_id,)
            ).fetchone()

        return dict(atualizado)

    def consultar_documentos(self, filtros):
        """
        Consulta documentos utilizando os filtros informados.

        Campos de texto permitem pesquisa parcial.
        """

        clausulas = []
        valores = []

        campos_texto = {
            "remetente",
            "motorista",
            "destinatario",
            "cidade_origem",
            "cidade_destino",
        }

        campos_validos = {
            "remetente",
            "codigo_barras",
            "numero_cte",
            "numero_nf",
            "numero_documento",
            "tipo_documento",
            "destinatario",
            "cidade_origem",
            "uf_origem",
            "cidade_destino",
            "uf_destino",
            "placa",
            "motorista",
        }

        for campo, valor in filtros.items():

            if campo not in campos_validos:
                continue

            if valor is None:
                continue

            valor = str(valor).strip()

            if not valor:
                continue

            if campo in campos_texto:

                clausulas.append(
                    f"""
                    instr(
                        MAIUSCULA({campo}),
                        MAIUSCULA(?)
                    ) > 0
                    """
                )

                valores.append(valor)

            else:

                clausulas.append(
                    f"{campo} = ?"
                )

                valores.append(valor)

        # Nenhum filtro informado.
        if not clausulas:
            return []

        sql = """
            SELECT *
            FROM documentos
            WHERE
        """

        sql += " AND ".join(clausulas)

        sql += """
            ORDER BY id DESC
        """

        with self.conectar() as con:

            rows = con.execute(
                sql,
                valores,
            ).fetchall()

        return [
            dict(row)
            for row in rows
        ]
