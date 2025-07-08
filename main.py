#!/usr/bin/env python3

import os
from dotenv import load_dotenv
from rich.table import Table

from uptrends_client import UptrendsClient
from ai_monitor_classifier import AIMonitorClassifier
from migration_script import MigrationScript

load_dotenv()

def main():
    print("🚀 Uptrends Monitor Migration Tool")
    
    # Verificar variables de entorno
    username = os.getenv('UPTRENDS_USERNAME')
    password = os.getenv('UPTRENDS_PASSWORD')
    
    if not username or not password:
        print("❌ Error: Faltan credenciales UPTRENDS_USERNAME y UPTRENDS_PASSWORD")
        return
    
    # Paso 1: Conectar a Uptrends
    print("\n📡 Paso 1: Conectando a Uptrends...")
    try:
        uptrends_client = UptrendsClient(username, password)
        
    except Exception as e:
        print(f"❌ Error conectando a Uptrends: {e}")
        return
    
    # Paso 2: Configurar clasificador IA
    print("\n🤖 Paso 2: Configurando clasificador IA...")
    ollama_host = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
    model_name = os.getenv('OLLAMA_MODEL', 'qwen2.5-coder:7b')
    
    try:
        ai_classifier = AIMonitorClassifier(ollama_host, model_name)
        print(f"✅ Clasificador configurado con modelo: {model_name}")
    except Exception as e:
        print(f"❌ Error configurando clasificador: {e}")
        return
    
    # Paso 3: Obtener patrón de filtro
    print("\n📋 Paso 3: Configurando filtro de monitores...")
    pattern = "CLVT"
    print("\n🚀 Paso 4: Ejecutando proceso de migración...")
    
    try:
        # Crear instancia de migración
        migration = MigrationScript(uptrends_client, ai_classifier)
        
        # Ejecutar migración
        print("\nFlujo: Lista → Filtro → Detalles → Clasificación → Validación → Generación")
        results = migration.migrate_monitors(pattern)
        
        # Mostrar resumen final
        print(f"\n🎉 Migración completada!")
        print(f"📊 Resumen:")
        print(f"  - Total de monitores: {results['total_monitors']}")
        print(f"  - Migraciones exitosas: {results['successful_migrations']}")
        print(f"  - Migraciones fallidas: {results['failed_migrations']}")
        
        # Mostrar archivos generados
        if results['successful_migrations'] > 0:
            print(f"\n📁 Archivos generados en:")
            print(f"  - nodejs-monitors/monitors/lightweight/ (YAML)")
            print(f"  - nodejs-monitors/monitors/journey/ (TypeScript)")
            
        print(f"\n✅ Proceso completado. Revisa los archivos en nodejs-monitors/monitors/")
        
    except Exception as e:
        print(f"❌ Error durante la migración: {e}")
        return

if __name__ == "__main__":
    main()