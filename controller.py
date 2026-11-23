"""Validação e respostas padronizadas para a interface."""
from datetime import datetime
import re
import sqlite3

if __package__ and '.' in __package__:
    from ..repositories.sqlite_repository import SQLiteRepository
else:
    from repositories.sqlite_repository import SQLiteRepository


class Controller:
    UFS = tuple('AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO'.split())
    def __init__(self, caminho_banco=None):
        self.repository = SQLiteRepository(caminho_banco)

    def consultar_ultimo_documento(self):
        """Retorna o último documento cadastrado no banco."""
        documentos = self.repository.consultar_documentos({})

        if not documentos:
            return None

        return max(
            documentos,
            key=lambda documento: int(documento.get("id") or 0)
        )

    @staticmethod
    def _normalizar_placa(valor):
        placa = str(valor or '').strip().upper().replace('-', '').replace(' ', '')
        return f'{placa[:3]}-{placa[3:]}' if len(placa) == 7 else placa

    @staticmethod
    def _erro(mensagem):
        return {'sucesso': False, 'mensagem': mensagem, 'dados': None}

    @staticmethod
    def _placa_valida(placa):
        return bool(re.fullmatch(r'[A-Z]{3}-[0-9][A-Z0-9][0-9]{2}', placa))

    def consultar_motorista_por_placa(self, placa):
        placa = self._normalizar_placa(placa)
        if not self._placa_valida(placa):
            return self._erro('Informe uma placa válida (ABC-1234 ou ABC-1D23).')
        dados = self.repository.consultar_motorista(placa)
        if dados is None:
            return {'sucesso': False, 'mensagem': 'Placa não cadastrada. Use o botão Cad. Motorista.', 'dados': {'placa': placa, 'motorista': ''}}

        return {'sucesso': True, 'mensagem': 'Placa encontrada.', 'dados': dados}

    def atualizar_motorista(self, dados):
        placa = self._normalizar_placa(dados.get('placa'))
        motorista = str(dados.get('motorista') or '').strip()
        if not self._placa_valida(placa):
            return self._erro('Informe uma placa válida (ABC-1234 ou ABC-1D23).')
        if not motorista:
            return self._erro('Informe o nome do motorista.')
        rg = str(dados.get('rg') or '').strip()
        exista = self.repository.salvar_motorista(placa, motorista, rg)
        return {'sucesso': True, 'mensagem': 'Motorista atualizado com sucesso.' if exista else 'Placa e motorista cadastrados com sucesso.', 'dados': self.repository.consultar_motorista(placa)}

    def cadastro_motorista(self, dados):
        """Compatibilidade: aplica a mesma regra de cadastrar ou atualizar."""
        return self.atualizar_motorista(dados)

    def extrair_numero_cte_nf(self, codigo_barras):
        """Identifica CT-e ou NF-e e extrai o número da chave."""
        codigo = re.sub(r"\s+", "", str(codigo_barras or ""))

        resultado = {
            "sucesso": False,
            "mensagem": "",
            "tipo_documento": "",
            "numero_cte": "",
            "numero_nf": "",
        }

        if not re.fullmatch(r"[0-9]{44}", codigo):
            resultado["mensagem"] = (
                "O código de barras deve possuir 44 dígitos."
            )
            return resultado

        modelo = codigo[20:22]
        numero = codigo[25:34].lstrip("0") or "0"

        if modelo == "57":
            resultado.update({
                "sucesso": True,
                "mensagem": "Número do CT-e extraído.",
                "tipo_documento": "CTE",
                "numero_cte": numero,
            })

        elif modelo == "55":
            resultado.update({
                "sucesso": True,
                "mensagem": "Número da NF-e extraído.",
                "tipo_documento": "NFE",
                "numero_nf": numero,
            })

        else:
            resultado["mensagem"] = (
                "A chave informada não pertence a um CT-e ou NF-e."
            )

        return resultado

    def cadastrar(self, dados):
        campos = ('remetente', 'codigo_barras', 'destinatario', 'cidade_origem', 'uf_origem', 'cidade_destino',
                  'uf_destino', 'placa', 'motorista', 'data', 'observacao')
        cadastro = {c: str(dados.get(c) or '').strip() for c in campos}
        if any(not cadastro[c] for c in campos if c not in ('observacao', 'cidade_origem', 'uf_origem')):
            return self._erro('Preencha remetente, destinatário, chave, cidade/UF de destino, placa, motorista e data.')
        cadastro['codigo_barras'] = re.sub(r'\s+', '', cadastro['codigo_barras'])
        extraido = self.extrair_numero_cte_nf(cadastro['codigo_barras'])
        if not extraido['sucesso']:
            return self._erro(extraido['mensagem'])
        cadastro['carregamento_id'] = dados.get('carregamento_id')
        cadastro['id_remetente'] = dados.get('id_remetente')
        cadastro['id_destinatario'] = dados.get('id_destinatario')
        cadastro['tipo_documento'] = extraido['tipo_documento']
        cadastro['numero_cte'] = extraido['numero_cte']
        cadastro['numero_nf'] = extraido['numero_nf']
        cadastro['numero_documento'] = extraido['numero_cte'] or extraido['numero_nf']
        # A chave é a fonte do número; não depende de pressionar Enter antes de salvar.
        cadastro['uf_origem'] = cadastro['uf_origem'].upper()
        if bool(cadastro['cidade_origem']) != bool(cadastro['uf_origem']):
            return self._erro('Informe cidade e UF de origem juntas.')
        if cadastro['uf_origem'] and cadastro['uf_origem'] not in self.UFS:
            return self._erro('Selecione uma UF de origem válida.')
        cadastro['uf_destino'] = cadastro['uf_destino'].upper()
        if cadastro['uf_destino'] not in self.UFS:
            return self._erro('Selecione uma UF de destino válida.')
        try:
            cadastro['data'] = datetime.strptime(cadastro['data'], '%d/%m/%Y').strftime('%d/%m/%Y')
        except ValueError:
            return self._erro('Informe uma data válida no formato dd/mm/aaaa.')
        cadastro['placa'] = self._normalizar_placa(cadastro['placa'])
        atual = self.consultar_motorista_por_placa(cadastro['placa'])
        if not atual['sucesso']:
            return atual
        if cadastro['motorista'] != atual['dados']['motorista']:
            return self._erro('O motorista da placa mudou. Consulte a placa novamente.')
        try:
            salvo = self.repository.cadastrar_documento(cadastro)
        except sqlite3.IntegrityError:
            if self.repository.consultar_documentos({'codigo_barras': cadastro['codigo_barras']}):
                return self._erro('Esta chave já está cadastrada.')
            raise
        return {'sucesso': True, 'mensagem': 'Cadastro realizado com sucesso.', 'filtros': cadastro, 'dados': salvo}

    def cadastrar_nfe_vinculada(self, dados, carregamento_id):
        """Cadastra nova NF-e copiando dados logísticos da primeira."""
        originais = self.repository.consultar_documentos({"codigo_barras": dados.get("chave_original", "")})
        if not originais:
            return self._erro("Primeira NF-e não encontrada.")
        original = originais[0]
        if original.get("tipo_documento") != "NFE":
            return self._erro("Somente NF-e pode ter notas vinculadas.")
        if int(original.get("carregamento_id") or original["id"]) != int(carregamento_id):
            return self._erro("O carregamento informado não corresponde à primeira nota.")
        chave = str(dados.get("codigo_barras") or "").strip()
        extraido = self.extrair_numero_cte_nf(chave)
        if not extraido["sucesso"] or extraido["tipo_documento"] != "NFE":
            return self._erro("Informe uma chave válida de NF-e (modelo 55).")
        copia = {campo: original.get(campo) for campo in (
            "remetente", "destinatario", "id_remetente", "id_destinatario",
            "cidade_origem", "uf_origem", "cidade_destino", "uf_destino",
            "placa", "motorista", "data", "observacao")}
        copia.update(codigo_barras=chave, carregamento_id=carregamento_id)
        return self.cadastrar(copia)

    def notas_vinculadas(self, documento):
        return self.repository.consultar_notas_carregamento(documento)

    def observacao_com_notas(self, documento):
        """Mantém a observação original e acrescenta apenas outras NF-e."""
        observacao = str(documento.get("observacao") or "").strip()
        notas = self.notas_vinculadas(documento)
        outras = [str(n["numero_nf"]) for n in notas if n["id"] != documento.get("id")]
        if outras:
            numero = documento.get("numero_nf") or documento.get("numero_documento")
            texto = f"NOTA FISCAL {numero} ESTÁ JUNTO COM AS NOTAS " + ", ".join(outras) + "."
            return (observacao + "\n\n" + texto).strip()
        return observacao

    def atualizar_documento(self, documento_id, dados, campos):
        """Atualiza a grafia de clientes ou o vínculo completo placa/motorista."""
        permitidos = {"remetente", "destinatario", "placa"}
        campos = set(campos or ()) & permitidos
        if not campos:
            return self._erro("Selecione ao menos um campo para atualizar.")

        atualizacao = {}
        for campo in ("remetente", "destinatario"):
            if campo in campos:
                valor = str(dados.get(campo) or "").strip()
                if not valor:
                    return self._erro(f"Informe o {campo}.")
                atualizacao[campo] = valor

        if "placa" in campos:
            placa = self._normalizar_placa(dados.get("placa"))
            motorista = str(dados.get("motorista") or "").strip()
            if not self._placa_valida(placa):
                return self._erro("Informe uma placa válida (ABC-1234 ou ABC-1D23).")

            vinculo = self.consultar_motorista_por_placa(placa)
            if not vinculo.get("sucesso"):
                return vinculo
            if motorista != vinculo["dados"].get("motorista", ""):
                return self._erro(
                    "O motorista não corresponde à placa. Consulte a placa "
                    "ou atualize o vínculo em Cad. Motorista."
                )
            atualizacao["placa"] = placa
            atualizacao["motorista"] = motorista

        try:
            salvo = self.repository.atualizar_documento(
                documento_id, atualizacao, campos
            )
        except (TypeError, ValueError) as erro:
            return self._erro(str(erro))

        return {
            "sucesso": True,
            "mensagem": "Documento atualizado com sucesso.",
            "dados": salvo,
        }

    def consultar(self, dados):
        campos = ('remetente', 'codigo_barras', 'numero_documento', 'numero_cte', 'numero_nf', 'destinatario', 'cidade_origem', 'uf_origem', 'cidade_destino', 'uf_destino', 'placa', 'motorista')
        filtros = {c: str(dados.get(c) or '').strip().upper() for c in campos if str(dados.get(c) or '').strip()}
        if 'placa' in filtros:
            filtros['placa'] = self._normalizar_placa(filtros['placa'])
        if 'numero_documento' in filtros:
            filtros['numero_documento'] = filtros['numero_documento'].lstrip('0') or '0'
        if 'numero_cte' in filtros:
            filtros['numero_cte'] = filtros['numero_cte'].lstrip('0') or '0'
        if 'codigo_barras' in filtros:
            filtros['codigo_barras'] = re.sub(r'\s+', '', filtros['codigo_barras'])
        registros = self.repository.consultar_documentos(filtros) if filtros else []
        quantidade = len(registros)
        mensagem = ('Documento encontrado.' if quantidade == 1 else f'{quantidade} documentos encontrados.') if quantidade else ('Nenhum documento encontrado.' if filtros else 'Informe pelo menos um campo para consultar.')
        return {'sucesso': bool(registros), 'mensagem': mensagem, 'tipo_retorno': 'unico' if quantidade == 1 else 'multiplo' if quantidade else 'vazio', 'quantidade': quantidade, 'filtros': filtros, 'dados': registros}
    def consultar_clientes(self):
        """Disponibiliza os clientes cadastrados para a View."""
        return self.repository.consultar_clientes()

    def listar_motoristas(self):
        """Disponibiliza os motoristas cadastrados para a View."""
        return self.repository.listar_motoristas()

    def consultar_nome_etiqueta(self, cliente_id):
        """Consulta o nome da etiqueta, usando o nome original como alternativa."""
        cliente = next(
            (
                c for c in self.repository.consultar_clientes()
                if str(c.get("id")) == str(cliente_id)
            ),
            None
        )

        if not cliente:
            return None

        nome_etiqueta = str(cliente.get("nome_etiqueta") or "").strip()

        return nome_etiqueta or cliente["nome"]

    def atualizar_nome_etiqueta(self, cliente_id, nome_etiqueta):
        """Salva o nome personalizado para futuras impressões."""
        nome_etiqueta = str(nome_etiqueta or "").strip()

        if not nome_etiqueta:
            raise ValueError("Informe o nome que será impresso na etiqueta.")

        return self.repository.atualizar_nome_etiqueta(
            cliente_id,
            nome_etiqueta
        )

    def localizar_cliente_etiqueta(
            self, nome, cidade="", uf="", cliente_id=None
    ):
        """Localiza o cliente e define o nome que será exibido na etiqueta."""

        clientes = self.repository.consultar_clientes()

        if cliente_id is not None:
            candidatos = [
                c for c in clientes
                if str(c.get("id")) == str(cliente_id)
            ]
        else:
            nome = str(nome or "").strip().casefold()
            cidade = str(cidade or "").strip().casefold()
            uf = str(uf or "").strip().casefold()

            candidatos = [
                c for c in clientes
                if str(c.get("nome") or "").strip().casefold() == nome
                   and (
                           not cidade
                           or str(c.get("cidade") or "").strip().casefold() == cidade
                   )
                   and (
                           not uf
                           or str(c.get("uf") or "").strip().casefold() == uf
                   )
            ]

        if len(candidatos) != 1:
            return None

        cliente = dict(candidatos[0])

        cliente["nome_etiqueta"] = (
                str(cliente.get("nome_etiqueta") or "").strip()
                or cliente["nome"]
        )

        return cliente

    def cadastrar_cliente(self, nome, cidade, uf):
        """Cadastro manual de cliente sem documento fiscal obrigatório."""
        if uf not in self.UFS:
            raise ValueError("Selecione uma UF válida.")
        return self.repository.cadastrar_cliente(nome, cidade, uf)
