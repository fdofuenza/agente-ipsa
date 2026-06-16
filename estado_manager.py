import json, os

ARCHIVO = "estado.json"

def cargar():
    if os.path.exists(ARCHIVO):
        with open(ARCHIVO) as f:
            return json.load(f)
    return {"capital_total":1898524,"efectivo":1898524,"posiciones":{},
            "vendiendo_cap":False,"max_posiciones":4,"reserva_pct":0.10}

def guardar(estado):
    with open(ARCHIVO,"w") as f:
        json.dump(estado,f,indent=2,ensure_ascii=False)

def get_efectivo(estado):
    return estado.get("efectivo", 0)

def capital_disponible(estado):
    reserva=estado["capital_total"]*estado.get("reserva_pct",0.10)
    return max(0,estado.get("efectivo",0)-reserva)

def posiciones_abiertas(estado):
    pos=estado.get("posiciones",{})
    if estado.get("vendiendo_cap"):
        return {k:v for k,v in pos.items() if k!="CAP.SN"}
    return pos

def slots_disponibles(estado):
    return max(0,estado.get("max_posiciones",4)-len(posiciones_abiertas(estado)))

def distribucion_sectores(estado):
    from config import ACCIONES
    sectores={}
    for t,d in estado.get("posiciones",{}).items():
        if t in ACCIONES:
            s=ACCIONES[t][1]
            m=d["unidades"]*d["precio_compra"]
            sectores[s]=sectores.get(s,0)+m
    cap=estado["capital_total"]
    return {s:round(m/cap*100,1) for s,m in sectores.items()}
