from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

# Define a estrutura de dados esperada na requisição
class PropostaRequest(BaseModel):
    cliente: str
    servico: str
    orcamento: float
    detalhes: str

@app.get("/")
def inicio():
    return {"mensagem": "Proposta AI esta funcionando!"}

@app.post("/proposta")
def criar_proposta(dados: PropostaRequest):
    # Por enquanto, simulamos o processamento retornando a confirmação dos dados
    return {
        "status": "Proposta recebida com sucesso!",
        "cliente": dados.cliente,
        "resumo": f"Serviço de '{dados.servico}' orçado em R$ {dados.orcamento:.2f}",
        "proposta_gerada": f"Proposta comercial para {dados.cliente}: Prestação de serviços em {dados.servico}. Detalhes: {dados.detalhes}"
    }