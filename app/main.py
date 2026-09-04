from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def inicio():
    return {"mensagem": "Proposta AI esta funcionando!"}

@app.get("/status")
def status():
    return {"status": "Online", "versao": "0.1.0"}

@app.get("/proposta/exemplo")
def exemplo_proposta():
    return {
        "cliente": "Empresa ABC",
        "valor": 5000.00,
        "descricao": "Desenvolvimento de sistema Web com IA"
    }