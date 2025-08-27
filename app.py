# app.py (Versión para despliegue web)

import requests
from pydantic import BaseModel, Field
import sys

# Volvemos a importar FastAPI
from fastapi import FastAPI
from mcp.server.fastmcp import FastMCP

# --- La lógica de búsqueda se mantiene igual ---
def generar_consultas(consulta_inicial: str) -> list[str]:
    consulta_limpia = consulta_inicial.strip()
    if not consulta_limpia:
        return []
    consultas = set()
    consultas.add(consulta_limpia)
    consultas.add(f"{consulta_limpia} remoto")
    return list(consultas)

# --- Creamos las instancias de FastAPI y FastMCP ---
app = FastAPI(title="Servidor de Búsqueda de Empleos")
mcp_app = FastMCP(
    name="buscador_empleos_cumbre_simple",
    instructions="Un servidor que obtiene una lista de empleos para que la IA la analice."
)

class BusquedaInput(BaseModel):
    consulta: str = Field(
        ..., 
        description="La consulta de búsqueda EXACTA. Debe ser lo más limpia posible, incluyendo puesto y ciudad. EVITA palabras de relleno como 'busca', 'quiero', 'para', 'en'. Ejemplos correctos: 'vendedor Cúcuta', 'desarrollador remoto', 'conductor Bogota'."
    )

@mcp_app.tool(
    name="buscar_empleos_lista_cruda",
    description="Busca ofertas de empleo en Colombia. Una buena consulta debe incluir el puesto y/o la ciudad. Por ejemplo: 'vendedor en Cúcuta', 'desarrollador remoto', 'conductor bogota'."
)
def buscar_empleos_raw(params: BusquedaInput) -> dict:
    # ... (La lógica interna de esta función no cambia)
    consulta_inicial = params.consulta
    consultas_a_realizar = generar_consultas(consulta_inicial)
    todas_las_vacantes = {}
    for consulta in consultas_a_realizar:
        api_url = f"https://api-search.cumbre.icu/search/{consulta}"
        try:
            response = requests.get(api_url)
            response.raise_for_status()
            data = response.json()
            vacancies = data.get("vacancies", [])
            for vacante in vacancies:
                todas_las_vacantes[vacante["id"]] = vacante
        except requests.exceptions.RequestException:
            pass
    
    lista_final_vacantes = list(todas_las_vacantes.values())
    return {
        "consultas_realizadas": consultas_a_realizar,
        "vacantes_encontradas": lista_final_vacantes
    }

# Montamos la app de MCP en FastAPI
app.mount("/mcp", mcp_app.streamable_http_app())