import pandas as pd
from datetime import datetime, timedelta

# --- CONFIGURAÇÃO INICIAL E DATAS ---

# Feriados Nacionais no período
feriados_bloqueio = [
    datetime(2025, 10, 12),  # Dom - Nossa Sra. Aparecida
    datetime(2025, 11, 2),   # Dom - Finados
    datetime(2025, 11, 15),  # Sáb - Proclamação da República
    datetime(2025, 11, 20),  # Qui - Consciência Negra
]

arquivo_excel = "inventario.xlsx" 

df = pd.read_excel(arquivo_excel)
lista_dfs_patch = []

# Rastreia o último patch aplicado em *qualquer* ambiente
ultimo_patch_geral = datetime(2025, 10, 5) 
data_inicio_fixa = datetime(2025, 10, 6) # 06/Out/2025

# --- FUNÇÃO PRINCIPAL DE AGENDAMENTO ---

def gerar_calendario_otimizado(df_inventario, ambiente_target, data_minima_inicio):
    df_amb = df_inventario[df_inventario['Ambiente'] == ambiente_target].copy()
    
    # Ordena por Cluster e Nó
    df_amb = df_amb.sort_values(['Cluster', 'Nó'])
    
    ultimo_patch_cluster = {}  
    proxima_data_candidata = data_minima_inicio

    for idx in df_amb.index:
        cluster = df_amb.loc[idx, 'Cluster']
        
        global ultimo_patch_geral
        
        # Garante a sequencialidade
        if proxima_data_candidata <= ultimo_patch_geral:
            patch_date = ultimo_patch_geral + timedelta(days=1)
        else:
            patch_date = proxima_data_candidata
            
        # Impõe a REGRA DE 7 DIAS
        if cluster in ultimo_patch_cluster:
            data_min_7_dias = ultimo_patch_cluster[cluster] + timedelta(days=7)
            patch_date = max(patch_date, data_min_7_dias)

        
        # Lógica de Feriados e Fins de Semana
        data_sem_horario = patch_date.replace(hour=0, minute=0, second=0)
        while patch_date.weekday() >= 5 or data_sem_horario in feriados_bloqueio:
            patch_date += timedelta(days=1)
            data_sem_horario = patch_date.replace(hour=0, minute=0, second=0)
        
        # Regra de segurança extra
        if patch_date <= ultimo_patch_geral:
            patch_date = ultimo_patch_geral + timedelta(days=1)
            data_sem_horario = patch_date.replace(hour=0, minute=0, second=0)
            while patch_date.weekday() >= 5 or data_sem_horario in feriados_bloqueio:
                patch_date += timedelta(days=1)
                data_sem_horario = patch_date.replace(hour=0, minute=0, second=0)


        # Atualização dos rastreadores e do DataFrame
        df_amb.loc[idx, 'Patch Date'] = patch_date
        ultimo_patch_cluster[cluster] = patch_date
        
        ultimo_patch_geral = patch_date
        proxima_data_candidata = patch_date + timedelta(days=1)

    return df_amb

# --- EXECUÇÃO PRINCIPAL (Ordem de Segurança: DEV -> HOM -> PROD) ---

data_inicio_ambiente = data_inicio_fixa

# 1. Agendar DEV
df_dev = gerar_calendario_otimizado(df, 'DEV', data_inicio_ambiente)
lista_dfs_patch.append(df_dev)

# 2. Agendar HOM 
data_inicio_ambiente = df_dev['Patch Date'].max() + timedelta(days=1)
df_hom = gerar_calendario_otimizado(df, 'HOM', data_inicio_ambiente)
lista_dfs_patch.append(df_hom)

# 3. Agendar PROD 
data_inicio_ambiente = df_hom['Patch Date'].max() + timedelta(days=1)
df_prod = gerar_calendario_otimizado(df, 'PROD', data_inicio_ambiente)
lista_dfs_patch.append(df_prod)

# Concatena resultados, ordena e adiciona a JANELA DE MANUTENÇÃO CORRETA
df_final = pd.concat(lista_dfs_patch).sort_values('Patch Date')

# Definição das janelas baseada na regra do cliente: PROD tem a menor janela
def definir_janela(ambiente):
    if ambiente == 'PROD':
        return '00:00 - 03:30'
    elif ambiente == 'HOM':
        return '00:00 - 05:00'
    else: # DEV
        return '00:00 - 06:00'

df_final['Janela'] = df_final['Ambiente'].apply(definir_janela)

# Remoção de índice e salvamento
df_final = df_final.reset_index(drop=True)

df_final.to_excel("calendario_patch_completo.xlsx", index=False)

print("Calendário gerado com sucesso! As janelas de manutenção agora refletem as restrições do negócio.")