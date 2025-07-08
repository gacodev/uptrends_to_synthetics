#!/usr/bin/env python3

import requests
import os
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv()

class MonitorListService:
    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self.base_url = "https://api.uptrends.com/v4"
        self.headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        self.auth = (username, password)
    
    def get_all_monitors(self) -> List[Dict]:
        """
        Obtiene todos los monitores desde Uptrends API
        Retorna una lista de objetos con id y name
        """
        url = f"{self.base_url}/Monitor"
        
        try:
            print("Obteniendo lista completa de monitores desde Uptrends...")
            response = requests.get(url, auth=self.auth, headers=self.headers, verify=False)
            response.raise_for_status()
            
            monitors_data = response.json()
            print(f"API respondió con {len(monitors_data)} monitores")
            
            # Crear array con objetos id, name
            monitor_list = []
            for monitor_data in monitors_data:
                monitor_obj = {
                    "id": monitor_data.get('MonitorGuid', ''),
                    "name": monitor_data.get('Name', '')
                }
                monitor_list.append(monitor_obj)
            
            print(f"Lista creada con {len(monitor_list)} monitores")
            return monitor_list
            
        except requests.exceptions.Timeout:
            print("Error: Timeout al obtener lista de monitores")
            return []
        except requests.exceptions.RequestException as e:
            print(f"Error al obtener lista de monitores: {e}")
            return []
    
    def display_monitors(self, monitors: List[Dict]) -> None:
        """
        Muestra la lista de monitores en formato legible
        """
        if not monitors:
            print("No hay monitores para mostrar")
            return
        
        print(f"\n=== Lista de {len(monitors)} monitores ===")
        for i, monitor in enumerate(monitors, 1):
            print(f"{i:3d}. ID: {monitor['id'][:8]}... | Name: {monitor['name']}")

def main():
    """
    Función principal para obtener y mostrar todos los monitores
    """
    print("🚀 Monitor List Service - Uptrends")
    
    # Verificar variables de entorno
    username = os.getenv('UPTRENDS_USERNAME')
    password = os.getenv('UPTRENDS_PASSWORD')
    
    if not username or not password:
        print("❌ Error: Faltan credenciales UPTRENDS_USERNAME y UPTRENDS_PASSWORD")
        return
    
    # Crear instancia del servicio
    monitor_service = MonitorListService(username, password)
    
    # Obtener todos los monitores
    monitors = monitor_service.get_all_monitors()
    
    # Mostrar resultados
    monitor_service.display_monitors(monitors)
    
    # Información adicional
    if monitors:
        print(f"\n📊 Total de monitores encontrados: {len(monitors)}")
        print("✅ Lista generada exitosamente")
    else:
        print("❌ No se pudieron obtener los monitores")

if __name__ == "__main__":
    main()